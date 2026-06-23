import logging
import time
import os
import sqlite3
from typing import List, Dict, Any
from dotenv import load_dotenv

from db_manager import db_manager
from skill_extractor import skill_extractor

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('reprocess.log', encoding='utf-8')
    ]
)

# 環境変数ロード
load_dotenv()

def get_all_emails() -> List[Dict[str, Any]]:
    """DBから全てのメールを取得する"""
    conn = sqlite3.connect(db_manager.db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute('SELECT message_id, body, subject, received_at FROM emails')
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()

def clear_project_data(message_id: str):
    """特定のメッセージIDに関連するプロジェクトとスキル紐付けを削除する"""
    conn = sqlite3.connect(db_manager.db_path)
    c = conn.cursor()
    try:
        # プロジェクトIDを取得
        c.execute('SELECT id FROM projects WHERE email_message_id = ?', (message_id,))
        project_rows = c.fetchall()
        
        for row in project_rows:
            project_id = row[0]
            # 紐付け削除
            c.execute('DELETE FROM project_skills WHERE project_id = ?', (project_id,))
            # FTS削除
            c.execute('DELETE FROM projects_fts WHERE rowid = ?', (project_id,))
            
        # プロジェクト削除
        c.execute('DELETE FROM projects WHERE email_message_id = ?', (message_id,))
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to clear data for {message_id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def reprocess_all():
    """全メールを再処理する"""
    emails = get_all_emails()
    logging.info(f"Found {len(emails)} emails. Starting reprocessing...")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for i, email in enumerate(emails):
        msg_id = email['message_id']
        subject = email['subject']
        body = email['body']
        
        logging.info(f"[{i+1}/{len(emails)}] Processing: {subject}")
        
        try:
            # 1. 既存データの削除
            clear_project_data(msg_id)
            
            # 2. 解析 (ルールベース)
            extracted_data = skill_extractor.extract_all(body)
            
            if not extracted_data:
                logging.error(f" -> Failed to extract data for {msg_id}")
                error_count += 1
                continue
            
            # 3. 人材情報ならスキップ
            if extracted_data.get('type') == 'engineer':
                logging.info(f" -> Skipped (Type: Engineer)")
                skip_count += 1
                continue
                
            # 4. データ整形と保存
            skills_list = extracted_data.pop('skills', [])
            
            project_info = extracted_data
            # タイトル補完
            if not project_info.get('title') or project_info['title'] == '案件名なし':
                 project_info['title'] = subject
            
            # 保存
            project_id = db_manager.save_project(msg_id, project_info, skills_list)
            logging.info(f" -> Saved Project ID: {project_id}")
            success_count += 1
            
        except Exception as e:
            logging.error(f" -> Error processing {msg_id}: {e}")
            error_count += 1
            
    logging.info("------------------------------------------------")
    logging.info(f"Reprocessing Complete.")
    logging.info(f"Success: {success_count}")
    logging.info(f"Skipped (Engineer/Resume): {skip_count}")
    logging.info(f"Errors: {error_count}")
    logging.info("------------------------------------------------")

if __name__ == "__main__":
    reprocess_all()
