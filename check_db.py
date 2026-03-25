import sqlite3
import json

def check_database():
    output = []
    
    def log(message):
        print(message)
        output.append(str(message) + '\n')
    
    try:
        # データベースに接続
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row  # カラム名でアクセスできるようにする
        cursor = conn.cursor()
        
        # テーブル一覧を取得
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        log("\n=== テーブル一覧 ===")
        for table in tables:
            log(f"- {table['name']}")
        
        # 各テーブルの内容を表示
        for table in tables:
            table_name = table['name']
            log(f"\n=== {table_name} テーブルの内容 ===")
            
            try:
                # テーブルのカラム情報を取得
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                column_names = [col['name'] for col in columns]
                log(f"カラム: {', '.join(column_names)}")
                
                # テーブルのデータ数を取得
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name};")
                count = cursor.fetchone()['count']
                log(f"レコード数: {count}")
                
                # テーブルのデータを取得（最大20件）
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 20;")
                rows = cursor.fetchall()
                
                if not rows:
                    log("データがありません")
                else:
                    log("データ:")
                    for i, row in enumerate(rows, 1):
                        row_dict = dict(row)
                        # バイナリデータは表示しない
                        for key, value in row_dict.items():
                            if isinstance(value, (bytes, bytearray)):
                                row_dict[key] = f"<binary data: {len(value)} bytes>"
                        log(f"[{i}] {json.dumps(row_dict, ensure_ascii=False, default=str)}")
                
                # 外部キー関係を確認
                if table_name in ['project_requirements', 'skills']:
                    log("\n外部キー関係:")
                    if table_name == 'project_requirements':
                        cursor.execute("PRAGMA foreign_key_list(project_requirements);")
                    elif table_name == 'skills':
                        cursor.execute("PRAGMA foreign_key_list(skills);")
                    fk_info = cursor.fetchall()
                    if fk_info:
                        for fk in fk_info:
                            log(f"- {fk}")
                    else:
                        log("外部キー制約は設定されていません")
                        
            except sqlite3.Error as e:
                log(f"エラー: {str(e)}")
        
    except sqlite3.Error as e:
        log(f"データベースエラー: {str(e)}")
    finally:
        if conn:
            conn.close()
    
    # 結果をファイルに保存
    with open('database_dump.txt', 'w', encoding='utf-8') as f:
        f.writelines(output)
    print("\nデータベースの内容を 'database_dump.txt' に保存しました")

if __name__ == "__main__":
    check_database()
