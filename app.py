import os
import re
from typing import Dict, List, Optional
from pathlib import Path
import PyPDF2

# 開発環境用の設定（本番環境では削除またはコメントアウト）
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, jsonify, request, g, send_from_directory, url_for, render_template, redirect, send_file, session, flash, make_response, current_app
from werkzeug.utils import secure_filename
from ruamel import yaml
from flask_cors import CORS
import json
import pickle
from googleapiclient.discovery import build
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
        id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        current_role TEXT,
        location TEXT,
        experience_years REAL,
        skills TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
app = Flask(__name__)
# セキュアなセッション設定
app.secret_key = os.urandom(24)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600,  # 1時間
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=MAX_FILE_SIZE,
    SQLALCHEMY_DATABASE_URI=f'sqlite:///{DB_FILE}',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# ロギングの設定
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# CORSとCSPの設定
CORS(app)  # CORSを有効化

# Gmail認証状態を確認する関数
def check_gmail_auth():
    """Gmail認証状態を確認し、認証されていない場合はFalseを返す"""
    if 'credentials' not in session:
        app.logger.debug("No credentials in session")
        return False
    
    try:
        # セッションから認証情報を復元
        creds_dict = session['credentials']
        
        # 有効期限をdatetimeオブジェクトに変換
        if 'expiry' in creds_dict and isinstance(creds_dict['expiry'], str):
            creds_dict['expiry'] = datetime.fromisoformat(creds_dict['expiry'])
        
        credentials = Credentials(**creds_dict)
        
        # トークンの有効期限を確認（10分以内に切れる場合はリフレッシュを試みる）
        if credentials.expired or (credentials.expiry and 
                                 (credentials.expiry - datetime.utcnow().replace(tzinfo=timezone.utc)).total_seconds() < 600):
            app.logger.info("Token expired or about to expire, attempting to refresh...")
            if credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    # 更新した認証情報をセッションに保存
                    session['credentials'] = {
                        'token': credentials.token,
                        'refresh_token': credentials.refresh_token,
                        'token_uri': credentials.token_uri,
                        'client_id': credentials.client_id,
                        'client_secret': credentials.client_secret,
                        'scopes': credentials.scopes,
                        'expiry': credentials.expiry.isoformat() if credentials.expiry else None
                    }
                    session.modified = True
                    app.logger.info("Successfully refreshed token")
                except Exception as e:
                    app.logger.error(f"Failed to refresh token: {str(e)}")
                    session.pop('credentials', None)
                    return False
        return True
    except Exception as e:
        app.logger.error(f"Error checking auth status: {str(e)}", exc_info=True)
        session.pop('credentials', None)
        return False

# 認証が必要なルートのミドルウェア
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 認証不要なパスはスキップ
        if request.path in ['/', '/gmail/auth', '/gmail/auth/callback', '/api/auth/status']:
            return f(*args, **kwargs)
            
        # 認証状態を確認
        if not check_gmail_auth():
            # 現在のURLをセッションに保存
            session['next'] = request.url
            return redirect(url_for('gmail_auth'))
        return f(*args, **kwargs)
    return decorated_function

# セキュリティヘッダーを追加するミドルウェア
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Content Security Policy (CSP) の設定
    csp_policy = """
        default-src 'self';
        script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://unpkg.com;
        style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com;
        img-src 'self' data: https: http:;
        font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net;
        connect-src 'self' http://localhost:5000;
        frame-ancestors 'self';
    """.replace('\n', ' ').replace('  ', '').strip()
    
    response.headers['Content-Security-Policy'] = csp_policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
    
    return response

# スキルキーワード（必要に応じて追加）
SKILL_KEYWORDS = [
    'Python', 'JavaScript', 'Java', 'C#', 'C++', 'Ruby', 'PHP', 'Go', 'Swift', 'Kotlin',
    'Django', 'Flask', 'FastAPI', 'React', 'Vue.js', 'Angular', 'Node.js', 'Spring', 'Laravel',
    'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Terraform', 'Ansible',
    'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch',
    '機械学習', '深層学習', 'データ分析', 'データベース', 'API開発', 'セキュリティ',
    'テスト', 'CI/CD', 'DevOps', 'アジャイル', 'スクラム', 'Git', 'GitHub', 'GitLab', 'Bitbucket'
]

def extract_text_from_pdf(file_path: str) -> str:
    """
    PDFファイルからテキストを抽出する
    
    Args:
        file_path (str): 抽出するPDFファイルのパス
        
    Returns:
        str: 抽出されたテキスト
        
    Raises:
        Exception: ファイルの読み込みやテキスト抽出に失敗した場合
    """
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            
            # パスワードで保護されたPDFの処理
            if reader.is_encrypted:
                try:
                    # 空のパスワードで試行
                    reader.decrypt('')
                except:
                    # パスワードが必要な場合はエラーをスロー
                    raise Exception('パスワードで保護されたPDFのため、テキストを抽出できません')
            
            # 各ページからテキストを抽出
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
            
            # テキストが空の場合はエラーをスロー
            if not text.strip():
                raise Exception('PDFからテキストを抽出できませんでした。画像のみのPDFの可能性があります。')
                
            return text
            
    except Exception as e:
        raise Exception(f'PDFの処理中にエラーが発生しました: {str(e)}')

def extract_text_from_docx(file_path: str) -> str:
    """
    Word文書(.docx, .doc)からテキストを抽出する
    
    Args:
        file_path (str): 抽出するWordファイルのパス
        
    Returns:
        str: 抽出されたテキスト
        
    Raises:
        Exception: ファイルの読み込みやテキスト抽出に失敗した場合
    """
    try:
        import docx2txt
        
        # ファイルが存在するか確認
        if not os.path.exists(file_path):
            raise FileNotFoundError('指定されたファイルが見つかりません')
            
        # ファイル拡張子を確認
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in ['.docx', '.doc']:
            raise ValueError('サポートされていないファイル形式です')
            
        # テキストを抽出
        text = docx2txt.process(file_path)
        
        # テキストが空の場合はエラーをスロー
        if not text or not text.strip():
            raise Exception('ドキュメントからテキストを抽出できませんでした')
            
        return text
        
    except ImportError:
        raise ImportError('docx2txtライブラリがインストールされていません。`pip install docx2txt`を実行してインストールしてください。')
    except Exception as e:
        raise Exception(f'Word文書の処理中にエラーが発生しました: {str(e)}')

