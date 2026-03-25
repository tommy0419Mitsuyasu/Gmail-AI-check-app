import os
import sqlite3
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skill_extractor import skill_extractor
from db_manager import db_manager

def clean_db():
    print("データベースのクレンジングを開始します...")
    
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    
    # 全案件のタイトルと詳細または本文を取得
    # emailsテーブルから取得できればベスト
    cursor.execute("""
        SELECT p.id, p.email_message_id, p.title, e.body 
        FROM projects p 
        LEFT JOIN emails e ON p.email_message_id = e.message_id
    """)
    rows = cursor.fetchall()
    
    deleted_count = 0
    checked_count = 0
    
    for row in rows:
        proj_id, msg_id, title, body = row
        checked_count += 1
        
        # 判定用テキスト (bodyがなければtitleを判定に使う)
        text_to_check = body if body else title
        if not text_to_check:
            continue
            
        record_type = skill_extractor._determine_record_type(text_to_check)
        
        if record_type == 'engineer':
            print(f"削除対象(人材シート判定): [{proj_id}] {title}")
            
            # DBから削除
            cursor.execute("DELETE FROM project_skills WHERE project_id = ?", (proj_id,))
            cursor.execute("DELETE FROM projects WHERE id = ?", (proj_id,))
            deleted_count += 1
            
    conn.commit()
    conn.close()
    
    print(f"完了しました！ {checked_count} 件中、 {deleted_count} 件の「人材シート（ノイズ枠）」を案件データベースから削除しました。")

if __name__ == '__main__':
    clean_db()
