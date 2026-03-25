
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

    def fetch_and_process_emails(self, days_ck: int = 14, max_results: int = 10000):
        """
        メールを取得して処理する
        
        Args:
            days_ck: 過去何日分をチェックするか
            max_results: 最大取得件数
        """
        if not self.service:
            logging.error("Service not initialized.")
            return

        # 検索クエリの構築
        date_threshold = (datetime.utcnow() - timedelta(days=days_ck)).strftime('%Y/%m/%d')
        # sales@artwize.co.jp 宛て、かつ添付ファイルなし（テキストベースのSES案件メールを想定）
        query = f'to:sales@artwize.co.jp after:{date_threshold} -has:attachment'
        
        logging.info(f"Searching emails with query: {query}")

        try:
            # メッセージ一覧の取得
            results = self.service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute()
            messages = results.get('messages', [])
            
            if not messages:
                logging.info("No messages found.")
                return

            logging.info(f"Found {len(messages)} messages. Processing...")

            # 処理済みチェックと並列処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for msg in messages:
                    # すでにDBにあるかチェック（db_managerにexists機能を追加するのも手だが、saveでIGNOREするのでそのまま投げる）
                    # ただしAPI制限節約のため、できればチェックしたい。
                    # ここではシンプルにsaveの重複排除に任せるが、fetch_detailは行うことになる。
                    futures.append(executor.submit(self._process_single_message, msg['id']))

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logging.error(f"Error in processing thread: {e}")

        except Exception as e:
            logging.error(f"Error during fetch: {e}")

    def _process_single_message(self, message_id: str):
        """1通のメールを詳細取得・解析・保存する"""
        try:
            # 詳細取得
            msg = self.service.users().messages().get(
                userId='me', id=message_id, format='full'
            ).execute()

            # ヘッダー情報の抽出
            headers = {h['name'].lower(): h['value'] for h in msg['payload']['headers']}
            subject = headers.get('subject', 'No Subject')
            sender = headers.get('from', 'Unknown')
            # Dateヘッダーのパース等は省略（DBには受信時の生文字列を入れるか、datetime変換するか）
            # ここではシンプルに文字列として扱うが、received_atには現在時刻またはInternalDateを使用する手もある
            internal_date = int(msg['internalDate']) / 1000
            received_at = datetime.fromtimestamp(internal_date).isoformat()

            # 本文の抽出
            body = self._get_email_body(msg['payload'])
            if not body:
                logging.warning(f"Empty body for message {message_id}")
                return

            # DBへメール保存 (重複時はFalseが返る)
            saved = db_manager.save_email(
                message_id, subject, sender, received_at, body, raw_data=msg
            )
            
            if not saved:
                logging.debug(f"Message {message_id} already exists. Skipping analysis.")
                return

            # 解析（AIまたは従来手法による一括抽出）
            extracted_data = skill_extractor.extract_all(body)
            
            # 人材情報（スキルシート）の場合はスキップ
            if extracted_data.get('type') == 'engineer':
                logging.info(f"Skipping resume/engineer data: {extracted_data.get('title')}")
                return

            # スキル情報を分離
            skills_list = extracted_data.pop('skills', [])
            
            # 案件情報の補正
            project_info = extracted_data
            if not project_info.get('title') or project_info['title'] == '案件名なし':
                 project_info['title'] = subject

            # DBへ案件保存
            project_id = db_manager.save_project(message_id, project_info, skills_list)
            logging.info(f"Processed project {project_id}: {project_info['title']}")

        except Exception as e:
            logging.error(f"Failed to process message {message_id}: {e}", exc_info=True)

    def _get_email_body(self, payload: Dict) -> str:
        """メールペイロードから本文を抽出する（再帰的）"""
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                         body += base64.urlsafe_b64decode(data).decode('utf-8')
                elif part['mimeType'] == 'multipart/alternative':
                    body += self._get_email_body(part)
        elif payload['mimeType'] == 'text/plain':
             data = payload['body'].get('data')
             if data:
                 body = base64.urlsafe_b64decode(data).decode('utf-8')
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