def extract_skills(text: str) -> Dict[str, List[str]]:
    """テキストからスキルを抽出する"""
    text_lower = text.lower()
    found_skills = {
        'programming_languages': [],
        'frameworks': [],
        'cloud_services': [],
        'databases': [],
        'other_skills': []
    }
    
    # スキルのカテゴリ分け
    skill_categories = {
        'programming_languages': ['python', 'javascript', 'java', 'c#', 'c++', 'ruby', 'php', 'go', 'swift', 'kotlin'],
        'frameworks': ['django', 'flask', 'fastapi', 'react', 'vue', 'angular', 'node.js', 'spring', 'laravel'],
        'cloud_services': ['aws', 'amazon web services', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'terraform', 'ansible'],
        'databases': ['mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle', 'sql server']
    }
    
    # スキルを抽出してカテゴリ分け
    for skill in SKILL_KEYWORDS:
        skill_lower = skill.lower()
        if re.search(r'\b' + re.escape(skill_lower) + r'\b', text_lower):
            added = False
            for category, keywords in skill_categories.items():
                if any(keyword in skill_lower for keyword in keywords):
                    found_skills[category].append(skill)
                    added = True
                    break
            if not added:
                found_skills['other_skills'].append(skill)
    
    return found_skills

def analyze_resume(file_path: str) -> Dict:
    """スキルシートを解析してスキルを抽出する"""
    file_extension = Path(file_path).suffix.lower()
    
    try:
        # ファイルの存在確認
        if not os.path.exists(file_path):
            return {'status': 'error', 'message': 'ファイルが見つかりません'}
            
        # ファイルサイズの確認（10MB以下）
        if os.path.getsize(file_path) > 10 * 1024 * 1024:  # 10MB
            return {'status': 'error', 'message': 'ファイルサイズが大きすぎます（10MBまで）'}
        
        # ファイルの種類に応じてテキスト抽出
        text = ""
        try:
            if file_extension == '.pdf':
                text = extract_text_from_pdf(file_path)
            elif file_extension in ['.docx', '.doc']:
                text = extract_text_from_docx(file_path)
            else:
                return {'status': 'error', 'message': 'サポートされていないファイル形式です'}
                
            # テキストが空でないか確認
            if not text or not text.strip():
                return {'status': 'error', 'message': 'ファイルからテキストを抽出できませんでした'}
                
        except Exception as e:
            return {'status': 'error', 'message': f'ファイルの解析中にエラーが発生しました: {str(e)}'}
        
        # スキル抽出
        try:
            skills = extract_skills(text)
            return {
                'status': 'success',
                'file_type': file_extension,
                'text_length': len(text),
                'skills': skills,
                'extracted_text': text[:1000] + ('...' if len(text) > 1000 else '')  # プレビュー用に最初の1000文字を返す
            }
        except Exception as e:
            return {'status': 'error', 'message': f'スキル抽出中にエラーが発生しました: {str(e)}'}
            
    except Exception as e:
        return {'status': 'error', 'message': f'予期せぬエラーが発生しました: {str(e)}'}

# データベース初期化
with app.app_context():
    if not os.path.exists(DB_FILE):
        init_db()

# アプリケーション終了時にデータベース接続を閉じる
app.teardown_appcontext(close_db)

# ルートURL
@app.route('/')
def index():
    # 認証状態を確認
    is_authenticated = False
    token_path = 'token.pickle'
    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
                # トークンの有効期限を確認
                if creds and creds.valid:
                    is_authenticated = True
                elif creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        with open(token_path, 'wb') as token:
                            pickle.dump(creds, token)
                        is_authenticated = True
                    except Exception as refresh_error:
                        app.logger.error(f"トークンの更新に失敗しました: {refresh_error}")
                        os.unlink(token_path)
        except Exception as e:
            app.logger.error(f"認証情報の読み込みエラー: {e}")
            # 無効な認証情報は削除
            if os.path.exists(token_path):
                os.unlink(token_path)
    
    return render_template('index.html', is_authenticated=is_authenticated)

# アップロードを許可する拡張子
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 静的ファイルのルーティング
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# ファイルアップロードページの表示
@app.route('/upload')
def upload_page():
    # 認証状態を確認
    is_authenticated = os.path.exists('token.pickle')
    return render_template('upload.html', is_authenticated=is_authenticated)

# ファイルアップロード用のAPIエンドポイント
@app.route('/api/upload', methods=['POST'])
def upload_file():
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'status': 'error', 'message': '許可されていないファイル形式です'}), 400
    
    try:
        filename = secure_filename(file.filename)
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # ファイルサイズの検証（16MB制限）
        if os.path.getsize(filepath) > app.config['MAX_CONTENT_LENGTH']:
            os.remove(filepath)  # 制限を超えたファイルは削除
            return jsonify({
                'status': 'error',
                'message': f'ファイルサイズが大きすぎます。最大{app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)}MBまでのファイルをアップロードできます。'
            }), 400
        
        analysis_result = analyze_resume(filepath)
        
        if analysis_result.get('status') == 'error':
            return jsonify({
                'status': 'error',
                'message': analysis_result.get('message', 'ファイルの解析中にエラーが発生しました')
            }), 400
            
        # スキル情報をセッションに保存
        if 'skills' in analysis_result:
            session['user_skills'] = analysis_result['skills']
        
        response = jsonify({
            'status': 'success',
            'message': 'ファイルのアップロードと解析が完了しました',
            'filename': filename,
            'skills': analysis_result.get('skills', []),
            'extracted_text': analysis_result.get('extracted_text', '')
        })
        
        return response
        
    except Exception as e:
        # エラーが発生した場合、アップロードされたファイルを削除
        if 'filepath' in locals() and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
                
        return jsonify({
            'status': 'error',
            'message': f'ファイルの処理中にエラーが発生しました: {str(e)}'
        }), 500

