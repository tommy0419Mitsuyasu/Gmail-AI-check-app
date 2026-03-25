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
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(16))

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

if __name__ == '__main__':
    initialize_app()
    app.run(debug=True, port=5000)
