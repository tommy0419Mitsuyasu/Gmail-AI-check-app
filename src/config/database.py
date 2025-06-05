from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session
from typing import Generator

# モデルをインポートして、SQLAlchemyにテーブルを作成させるために必要
from models.db_models import *
import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# ベースディレクトリを設定
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# データベースファイルのパス
DATABASE_URL = f"sqlite:///{BASE_DIR}/sql_app.db"

# SQLAlchemyエンジンの作成
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=True  # 開発用にSQLログを出力
)

# セッションファクトリの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """
    データベースセッションを取得する依存関係
    各リクエストで新しいセッションを作成し、リクエスト終了時にクローズ
    
    Yields:
        Session: SQLAlchemy セッションオブジェクト
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """データベーステーブルを作成"""
    SQLModel.metadata.create_all(bind=engine)
    print("テーブルが正常に作成されました。")