# Gmail検索用のエンドポイント
@app.route('/search_gmail', methods=['POST'])
def search_gmail():
    # リクエストから検索クエリを取得
    data = request.get_json()
    query = data.get('query', '')
    max_results = data.get('maxResults', 10)
    
    # Gmailサービスを取得
    service = get_gmail_service()
    if not service:
        return jsonify({'status': 'error', 'message': 'Gmailサービスに接続できません。認証が必要です。'}), 401
    
    try:
        # 現在の日付と2日前の日付を取得
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        two_days_ago = now - timedelta(days=2)
        
        # 日付をRFC 2822形式に変換
        date_query = f'after:{two_days_ago.strftime("%Y/%m/%d")}'
        
        # 検索クエリを構築（sales@artwize.co.jp宛てで、過去2日間、添付ファイルなし）
        full_query = f'to:sales@artwize.co.jp {date_query} {query} has:nouserlabels -has:attachment'
        
        # メッセージを検索
        results = service.users().messages().list(
            userId='me',
            q=full_query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        # 各メッセージの詳細を取得
        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date', 'To']
                ).execute()
                
                # メタデータから必要な情報を抽出
                headers = {}
                for header in message.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 添付ファイルの有無を確認（より確実な方法）
                has_attachments = False
                
                # 1. メッセージの添付ファイルを直接確認
                if 'filename' in message.get('payload', {}) and message['payload']['filename']:
                    has_attachments = True
                
                # 2. パーツを再帰的にチェック
                def check_parts(part):
                    if not part:
                        return False
                        
                    # 添付ファイルとして扱うMIMEタイプ
                    attachment_mime_types = {
                        'application/octet-stream',
                        'application/pdf',
                        'application/msword',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        'application/vnd.ms-powerpoint',
                        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                        'application/zip',
                        'application/x-rar-compressed',
                        'application/x-7z-compressed',
                        'application/x-tar',
                        'application/x-gzip'
                    }
                    
                    # ファイル名がある場合、または添付ファイルとして扱うMIMEタイプの場合
                    if (part.get('filename') and part['filename']) or \
                       (part.get('mimeType') and part['mimeType'] in attachment_mime_types):
                        return True
                        
                    # ネストされたパーツを確認
                    for sub_part in part.get('parts', []):
                        if check_parts(sub_part):
                            return True
                            
                    return False
                
                # メッセージの全パーツをチェック
                if not has_attachments and 'parts' in message.get('payload', {}):
                    has_attachments = check_parts(message['payload'])
                
                # 添付ファイルがある場合はスキップ
                if has_attachments:
                    print(f"添付ファイルがあるメールをスキップしました: {message['id']}")
                    print(f"件名: {headers.get('subject', '(件名なし)')}")
                    print(f"送信者: {headers.get('from', '送信者不明')}")
                    print("-" * 50)
                    continue
                
                # 受信日時をフォーマット
                email_date = headers.get('date', '')
                try:
                    from email.utils import parsedate_to_datetime
                    email_date = parsedate_to_datetime(email_date).strftime('%Y-%m-%d %H:%M:%S')
                except (TypeError, ValueError):
                    pass
                
                email_data = {
                    'id': message['id'],
                    'subject': headers.get('subject', '(件名なし)'),
                    'from': headers.get('from', '送信者不明'),
                    'to': headers.get('to', ''),
                    'snippet': message.get('snippet', ''),
                    'date': email_date,
                    'has_attachments': has_attachments
                }
                emails.append(email_data)
                
            except Exception as e:
                print(f"メッセージの取得中にエラーが発生しました: {e}")
                continue
        
        return jsonify({
            'status': 'success',
            'emails': emails
        })
        
    except Exception as e:
        app.logger.error(f"Gmail検索中にエラーが発生しました: {e}")
        return jsonify({
            'status': 'error',
            'message': f'メールの検索中にエラーが発生しました: {str(e)}'
        }), 500

import secrets
from datetime import datetime
from functools import wraps
from flask import url_for, redirect, session, request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Gmail認証用のエンドポイント
@app.route('/gmail/auth')
def gmail_auth():
    # リファラ（元のページ）をセッションに保存
    referrer = request.referrer or url_for('index')
    session['next'] = referrer
    
    try:
        app.logger.debug("Starting Gmail authentication process")
        # リダイレクトURIを生成
        redirect_uri = url_for('gmail_auth_callback', _external=True)
        app.logger.debug(f"Using redirect_uri: {redirect_uri}")
        
        # credentials.jsonの存在を確認
        if not os.path.exists('credentials.json'):
            app.logger.error("credentials.json not found")
            return "credentials.json ファイルが見つかりません。", 500
            
        # OAuth2フローの設定
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/gmail.readonly'],
            redirect_uri=redirect_uri
        )
        
        # CSRF対策のための状態トークンを生成
        state = secrets.token_urlsafe(16)
        
        # 認証URLを生成
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='select_account'  # 常にアカウント選択を表示
        )
        
        # フローデータをセッションに保存
        session['oauth_flow'] = {
            'state': state,
            'redirect_uri': redirect_uri,
            'timestamp': datetime.now().timestamp(),
            'next': referrer  # リダイレクト先も保存
        }
        session.modified = True
        
        # 古いトークンファイルが残っている場合は削除
        token_path = 'token.pickle'
        if os.path.exists(token_path):
            try:
                os.unlink(token_path)
            except Exception as e:
                app.logger.warning(f"Failed to remove old token file: {e}")
        
        app.logger.info("Redirecting to Google OAuth URL")
        return redirect(auth_url)
        
    except Exception as e:
        app.logger.error(f"Error in gmail_auth: {str(e)}", exc_info=True)
        return f"認証エラーが発生しました: {str(e)}", 500

