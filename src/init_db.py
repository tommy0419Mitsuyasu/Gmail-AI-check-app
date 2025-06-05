import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.database import create_tables, engine
from models.db_models import *

def init_db():
    """データベースを初期化し、テーブルを作成"""
    print("データベースを初期化しています...")
    create_tables()
    print("データベースの初期化が完了しました。")

if __name__ == "__main__":
    init_db()
