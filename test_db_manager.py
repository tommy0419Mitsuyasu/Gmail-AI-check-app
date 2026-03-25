
import logging
import sys
import os
import shutil
from datetime import datetime

# UTF-8設定
sys.stdout.reconfigure(encoding='utf-8')

from db_manager import DBManager

# テスト用DBファイル名
TEST_DB = 'test_ses_projects.db'

def test_db_manager():
    # 既存のテストDBがあれば削除
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        
    print(f"Initializing DB: {TEST_DB}...")
    db = DBManager(TEST_DB)
    
    # 1. メール保存テスト
    print("\n[Test 1] Saving Email...")
    msg_id = "msg123"
    saved = db.save_email(
        message_id=msg_id,
        subject="【SES】Javaエンジニア募集",
        sender="sales@example.com",
        received_at=datetime.utcnow().isoformat(),
        body="JavaでのWeb開発案件です。単価: 80万円〜、場所: 渋谷"
    )
    print(f"Email saved: {saved}")
    
    # 2. 案件保存テスト
    print("\n[Test 2] Saving Project...")
    project_data = {
        'title': 'Java Web開発案件',
        'description': 'Spring Bootを用いた開発',
        'min_price': 800000,
        'max_price': 900000,
        'price_text': '80-90万円',
        'location': '渋谷',
        'commercial_flow': 'エンド直'
    }
    skills = [
        {'name': 'Java', 'type': 'must'},
        {'name': 'Spring Boot', 'type': 'must'},
        {'name': 'AWS', 'type': 'want'}
    ]
    
    project_id = db.save_project(msg_id, project_data, skills)
    print(f"Project saved with ID: {project_id}")
    
    # 3. 検索テスト (条件なし)
    print("\n[Test 3] Search All...")
    results = db.search_projects()
    print(f"Found {len(results)} projects")
    if results:
        p = results[0]
        print(f"Title: {p['title']}")
        print(f"Price: {p['min_price']} - {p['max_price']}")
        print(f"Skills: {[s['name'] for s in p['skills']]}")

    # 4. FTS検索テスト
    print("\n[Test 4] FTS Search (keyword='Spring')...")
    results = db.search_projects(keywords='Spring')
    print(f"Found {len(results)} projects")
    
    # 5. 単価検索テスト
    print("\n[Test 5] Price Search (min=850000)...")
    results = db.search_projects(min_price=850000)
    print(f"Found {len(results)} projects (Expected to match because max_price 900000 >= 850000)")

    # 6. スキル検索テスト
    print("\n[Test 6] Skill Search (skill='AWS')...")
    results = db.search_projects(skills=['AWS'])
    print(f"Found {len(results)} projects")

    # クリーンアップ
    print("\nCleaning up...")
    del db
    # os.remove(TEST_DB)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_db_manager()