# Gmail認証コールバック用のエンドポイント
@app.route('/gmail/auth/callback')
def gmail_auth_callback():
    app.logger.debug("Entered gmail_auth_callback")
    
    # セッションから状態を取得
    oauth_flow = session.get('oauth_flow')
    if not oauth_flow:
        app.logger.error("OAuth flow data not found in session")
        return "セッションが無効です。最初からやり直してください。", 400
    
    # 状態の検証
    expected_state = oauth_flow.get('state')
    if not expected_state or expected_state != request.args.get('state'):
        app.logger.error(f"Invalid state parameter. Expected: {expected_state}, Got: {request.args.get('state')}")
        return "無効なリクエストです。最初からやり直してください。", 400
    
    # タイムアウトチェック（30分以内）
    if datetime.now().timestamp() - oauth_flow.get('timestamp', 0) > 1800:
        app.logger.error("OAuth flow timed out")
        session.pop('oauth_flow', None)
        session.modified = True
        return "セッションの有効期限が切れました。もう一度お試しください。", 400
    
    # エラーチェック
    if 'error' in request.args:
        error_msg = request.args.get('error_description', request.args.get('error', '不明なエラー'))
        app.logger.error(f"OAuth error: {error_msg}")
        return f"認証エラーが発生しました: {error_msg}", 400
    
    # 認証コードの確認
    if 'code' not in request.args:
        app.logger.error("No authorization code in callback")
        return "認証コードが提供されていません。", 400
    
    try:
        # フローの再構築
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/gmail.readonly'],
            state=expected_state,
            redirect_uri=oauth_flow['redirect_uri']
        )
        
        # 認証コードをトークンと交換
        try:
            flow.fetch_token(authorization_response=request.url)
        except Exception as e:
            app.logger.error(f"Error exchanging code for token: {str(e)}")
            return f"認証トークンの取得に失敗しました: {str(e)}", 500
        
        # 認証情報を取得
        credentials = flow.credentials
        if not credentials:
            app.logger.error("No credentials received from OAuth flow")
            return "認証情報が返されませんでした。", 400
            
        if not hasattr(credentials, 'valid') or not credentials.valid:
            app.logger.error(f"Invalid credentials received. Credentials: {credentials.__dict__}")
            return "無効な認証情報が返されました。", 400
            
        app.logger.debug(f"Received valid credentials. Token expires at: {getattr(credentials, 'expiry', 'Not specified')}")
        
        # トークンを安全に保存
        token_path = 'token.pickle'
        try:
            # 既存のトークンファイルをバックアップ
            backup_path = None
            if os.path.exists(token_path):
                backup_path = f"{token_path}.bak"
                os.replace(token_path, backup_path)
                
            # 新しいトークンを保存
            with open(token_path, 'wb') as token:
                pickle.dump(credentials, token)
                
            # バックアップが成功したら古いバックアップを削除
            if backup_path and os.path.exists(backup_path):
                os.unlink(backup_path)
                
            # パーミッションを制限（Unix系のみ）
            if os.name == 'posix':
                os.chmod(token_path, 0o600)
                
            app.logger.info(f"Successfully saved token to {token_path}")
            
        except Exception as e:
            # エラーが発生した場合はバックアップから復元
            if backup_path and os.path.exists(backup_path):
                try:
                    os.replace(backup_path, token_path)
                    app.logger.warning("Restored token from backup after error")
                except Exception as restore_error:
                    app.logger.error(f"Failed to restore token from backup: {str(restore_error)}")
                    
            app.logger.error(f"Error saving token: {str(e)}", exc_info=True)
            return f"認証情報の保存中にエラーが発生しました: {str(e)}", 500
        
        # 認証情報をセッションに保存
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None
        }
        
        # リダイレクト先を取得（デフォルトはトップページ）
        next_page = session.get('oauth_flow', {}).get('next', url_for('index'))
        
        # セッションをクリア
        session.pop('oauth_flow', None)
        session.pop('oauth_state', None)
        session.pop('next', None)
        session.modified = True
        
        app.logger.info(f"Successfully authenticated with Gmail API, redirecting to: {next_page}")
        return redirect(next_page)
        
    except Exception as e:
        app.logger.error(f"Error in gmail_auth_callback: {str(e)}", exc_info=True)
        # エラーが発生した場合は認証状態をクリア
        session.pop('oauth_flow', None)
        session.pop('oauth_state', None)
        session.modified = True
        return f"認証処理中にエラーが発生しました: {str(e)}", 500

# Gmail認証状態確認用のエンドポイント
@app.route('/api/gmail/auth/status')
def gmail_auth_status():
    """Gmail認証状態を確認するエンドポイント（旧バージョン互換用）"""
    return auth_status()

# 認証状態確認用のエンドポイント
@app.route('/api/auth/status')
def auth_status():
    """認証状態を確認するエンドポイント"""
    if 'credentials' not in session:
        return jsonify({'authenticated': False, 'message': 'Not authenticated'})
    
    try:
        credentials = Credentials(**session['credentials'])
        if not credentials.valid:
            return jsonify({'authenticated': False, 'message': 'Token expired'})
        return jsonify({'authenticated': True, 'message': 'Authenticated'})
    except Exception as e:
        return jsonify({'authenticated': False, 'message': str(e)})

def get_date_days_ago(days):
    """指定日数前の日付をYYYY/MM/DD形式で返す"""
    from datetime import datetime, timedelta
    date = datetime.now() - timedelta(days=days)
    return date.strftime('%Y/%m/%d')

