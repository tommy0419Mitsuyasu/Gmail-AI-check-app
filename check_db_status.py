
import sqlite3
import json
import sys

# UTF-8出力設定
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'ses_projects.db'

def check_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=== Database Status Check ===\n")

    # 1. 件数確認
    n_emails = cursor.execute("SELECT count(*) FROM emails").fetchone()[0]
    n_projects = cursor.execute("SELECT count(*) FROM projects").fetchone()[0]
    n_skills = cursor.execute("SELECT count(*) FROM skills").fetchone()[0]
    n_links = cursor.execute("SELECT count(*) FROM project_skills").fetchone()[0]
    n_fts = cursor.execute("SELECT count(*) FROM projects_fts").fetchone()[0]

    print(f"Emails: {n_emails}")
    print(f"Projects: {n_projects}")
    print(f"Skills Master: {n_skills}")
    print(f"Project-Skill Links: {n_links}")
    print(f"FTS Index Rows: {n_fts}")
    print("\n--------------------------------\n")

    # 2. 直近の案件詳細確認（スキル紐付け含む）
    print("=== Latest 5 Projects ===")
    projects = cursor.execute("""
        SELECT p.id, p.title, p.min_price, p.max_price, p.description
        FROM projects p
        ORDER BY p.id DESC
        LIMIT 5
    """).fetchall()

    for p in projects:
        print(f"\n[ID: {p['id']}] {p['title']}")
        print(f"Price: {p['min_price']} - {p['max_price']}")
        
        # 紐付いているスキル
        skills = cursor.execute("""
            SELECT s.name, ps.type
            FROM project_skills ps
            JOIN skills s ON ps.skill_id = s.id
            WHERE ps.project_id = ?
        """, (p['id'],)).fetchall()
        
        skill_names = [f"{s['name']}({s['type']})" for s in skills]
        print(f"Skills: {', '.join(skill_names) if skill_names else 'NONE detected'}")
        
        # FTSデータ確認
        fts = cursor.execute("SELECT skills_text FROM projects_fts WHERE rowid = ?", (p['id'],)).fetchone()
        if fts:
            print(f"FTS Text: {fts['skills_text']}")
        else:
            print("FTS Index: MISSING")
            
    conn.close()

if __name__ == "__main__":
    check_data()
