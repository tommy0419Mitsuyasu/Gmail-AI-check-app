from flask import Flask, jsonify, request, g, send_from_directory, url_for, render_template, redirect, send_file, session, flash
from werkzeug.utils import secure_filename
from ruamel import yaml
from flask_cors import CORS
import json
import sqlite3
import os
from datetime import datetime, timedelta
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import re
import PyPDF2
from typing import List, Dict, Any, Optional

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """データベースを初期化する"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # テーブル作成
    c.execute('''
    CREATE TABLE IF NOT EXISTS engineers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        current_role TEXT,
        location TEXT,
        experience_years REAL
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engineer_id INTEGER,
        name TEXT NOT NULL,
        level TEXT,
        FOREIGN KEY (engineer_id) REFERENCES engineers (id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        client_name TEXT,
        description TEXT,
        location TEXT,
        work_type TEXT,
        start_date TEXT,
        duration_months INTEGER,
        min_budget INTEGER,
        max_budget INTEGER
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS project_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        skill TEXT NOT NULL,
        level TEXT,
        weight INTEGER DEFAULT 1,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    ''')
    
    # サンプルデータの挿入
    c.execute("SELECT COUNT(*) FROM engineers")
    if c.fetchone()[0] == 0:
        # サンプルエンジニア
        c.execute('''
        INSERT INTO engineers (name, email, current_role, location, experience_years)
        VALUES (?, ?, ?, ?, ?)
        ''', ('山田太郎', 'yamada@example.com', 'シニアエンジニア', '東京', 8.5))
        
        engineer_id = c.lastrowid
        
        # スキル
        c.executemany('''
        INSERT INTO skills (engineer_id, name, level) VALUES (?, ?, ?)
        ''', [
            (engineer_id, 'Python', 'expert'),
            (engineer_id, 'JavaScript', 'intermediate')
        ])
        
        # プロジェクト
        c.execute('''
        INSERT INTO projects (name, client_name, description, location, work_type, duration_months, min_budget, max_budget)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('ECサイト開発', '株式会社ABC', '大手小売業向けECサイトの開発', '東京', 'リモート可', 6, 5000000, 8000000))
        
        project_id = c.lastrowid
        
        # プロジェクト要件
        c.executemany('''
        INSERT INTO project_requirements (project_id, skill, level, weight) VALUES (?, ?, ?, ?)
        ''', [
            (project_id, 'Python', 'expert', 3),
            (project_id, 'JavaScript', 'intermediate', 2)
        ])
    
    conn.commit()
    conn.close()

# アップロード設定
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
DB_FILE = 'database.db'
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB 制限

# アップロードフォルダが存在するか確認
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# アプリケーションの初期化
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.config['SECRET_KEY'] = 'your-secret-key-here'  # セッション用のシークレットキー
CORS(app)  # CORSを有効化

# データベース初期化
with app.app_context():
    if not os.path.exists(DB_FILE):
        init_db()

# アプリケーション終了時にデータベース接続を閉じる
app.teardown_appcontext(close_db)

# ルートURL
@app.route('/')
def index():
    return render_template('upload.html')

# アップロードを許可する拡張子
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 静的ファイルのルーティング
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# ファイルアップロード用のエンドポイント
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # ここでファイルの内容を解析する処理を実装
        # サンプルとしてダミーデータを返す
        dummy_skills = [
            {"skill_name": "Python", "category_name": "プログラミング言語", "count": 3},
            {"skill_name": "Flask", "category_name": "Webフレームワーク", "count": 2},
            {"skill_name": "JavaScript", "category_name": "プログラミング言語", "count": 1},
            {"skill_name": "Tailwind CSS", "category_name": "CSSフレームワーク", "count": 1},
        ]
        
        # テキストの抽出（実際にはファイルからテキストを抽出する処理を実装）
        extracted_text = "これはサンプルの抽出されたテキストです。実際のアプリケーションでは、アップロードされたファイルからテキストが抽出されます。"
        
        return jsonify({
            'success': True,
            'skills': dummy_skills,
            'text': extracted_text
        })
    
    return jsonify({'error': '許可されていないファイル形式です'}), 400

# Gmail検索用のエンドポイント
@app.route('/api/search_gmail', methods=['POST'])
def search_gmail():
    data = request.get_json()
    query = data.get('query', '')
    max_results = data.get('maxResults', 10)
    
    # ここでGmail APIを使用して検索を実行
    # サンプルとしてダミーデータを返す
    dummy_emails = [
        {
            "id": "12345",
            "sender": "recruiter@example.com",
            "subject": "Pythonエンジニアの求人について",
            "snippet": "PythonとFlaskの経験を活かせる案件がございます。ぜひご検討ください。",
            "date": "2025-06-01T10:30:00"
        },
        {
            "id": "12346",
            "sender": "hr@tech-company.com",
            "subject": "Webアプリケーション開発の案件情報",
            "snippet": "JavaScriptとReactを使用したWebアプリケーション開発の案件がございます。",
            "date": "2025-05-30T14:15:00"
        }
    ]
    
    return jsonify({
        'success': True,
        'emails': dummy_emails
    })

# Gmail認証用のエンドポイント
@app.route('/gmail_auth')
def gmail_auth():
    # ここでGmail認証の処理を実装
    # サンプルとして認証済みとして扱う
    return redirect(url_for('index'))

# Gmail認証状態確認用のエンドポイント
@app.route('/gmail_auth/status')
def gmail_auth_status():
    # サンプルとして認証済みとして扱う
    return jsonify({
        'authenticated': True,
        'email': 'user@example.com'
    })

# エラーメッセージ
error_messages = {
    'no_file': 'ファイルが選択されていません',
    'invalid_extension': '許可されていないファイル形式です。PDFまたはWord文書をアップロードしてください。',
    'file_too_large': f'ファイルサイズが大きすぎます。{MAX_FILE_SIZE // (1024*1024)}MB以下のファイルをアップロードしてください。',
    'upload_failed': 'ファイルのアップロードに失敗しました。',
    'processing_error': 'ファイルの処理中にエラーが発生しました。',
    'invalid_file': 'ファイルが破損しているか、サポートされていない形式です。'
}

# Gmail APIの設定
# Gmail APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    # ここにGmail APIの認証処理を実装
    creds = None
    # トークンファイルが存在する場合は読み込む
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # 有効な認証情報がない場合はNoneを返す
    if not creds or not creds.valid:
        return None
    
    try:
        # Gmail APIのサービスを構築して返す
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        app.logger.error(f"Gmailサービスの作成中にエラーが発生しました: {e}")
        return None

if __name__ == '__main__':
    # アップロードフォルダが存在するか確認
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        
    app.run(debug=True, port=5000, host='0.0.0.0')