def search_gmail_emails(service, skills, normalized_skills):
    """Gmailからメールを検索して案件情報を返す"""
    try:
        # 検索クエリを作成
        query_parts = [f'to:sales@artwize.co.jp', f'after:{get_date_days_ago(2)}']
        if skills:
            query_parts.append(f"({' OR '.join(skills)})")
        
        query = ' '.join(query_parts)
        
        # メールを検索
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=10
        ).execute()
        
        messages = results.get('messages', [])
        projects = []
        
        for msg in messages:
            try:
                # メールの詳細を取得
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['subject', 'from', 'date']
                ).execute()
                
                # メタデータから必要な情報を抽出
                headers = {}
                for header in message.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 受信日時をフォーマット
                email_date = headers.get('date', '')
                try:
                    from email.utils import parsedate_to_datetime
                    email_date = parsedate_to_datetime(email_date).strftime('%Y-%m-%d %H:%M:%S')
                except (TypeError, ValueError):
                    pass
                
                # 案件情報を作成
                project = {
                    'id': message['id'],
                    'name': headers.get('subject', '(件名なし)'),
                    'client_name': headers.get('from', '送信者不明'),
                    'date': email_date,
                    'snippet': message.get('snippet', ''),
                    'source': 'gmail'
                }
                
                # スキルマッチング情報を追加
                project['matched_skills'] = [s for s in normalized_skills if s.lower() in project['snippet'].lower()]
                project['match_count'] = len(project['matched_skills'])
                project['match_score'] = project['match_count']  # 単純にマッチ数を使用
                project['match_percentage'] = min(project['match_count'] * 20, 100)  # 1スキルあたり20%と仮定
                
                projects.append(project)
                
            except Exception as e:
                print(f"メールの処理中にエラーが発生しました: {e}")
                continue
        
        return projects
        
    except Exception as e:
        print(f"Gmail検索中にエラーが発生しました: {e}")
        raise

# スキルに基づいて案件を検索するAPI
@app.route('/api/search_projects', methods=['POST'])
def search_projects():
    try:
        data = request.get_json()
        if not data or 'skills' not in data or not data['skills']:
            return jsonify({'status': 'error', 'message': 'スキルが指定されていません'}), 400
        
        skills = data['skills']
        if not isinstance(skills, list):
            return jsonify({'status': 'error', 'message': '無効なスキル形式です'}), 400
        
        # 空のスキルを除外して正規化
        normalized_skills = [skill.lower().strip() for skill in skills if skill.strip()]
        if not normalized_skills:
            return jsonify({'status': 'error', 'message': '有効なスキルが指定されていません'}), 400
        
        # Gmail APIからメールを検索
        service = get_gmail_service()
        if not service:
            return jsonify({
                'status': 'error',
                'message': 'Gmailサービスに接続できませんでした。認証が必要です。'
            }), 500
        
        # Gmailからメールを検索して案件を取得
        projects = search_gmail_emails(service, skills, normalized_skills)
        
        # マッチスコアでソート（降順）
        projects.sort(key=lambda x: x['match_score'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'projects': projects,
            'total': len(projects)
        })
        
    except Exception as e:
        print(f"プロジェクト検索中にエラーが発生しました: {e}")
        return jsonify({
            'status': 'error',
            'message': f'プロジェクトの検索中にエラーが発生しました: {str(e)}'
        }), 500

# スキルを保存するAPIエンドポイント
@app.route('/api/save_skills', methods=['POST'])
def save_skills():
    try:
        data = request.get_json()
        if not data or 'skills' not in data or not data['skills']:
            return jsonify({'status': 'error', 'message': 'スキルが指定されていません'}), 400
        
        engineer_id = data.get('engineerId', '1')
        skills = data['skills']
        
        if not isinstance(skills, list):
            return jsonify({'status': 'error', 'message': '無効なスキル形式です'}), 400
        
        # スキルをカンマ区切りの文字列に変換
        skills_str = ','.join(skills)
        
        # データベースに保存
        conn = get_db()
        c = conn.cursor()
        
        # エンジニアが既に存在するか確認
        c.execute('SELECT id FROM engineers WHERE id = ?', (engineer_id,))
        engineer = c.fetchone()
        
        if engineer:
            # 既存のエンジニアのスキルを更新
            c.execute('''
                UPDATE engineers 
                SET skills = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (skills_str, engineer_id))
        else:
            # 新しいエンジニアとして登録
            c.execute('''
                INSERT INTO engineers (id, skills, created_at, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (engineer_id, skills_str))
        
        conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'スキルが正常に保存されました',
            'engineer_id': engineer_id,
            'skills_count': len(skills)
        })
        
    except Exception as e:
        print(f'Error saving skills: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'スキルの保存中にエラーが発生しました',
            'error': str(e)
        }), 500

def get_recent_sales_emails(service, days=2, max_results=10):
    """指定された日数分のメールを取得する"""
    from datetime import datetime, timedelta
    
    # 日付の計算
    after_date = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
    
    # 検索クエリの構築
    query_parts = [
        f'after:{after_date}',
        '(from:sales@artwize.co.jp OR to:sales@artwize.co.jp OR cc:sales@artwize.co.jp)',
        '(案件 OR 求人 OR 募集 OR プロジェクト)'
    ]
    
    query = ' '.join(query_parts)
    
    try:
        # メールIDの取得
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        
        # メールの詳細を取得
        detailed_messages = []
        for msg in messages:
            try:
                msg_detail = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                detailed_messages.append(msg_detail)
            except Exception as e:
                print(f"Error getting message details: {e}")
                continue
                
        return detailed_messages
        
    except Exception as e:
        print(f"Error getting messages: {e}")
        return []

