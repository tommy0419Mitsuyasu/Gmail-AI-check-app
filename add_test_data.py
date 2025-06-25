import sqlite3
from datetime import datetime, timedelta

def add_test_data():
    try:
        # データベースに接続
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # 既存のテストデータを削除（必要に応じてコメントアウト）
        cursor.execute("DELETE FROM project_requirements")
        cursor.execute("DELETE FROM projects")
        cursor.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name IN ('projects', 'project_requirements')")
        
        # テスト用のプロジェクトデータ
        projects = [
            {
                'name': 'ECサイト開発',
                'client_name': '株式会社ABC',
                'description': '大手小売業向けECサイトの開発',
                'location': '東京',
                'work_type': 'リモート可',
                'start_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
                'duration_months': 6,
                'min_budget': 5000000,
                'max_budget': 8000000,
                'requirements': [
                    {'skill': 'Python', 'level': 'expert', 'weight': 3},
                    {'skill': 'Django', 'level': 'intermediate', 'weight': 2},
                    {'skill': 'JavaScript', 'level': 'intermediate', 'weight': 2},
                    {'skill': 'HTML/CSS', 'level': 'basic', 'weight': 1}
                ]
            },
            {
                'name': 'モバイルアプリ開発',
                'client_name': '株式会社XYZ',
                'description': '健康管理アプリの開発',
                'location': '大阪',
                'work_type': 'ハイブリッド',
                'start_date': (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d'),
                'duration_months': 4,
                'min_budget': 4000000,
                'max_budget': 6000000,
                'requirements': [
                    {'skill': 'React Native', 'level': 'intermediate', 'weight': 3},
                    {'skill': 'TypeScript', 'level': 'intermediate', 'weight': 2},
                    {'skill': 'Firebase', 'level': 'basic', 'weight': 1}
                ]
            },
            {
                'name': 'データ分析基盤構築',
                'client_name': '株式会社データソリューション',
                'description': 'ビッグデータ分析基盤の構築',
                'location': 'リモート',
                'work_type': 'リモート',
                'start_date': (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d'),
                'duration_months': 3,
                'min_budget': 3000000,
                'max_budget': 5000000,
                'requirements': [
                    {'skill': 'Python', 'level': 'intermediate', 'weight': 2},
                    {'skill': 'SQL', 'level': 'intermediate', 'weight': 2},
                    {'skill': 'AWS', 'level': 'basic', 'weight': 1},
                    {'skill': 'データ分析', 'level': 'intermediate', 'weight': 2}
                ]
            }
        ]
        
        # プロジェクトを追加
        for project in projects:
            # プロジェクトを追加
            cursor.execute('''
                INSERT INTO projects (
                    name, client_name, description, location, 
                    work_type, start_date, duration_months, 
                    min_budget, max_budget
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project['name'],
                project['client_name'],
                project['description'],
                project['location'],
                project['work_type'],
                project['start_date'],
                project['duration_months'],
                project['min_budget'],
                project['max_budget']
            ))
            
            # 追加したプロジェクトのIDを取得
            project_id = cursor.lastrowid
            
            # プロジェクト要件を追加
            for req in project['requirements']:
                cursor.execute('''
                    INSERT INTO project_requirements (
                        project_id, skill, level, weight
                    ) VALUES (?, ?, ?, ?)
                ''', (
                    project_id,
                    req['skill'],
                    req['level'],
                    req['weight']
                ))
        
        # 変更をコミット
        conn.commit()
        print("テストデータの追加が完了しました")
        
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_test_data()
