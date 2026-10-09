import os
import secrets
import logging
from flask import Flask, session
from flask_cors import CORS
from dotenv import load_dotenv

# Blueprint のインポート
from src.routes.api_routes import api_bp
from src.routes.view_routes import view_bp
from src.routes.gmail_routes import gmail_bp

# データベース初期化
from db_manager import db_manager

# 設定と初期化
load_dotenv()

app = Flask(__name__)
# セッション暗号化用キー（本番環境では環境変数から設定することを推奨）
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key_for_development_12345')

# アップロード設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'doc'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 制限

# ロギングの設定
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# CORSとCSPの設定
CORS(app)  # CORSを有効化

# セキュリティヘッダーを追加するミドルウェア
@app.after_request
def add_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # PDFとWordのダウンロードを許可するためのCSP
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://code.jquery.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://www.googleapis.com https://generativelanguage.googleapis.com; "
        "object-src 'self' data: blob:; "
        "worker-src 'self' blob:; "
        "frame-src 'self' blob:;"
    )
    response.headers['Content-Security-Policy'] = csp
    return response

# Blueprintの登録
app.register_blueprint(api_bp)
app.register_blueprint(view_bp)
app.register_blueprint(gmail_bp)

# リソースの初期化
def initialize_app():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # アップロードフォルダが存在するか確認
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # データベースフォルダが存在するか確認
    os.makedirs(os.path.join(BASE_DIR, 'db'), exist_ok=True)


import threading
import time

def start_batch_scheduler():
    from batch_processor import BatchProcessor
    
    def run_batch_job():
        # 起動直後は30秒待機してから初回実行する
        time.sleep(30)
        while True:
            try:
                logger.info("定期バッチ（メール取得処理）を開始します...")
                processor = BatchProcessor()
                # 最新2日分、最大10000件のメールを取得して解析
                processor.fetch_and_process_emails(days_ck=2, max_results=10000)
                logger.info("定期バッチが正常に完了しました。")
            except Exception as e:
                logger.error(f"定期バッチの実行中にエラーが発生しました: {e}", exc_info=True)
            
            # 5分に1回（300秒）実行
            time.sleep(300)
            
    # Werkzeugの再起動ループでスレッドが二重起動するのを防ぐ
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        thread = threading.Thread(target=run_batch_job, daemon=True)
        thread.start()
        logger.info("バックグラウンドの定期バッチスケジューラーが起動しました。")

if __name__ == '__main__':
    start_batch_scheduler()
    initialize_app()
    app.run(debug=True, port=5000)