def extract_email_info(service, msg_id):
    """メールの詳細情報を取得"""
    try:
        message = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='raw'
        ).execute()
        
        msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))
        mime_msg = message_from_bytes(msg_str)
        
        subject = mime_msg.get('subject', '件名なし')
        sender = mime_msg.get('from', '差出人不明')
        date = mime_msg.get('date', '')
        body = ''
        
        # 日付をフォーマット
        try:
            if date:
                date_obj = parsedate_to_datetime(date)
                date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
        except:
            date = '日付不明'
        
        # 本文の取得
        if mime_msg.is_multipart():
            for part in mime_msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    body = part.get_payload(decode=True).decode(errors='ignore')
                    break
        else:
            body = mime_msg.get_payload(decode=True).decode(errors='ignore')
            
        return {
            'id': msg_id,
            'subject': subject,
            'from': sender,
            'date': date,
            'body': body
        }
    except Exception as e:
        print(f"Error extracting email info: {e}")
        return None

def extract_skills_from_email(body: str) -> List[str]:
    """メール本文からスキルを抽出"""
    skill_patterns = [
        r'(?:スキル|技術|経験|経験者|経験年数)[：:]\s*([^\n\r]+)',
        r'(?:言語|フレームワーク|ツール)[：:]\s*([^\n\r]+)',
        r'(?:必須|歓迎)スキル[：:]\s*([^\n\r]+)'
    ]
    
    skills = set()
    for pattern in skill_patterns:
        matches = re.findall(pattern, body, re.IGNORECASE)
        for match in matches:
            skills.update(re.split(r'[,、・/]', match))
    
    return [skill.strip() for skill in skills if skill.strip()]

def find_matching_engineers(required_skills: List[str]) -> List[Dict[str, Any]]:
    """必要なスキルに基づいてマッチするエンジニアを検索
    
    Args:
        required_skills: 必要なスキルのリスト
        
    Returns:
        マッチしたエンジニアのリスト（完全一致を優先し、スコア順にソート）
    """
    if not required_skills:
        return []
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 各スキルに対して完全一致と部分一致で検索
    skill_conditions = []
    params = []
    
    # 各スキルに対して完全一致と部分一致の条件を追加
    for skill in required_skills:
        skill_conditions.append("""
            EXISTS (
                SELECT 1 FROM skills s 
                WHERE s.engineer_id = e.id 
                AND (s.skill = ? OR s.skill LIKE ?)
            )
        """)
        params.extend([skill, f"%{skill}%"])
    
    query = f"""
    SELECT 
        e.*, 
        GROUP_CONCAT(DISTINCT s.skill) as skills,
        COUNT(DISTINCT CASE WHEN s.skill IN ({','.join(['?']*len(required_skills))}) THEN s.skill END) as exact_matches,
        COUNT(DISTINCT s.skill) as total_matches
    FROM engineers e
    JOIN skills s ON e.id = s.engineer_id
    WHERE {' OR '.join(skill_conditions)}
    GROUP BY e.id
    HAVING exact_matches > 0
    ORDER BY exact_matches DESC, total_matches DESC
    LIMIT 10
    """
    
    # クエリパラメータを準備（完全一致用のスキルリスト + 各スキルの完全一致/部分一致パラメータ）
    query_params = required_skills + params
    cursor.execute(query, query_params)
    
    return [dict(row) for row in cursor.fetchall()]

@app.route('/api/emails', methods=['GET'])
def get_emails():
    """Gmailからメール一覧を取得する"""
    if 'credentials' not in session:
        return jsonify({'error': 'Gmail認証が必要です'}), 401
    
    try:
        credentials = Credentials(**session['credentials'])
        service = build('gmail', 'v1', credentials=credentials)
        
        # 過去7日間のメールを取得
        emails = get_recent_sales_emails(service, days=7, max_results=50)
        email_list = []
        
        for email in emails:
            # メールの基本情報のみを取得（本文は取得しない）
            msg = service.users().messages().get(userId='me', id=email['id'], format='metadata', metadataHeaders=['subject', 'from', 'date']).execute()
            
            # メタデータから情報を抽出
            headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
            
            email_info = {
                'id': email['id'],
                'subject': headers.get('subject', '(件名なし)'),
                'from': headers.get('from', '差出人不明'),
                'date': headers.get('date', '日付不明'),
                'snippet': msg.get('snippet', '')
            }
            
            email_list.append(email_info)
        
        return jsonify({
            'status': 'success',
            'emails': email_list[:20]  # 最大20件に制限
        })
        
    except Exception as e:
        print(f'Error in get_emails: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/emails/<email_id>', methods=['GET'])
