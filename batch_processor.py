
import os
import json
import logging
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_manager import db_manager
from skill_extractor import skill_extractor
from vector_engine import vector_engine
import numpy as np

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('batch_processor.log', encoding='utf-8')
    ]
)

class BatchProcessor:
    def __init__(self, token_file: str = 'token.json', max_workers: int = 5):
        """
        バッチプロセッサの初期化
        
        Args:
            token_file: 認証トークンファイルのパス
            max_workers: 並列処理のスレッド数
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.token_file = os.path.join(base_dir, token_file) if not os.path.isabs(token_file) else token_file
        self.max_workers = 1 # googleapiclientはスレッドセーフではないため、マルチスレッドを無効化
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Gmail APIの認証を行う"""
        try:
            if not os.path.exists(self.token_file):
                logging.error(f"Token file not found: {self.token_file}")
                logging.error("Please log in via the web application first to generate the token.")
                return

            with open(self.token_file, 'r', encoding='utf-8') as f:
                creds_data = json.load(f)

            creds = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data.get('refresh_token'),
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )

            if creds.expired and creds.refresh_token:
                logging.info("Refreshing expired token...")
                creds.refresh(Request())
                # 更新されたトークンを保存
                creds_data.update({
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None
                })
                with open(self.token_file, 'w', encoding='utf-8') as f:
                    json.dump(creds_data, f)

            self.service = build('gmail', 'v1', credentials=creds)
            logging.info("Gmail API authenticated successfully.")

        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            self.service = None

    def fetch_and_process_emails(self, days_ck: int = 14, max_results: int = 1000):
        """
        メールを取得して処理する
        
        Args:
            days_ck: 過去何日分をチェックするか
            max_results: 最大取得件数
        """
        if not self.service:
            logging.error("Service not initialized.")
            return

        # historyIdの取得
        history_id = db_manager.get_sync_state('historyId')
        new_message_ids = []
        next_history_id = None
        
        try:
            if history_id:
                logging.info(f"Fetching changes since historyId: {history_id}")
                try:
                    page_token = None
                    while True:
                        res = self.service.users().history().list(
                            userId='me', startHistoryId=history_id, pageToken=page_token
                        ).execute()
                        next_history_id = res.get('historyId')
                        for history in res.get('history', []):
                            for msg_added in history.get('messagesAdded', []):
                                new_message_ids.append(msg_added['message']['id'])
                        page_token = res.get('nextPageToken')
                        if not page_token:
                            break
                except Exception as e:
                    logging.warning(f"History sync failed, falling back to full sync: {e}")
                    history_id = None
            
            if not history_id:
                # 検索クエリの構築（フルシンク）
                date_threshold = (datetime.utcnow() - timedelta(days=days_ck)).strftime('%Y/%m/%d')
                query = f'to:sales@artwize.co.jp after:{date_threshold}'  # 添付ファイル制限を撤廃 (-has:attachmentを削除)
                logging.info(f"Searching emails with query: {query}")

                page_token = None
                while len(new_message_ids) < max_results:
                    results = self.service.users().messages().list(
                        userId='me', q=query, maxResults=min(500, max_results - len(new_message_ids)), pageToken=page_token
                    ).execute()
                    
                    msgs = results.get('messages', [])
                    if not msgs:
                        break
                        
                    new_message_ids.extend([m['id'] for m in msgs])
                    
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break
                        
                # 最新のhistoryIdを保存する用
                try:
                    prof = self.service.users().getProfile(userId='me').execute()
                    next_history_id = prof.get('historyId')
                except Exception as e:
                    logging.error(f"Failed to get profile for historyId: {e}")

            # 重複排除のために一意にする
            new_message_ids = list(set(new_message_ids))
            if not new_message_ids:
                logging.info("No new messages found.")
                if next_history_id:
                    db_manager.set_sync_state('historyId', next_history_id)
                return

            logging.info(f"Found {len(new_message_ids)} messages. Checking against DB...")

            # 処理済みチェック
            conn = db_manager._get_connection()
            c = conn.cursor()
            unprocessed_ids = []
            for msg_id in new_message_ids:
                c.execute("SELECT status FROM emails WHERE message_id = ?", (msg_id,))
                row = c.fetchone()
                if not row or row[0] == 'failed':
                    unprocessed_ids.append(msg_id)
            conn.close()

            logging.info(f"Processing {len(unprocessed_ids)} new messages...")

            if not unprocessed_ids:
                if next_history_id:
                    db_manager.set_sync_state('historyId', next_history_id)
                return

            # Batch request processing
            existing_simhashes = set(db_manager.get_existing_simhashes())
            
            def process_message_callback(request_id, response, exception):
                if exception is not None:
                    logging.error(f"Error fetching message: {exception}")
                    return
                self._process_single_message(response, existing_simhashes)
                
            batch_size = 50
            for i in range(0, len(unprocessed_ids), batch_size):
                batch = self.service.new_batch_http_request(callback=process_message_callback)
                batch_ids = unprocessed_ids[i:i+batch_size]
                logging.info(f"Fetching batch {i//batch_size + 1}: {len(batch_ids)} messages")
                for msg_id in batch_ids:
                    batch.add(self.service.users().messages().get(userId='me', id=msg_id, format='full'))
                try:
                    batch.execute()
                except Exception as e:
                    logging.error(f"Batch execution failed: {e}")
                    
            # 処理完了後にhistoryIdを更新
            if next_history_id:
                db_manager.set_sync_state('historyId', next_history_id)

        except Exception as e:
            logging.error(f"Error during fetch: {e}")

    def _process_single_message(self, msg: Dict, existing_simhashes: set):
        """1通のメールを詳細解析・保存する"""
        message_id = msg['id']
        try:
            # ヘッダー情報の抽出
            headers = {h['name'].lower(): h['value'] for h in msg['payload']['headers']}
            subject = headers.get('subject', 'No Subject')
            sender = headers.get('from', 'Unknown')
            internal_date = int(msg['internalDate']) / 1000
            received_at = datetime.fromtimestamp(internal_date).isoformat()

            # 本文の抽出
            body = self._get_email_body(msg['payload'])
            if not body:
                logging.warning(f"Empty body for message {message_id}")
                db_manager.save_email(message_id, subject, sender, received_at, "", raw_data=None, status='failed')
                return

            # Simhash計算
            import re
            from simhash import Simhash
            
            norm_body = re.sub(r'お世話になっております。?.*$', '', body, flags=re.MULTILINE)
            norm_body = re.sub(r'よろしくお願いいたします。?.*$', '', norm_body, flags=re.MULTILINE)
            norm_body = re.sub(r'[-_]{4,}', '', norm_body)
            norm_body = re.sub(r'\s+', '', norm_body)
            simhash_val = str(Simhash(norm_body).value) if norm_body else ""
            
            if simhash_val in existing_simhashes and simhash_val != "":
                logging.debug(f"Message {message_id} is a duplicate (simhash match).")
                db_manager.save_email(message_id, subject, sender, received_at, body, raw_data=None, status='done', simhash_val=simhash_val)
                return
            
            existing_simhashes.add(simhash_val)

            # DBへメール保存 (raw_dataは保存しない)
            db_manager.save_email(
                message_id, subject, sender, received_at, body, raw_data=None, status='pending', simhash_val=simhash_val
            )
            
            # 抽出（AIまたは正規表現によるフォールバック）
            try:
                extracted_data = skill_extractor.extract_all(body)
            except Exception as e:
                logging.warning(f"Extraction failed for {message_id}: {e}")
                db_manager.update_email_status(message_id, 'failed')
                return
            
            if not extracted_data:
                db_manager.update_email_status(message_id, 'failed')
                return

            # 人材情報（スキルシート）の場合はスキップ
            if extracted_data.get('type') == 'engineer':
                logging.info(f"Skipping resume/engineer data: {message_id}")
                db_manager.update_email_status(message_id, 'done')
                return

            projects = extracted_data.get('projects', [])
            if not projects:
                # 古い形式の互換性用フォールバック
                skills_list = extracted_data.pop('skills', [])
                project_info = extracted_data
                if not project_info.get('title') or project_info['title'] == '案件なし':
                    project_info['title'] = subject
                
                # ベクトル計算
                proj_text = f"{project_info.get('title', '')}\n{project_info.get('description', '')}\n{' '.join([s.get('name', '') for s in skills_list])}"
                emb_arr = vector_engine.encode(proj_text)
                emb_bytes = emb_arr.astype(np.float32).tobytes() if emb_arr.size > 0 else None
                
                db_manager.save_project(message_id, project_info, skills_list, embedding=emb_bytes)
                logging.info(f"Processed 1 project from {message_id}")
            else:
                for idx, project_info in enumerate(projects):
                    skills_list = project_info.pop('skills', [])
                    if not project_info.get('title') or project_info['title'] == '案件なし':
                        project_info['title'] = f"{subject} ({idx+1})"
                        
                    # ベクトル計算
                    proj_text = f"{project_info.get('title', '')}\n{project_info.get('description', '')}\n{' '.join([s.get('name', '') for s in skills_list])}"
                    emb_arr = vector_engine.encode(proj_text)
                    emb_bytes = emb_arr.astype(np.float32).tobytes() if emb_arr.size > 0 else None
                    
                    project_id = db_manager.save_project(message_id, project_info, skills_list, embedding=emb_bytes)
                    logging.info(f"Processed project {project_id}: {project_info['title']}")
            
            db_manager.update_email_status(message_id, 'done')

        except Exception as e:
            logging.error(f"Failed to process message {message_id}: {e}", exc_info=True)
            db_manager.update_email_status(message_id, 'failed')

    def _get_email_body(self, payload: Dict) -> str:
        """メールの本文を抽出（再帰的）し、マルチパートやHTMLにも対応"""
        import base64
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            BeautifulSoup = None

        body = ""
        parts = payload.get('parts', [payload]) if 'parts' in payload else [payload]
        
        for part in parts:
            mime_type = part.get('mimeType', '')
            if mime_type == 'text/plain':
                data = part.get('body', {}).get('data')
                if data:
                    try:
                        body += base64.urlsafe_b64decode(data).decode('utf-8')
                    except UnicodeDecodeError:
                        body += base64.urlsafe_b64decode(data).decode('cp932', errors='ignore')
            elif mime_type == 'text/html':
                data = part.get('body', {}).get('data')
                if data:
                    try:
                        html = base64.urlsafe_b64decode(data).decode('utf-8')
                    except UnicodeDecodeError:
                        html = base64.urlsafe_b64decode(data).decode('cp932', errors='ignore')
                    if BeautifulSoup:
                        body += BeautifulSoup(html, 'html.parser').get_text(separator='\n')
                    else:
                        import re
                        body += re.sub('<[^<]+?>', '\n', html)
            elif mime_type.startswith('multipart/'):
                body += self._get_email_body(part)
                
        return body

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='SES Email Batch Processor')
    parser.add_argument('--days', type=int, default=14, help='Lookback days')
    parser.add_argument('--limit', type=int, default=100, help='Max emails to process')
    parser.add_argument('--workers', type=int, default=5, help='Number of worker threads')
    args = parser.parse_args()

    processor = BatchProcessor(max_workers=args.workers)
    processor.fetch_and_process_emails(days_ck=args.days, max_results=args.limit)