def get_email_detail(email_id):
    """特定のメールの詳細を取得する"""
    if 'credentials' not in session:
        return jsonify({'error': 'Gmail認証が必要です'}), 401
    
    try:
        credentials = Credentials(**session['credentials'])
        service = build('gmail', 'v1', credentials=credentials)
        
        # メールの詳細を取得
        email_info = extract_email_info(service, email_id)
        
        # メール本文からスキルを抽出
        required_skills = extract_skills_from_email(email_info['body'])
        
        # スキルに基づいてマッチするエンジニアを検索
        matched_engineers = find_matching_engineers(required_skills) if required_skills else []
        
        # スキルに基づいてマッチする案件を検索
        matched_projects = []
        if required_skills:
            # データベースから案件を検索
            conn = get_db()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # スキルに基づいて案件を検索
            placeholders = ','.join(['?'] * len(required_skills))
            query = f"""
            SELECT DISTINCT p.*
            FROM projects p
            JOIN project_requirements pr ON p.id = pr.project_id
            WHERE pr.skill IN ({placeholders})
            GROUP BY p.id
            ORDER BY COUNT(DISTINCT pr.skill) DESC
            LIMIT 5
            """
            
            c.execute(query, required_skills)
            matched_projects = [dict(row) for row in c.fetchall()]
        
        return jsonify({
            'status': 'success',
            'email': {
                'subject': email_info['subject'],
                'from': email_info['from'],
                'date': email_info['date'],
                'body': email_info['body']
            },
            'extracted_skills': required_skills,
            'matched_engineers': matched_engineers,
            'matched_projects': matched_projects
        })
        
    except Exception as e:
        print(f'Error in get_email_detail: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 既存のmatch_projects関数はそのまま残す
@app.route('/api/match_projects', methods=['GET'])
def match_projects():
    """スキルに基づいてエンジニアと案件をマッチングする"""
    if 'credentials' not in session:
        return jsonify({'error': 'Gmail認証が必要です'}), 401
    
    try:
        credentials = Credentials(**session['credentials'])
        service = build('gmail', 'v1', credentials=credentials)
        
        # 過去2日間のメールを取得
        emails = get_recent_sales_emails(service, days=2)
        results = []
        
        for email in emails:
            # メールの詳細を取得
            email_info = extract_email_info(service, email['id'])
            
            # メール本文からスキルを抽出
            required_skills = extract_skills_from_email(email_info['body'])
            if not required_skills:
                continue
                
            # スキルに基づいてマッチするエンジニアを検索
            matched_engineers = find_matching_engineers(required_skills)
            
            # 結果に追加
            results.append({
                'email_id': email['id'],
                'email': {
                    'subject': email_info['subject'],
                    'from': email_info['from'],
                    'date': email_info['date'],
                    'snippet': email_info['body'][:200] + '...' if len(email_info['body']) > 200 else email_info['body']
                },
                'required_skills': required_skills,
                'matched_engineers': matched_engineers
            })
        
        return jsonify({
            'status': 'success',
            'matches': results
        })
        
    except Exception as e:
        print(f'Error in match_projects: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        
        # 過去2日間のメールを取得
        emails = get_recent_sales_emails(service, days=2)
        results = []
        
        for email in emails:
            email_info = extract_email_info(service, email['id'])
            if not email_info:
                continue
                
            # メールからスキルを抽出
            required_skills = extract_skills_from_email(email_info['body'])
            
            # マッチするエンジニアを検索
            matched_engineers = find_matching_engineers(required_skills)
            
            if matched_engineers:
                results.append({
                    'email': email_info,
                    'required_skills': required_skills,
                    'matched_engineers': matched_engineers
                })
        
        return jsonify({
            'status': 'success',
            'matches': results
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/matches')
def view_matches():
    """マッチング結果を表示するページ"""
    if 'credentials' not in session:
        return redirect(url_for('gmail_auth'))
    return render_template('matches.html')

@app.route('/api/projects', methods=['GET'])
def get_projects_api():
    """
    Gmailから案件情報を取得して検索・並び替えができるAPIエンドポイント
    
    クエリパラメータ:
    - q: 検索クエリ（件名・本文から検索）
    - sort: ソート順（date, salary, relevance）
    - min_salary: 最低給与（万円）
    - max_salary: 最高給与（万円）
    - skills: カンマ区切りのスキルリスト（例: Python,JavaScript,React）
    - days: 何日前までのメールを取得するか（デフォルト: 30日）
    """
    try:
        # クエリパラメータを取得
        search_query = request.args.get('q', '').lower()
        sort_by = request.args.get('sort', 'date')
        min_salary = request.args.get('min_salary')
        max_salary = request.args.get('max_salary')
        skills_param = request.args.get('skills', '')
        days = int(request.args.get('days', 30))
        
        # スキルフィルターを処理
        skills_filter = [s.strip().upper() for s in skills_param.split(',')] if skills_param else []
        
        # Gmail APIを使用してメールを取得
        if 'credentials' not in session:
            return jsonify({'error': 'Gmail認証が必要です'}), 401
            
        credentials = Credentials(**session['credentials'])
        service = build('gmail', 'v1', credentials=credentials)
        
        # メールを取得
        emails = get_recent_sales_emails(service, days=days, max_results=50)
        
        projects = []
        
        for email in emails:
            try:
                # メタデータから情報を抽出
                headers = {}
                for header in email.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 件名を取得
                subject = headers.get('subject', '（件名なし）')
                
                # メール本文は取得済みの場合はそのまま使用、なければ空文字列
                body = email.get('snippet', '')
                
                # 日付を取得してフォーマット
                date_str = headers.get('date', '')
                try:
                    from email.utils import parsedate_to_datetime
                    parsed_date = parsedate_to_datetime(date_str)
                    formatted_date = parsedatedate.isoformat()
                    timestamp = parsed_date.timestamp()
                except (TypeError, ValueError):
                    # 日付のパースに失敗した場合は現在時刻を使用
                    parsed_date = datetime.utcnow()
                    formatted_date = parsed_date.isoformat()
                    timestamp = parsed_date.timestamp()
                    
                # 送信者情報を取得
                from_email = headers.get('from', '送信者不明')
                
                # スニペット（本文の一部）を取得
                snippet = email.get('snippet', '')[:200] + '...' if len(email.get('snippet', '')) > 200 else email.get('snippet', '')
                
                # 給与情報を抽出（正規表現で数値を検索）
                salary = 0
                salary_match = re.search(r'(給与|年収|報酬|単価)[:：]?\s*([\d,]+)[\s-~]*([\d,]*)', subject + ' ' + body)
                if salary_match:
                    try:
                        # 数値を抽出して平均を計算
                        min_sal = int(salary_match.group(2).replace(',', ''))
                        max_sal = int(salary_match.group(3).replace(',', '')) if salary_match.group(3) else min_sal
                        salary = (min_sal + max_sal) // 2
                    except (ValueError, AttributeError):
                        pass
                
                # 給与フィルターを適用
                if min_salary and salary < int(min_salary):
                    continue
                if max_salary and salary > int(max_salary) and int(max_salary) > 0:  # max_salary=0は無視
                    continue
                
                # 勤務地を抽出
                location_match = re.search(r'勤務地[：:]([^\n]+)', body)
                location = location_match.group(1).strip() if location_match else '未記載'
                
                # スキルを抽出
                skills_match = re.findall(r'[A-Za-z0-9+#.]+', (subject + ' ' + body).upper())
                valid_skills = list(set([s for s in skills_match if s in SKILL_KEYWORDS]))
                
                # スキルフィルターが指定されている場合はマッチングを確認
                if skills_filter and not any(skill in valid_skills for skill in skills_filter):
                    continue
                    
                # プロジェクトオブジェクトを作成
                project = {
                    'id': email['id'],
                    'threadId': email.get('threadId', ''),
                    'subject': subject,
                    'snippet': snippet,
                    'date': formatted_date,
                    'timestamp': timestamp,
                    'from': from_email,
                    'salary': salary,
                    'location': location,
                    'body': body[:500] + '...' if len(body) > 500 else body,
                    'skills': valid_skills,
                    'match_count': len(valid_skills)
                }
                
                projects.append(project)
                
            except Exception as e:
                print(f"Error processing email {email.get('id', 'unknown')}: {str(e)}")
                continue
        
        # ソート処理
        if sort_by == 'date':
            projects.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        elif sort_by == 'salary':
            projects.sort(key=lambda x: x.get('salary', 0), reverse=True)
        elif sort_by == 'relevance':
            # 関連性でソート（マッチしたスキル数が多い順）
            projects.sort(key=lambda x: x.get('match_count', 0), reverse=True)
        
        # ソート処理
        if sort_by == 'date':
            projects.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        elif sort_by == 'salary':
            projects.sort(key=lambda x: x.get('salary', 0), reverse=True)
        elif sort_by == 'relevance':
            # 関連度でソート（検索クエリとの一致度）
            def relevance_score(p):
                if not search_query:
                    return 0
                    
                score = 0
                query = search_query.lower()
                
                # 件名でのマッチング（重み付け高め）
                if 'subject' in p and query in p['subject'].lower():
                    score += 3
                
                # 本文でのマッチング
                if 'body' in p and query in p['body'].lower():
                    score += 1
                    
                # スキルでのマッチング（完全一致）
                if 'skills' in p and any(query == skill.lower() for skill in p['skills']):
                    score += 2
                    
                return -score  # 降順ソートのため負の値を返す
            
            # 関連度スコアでソート
            projects.sort(key=relevance_score)
            
            # 関連度が同じ場合は日付の新しい順にソート
            projects.sort(key=lambda x: (relevance_score(x), x.get('timestamp', 0)), reverse=True)
        
        return jsonify({
            'status': 'success',
            'data': projects,
            'total': len(projects)
        })
        
    except Exception as e:
        app.logger.error(f'Error in get_projects_api: {str(e)}', exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'プロジェクトの取得中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/projects', methods=['GET'])
@login_required
def get_projects():
    """
    プロジェクト一覧ページを表示する
    """
    # 認証情報を取得（login_requiredデコレータで認証済みであることが保証されている）
    credentials = Credentials(**session['credentials'])
    
    conn = None
    try:
        conn = get_db()
        c = conn.cursor()
        
        # プロジェクトと必要なスキルを取得
        c.execute('''
            SELECT p.*, 
                   GROUP_CONCAT(DISTINCT pr.skill) as required_skill_names
            FROM projects p
            LEFT JOIN project_requirements pr ON p.id = pr.project_id
            GROUP BY p.id
        ''')
        
        projects = []
        for row in c.fetchall():
            project = dict(row)
            # 必要なスキル名がNoneの場合は空の文字列に変換
            if not project.get('required_skill_names'):
                project['required_skill_names'] = ''
            projects.append(project)
        
        # テンプレートにプロジェクトデータを渡してレンダリング
        return render_template('projects.html', projects=projects)
        
    except Exception as e:
        app.logger.error(f'Error fetching projects: {str(e)}')
        # エラーが発生した場合は空のリストを渡してテンプレートをレンダリング
        return render_template('projects.html', projects=[])
        
    finally:
        if conn:
            conn.close()

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
    """Gmail APIサービスを取得する"""
    # セッションから認証情報を取得
    if 'credentials' not in session:
        app.logger.debug("No credentials in session for get_gmail_service")
        return None
    
    try:
        # セッションから認証情報を復元
        creds_dict = session['credentials'].copy()  # セッションを変更しないようにコピー
        
        # 有効期限をdatetimeオブジェクトに変換
        if 'expiry' in creds_dict and isinstance(creds_dict['expiry'], str):
            creds_dict['expiry'] = datetime.fromisoformat(creds_dict['expiry'])
        
        # 認証情報オブジェクトを作成
        creds = Credentials(
            token=creds_dict.get('token'),
            refresh_token=creds_dict.get('refresh_token'),
            token_uri=creds_dict.get('token_uri'),
            client_id=creds_dict.get('client_id'),
            client_secret=creds_dict.get('client_secret'),
            scopes=creds_dict.get('scopes'),
            expiry=creds_dict.get('expiry')
        )
        
        # トークンの有効期限を確認し、必要に応じて更新
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # 更新した認証情報をセッションに保存
                session['credentials'] = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None
                }
                session.modified = True
                app.logger.info("Successfully refreshed token in get_gmail_service")
            except Exception as refresh_error:
                app.logger.error(f"トークンの更新に失敗しました: {refresh_error}")
                session.pop('credentials', None)
                return None
        
        # 有効な認証情報がない場合はNoneを返す
        if not creds or not creds.valid:
            return None
        
        # Gmail APIのサービスを構築して返す
        service = build('gmail', 'v1', 
                      credentials=creds,
                      cache_discovery=False)  # キャッシュの無効化
        return service
        
    except Exception as e:
        app.logger.error(f"Gmailサービスの作成中にエラーが発生しました: {e}", exc_info=True)
        session.pop('credentials', None)
        return None

if __name__ == '__main__':
    # アップロードフォルダが存在するか確認
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # テンプレートフォルダが存在するか確認
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 開発用にデバッグモードで起動
    app.run(debug=True, port=5000, host='0.0.0.0')
