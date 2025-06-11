import os
import re
from typing import Dict, List, Optional
from pathlib import Path
import PyPDF2

# 開発環境用の設定（本番環境では削除またはコメントアウト）
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, jsonify, request, g, send_from_directory, url_for, render_template, redirect, send_file, session, flash, make_response
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
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.config['SECRET_KEY'] = 'your-secret-key-here'  # セッション用のシークレットキー

# CORSとCSPの設定
CORS(app)  # CORSを有効化

# レスポンスヘッダーにCSPを追加するミドルウェア
@app.after_request
def add_security_headers(response):
    # 開発環境では 'unsafe-inline' と 'unsafe-eval' を許可
    # 本番環境では、これらの設定を厳格化することを推奨
    csp_parts = [
        # デフォルトポリシー（明示的に指定されていないディレクティブのフォールバック）
        "default-src 'self';",
        
        # JavaScriptの読み込み元を制限
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://www.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;",
        
        # スタイルシートの読み込み元を制限
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;",
        "style-src-elem 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/;",
        
        # 画像の読み込み元を制限
        "img-src 'self' data: https:;",
        
        # フォントの読み込み元を制限
        "font-src 'self' data: https: https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;",
        
        # 接続先を制限（XHR、WebSocketなど）
        "connect-src 'self' http://localhost:5000 https://www.googleapis.com https://accounts.google.com https://*.googleapis.com;",
        
        # iframeの埋め込み元を制限
        "frame-src 'self' https://accounts.google.com;",
        
        # プラグインの実行を禁止
        "object-src 'none';",
        
        # ベースURIを制限
        "base-uri 'self';",
        
        # フォームの送信先を制限
        "form-action 'self' http://localhost:5000;",
        
        # フレームの埋め込みを制限
        "frame-ancestors 'self';",
        
        # Web Workerの読み込み元を制限
        "worker-src 'self' blob:;",
        
        # メディアファイルの読み込み元を制限
        "media-src 'self' data: blob:;",
        
        # マニフェストファイルの読み込み元を制限
        "manifest-src 'self';",
        
        # インラインスタイルの許可（必要に応じて）
        "style-src-attr 'unsafe-inline';",
        
        # インラインスクリプトのハッシュまたはnonceを強制（後で実装）
        # "require-trusted-types-for 'script';",
        
        # 信頼できるタイプを制限（後で実装）
        # "trusted-types 'none';",
        
        # アップグレード安全なリクエストを強制
        "upgrade-insecure-requests;"
    ]
    
    csp = ' '.join(csp_parts).replace('\n', ' ').strip()
    
    # セキュリティヘッダーを設定
    response.headers['Content-Security-Policy'] = csp
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    # 開発環境でのみ許可するヘッダー
    if app.debug:
        response.headers['X-Content-Security-Policy'] = csp  # IE用
        response.headers['X-WebKit-CSP'] = csp  # 古いWebKit用
    
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
    is_authenticated = os.path.exists('token.pickle')
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
    
    if not query:
        return jsonify({'status': 'error', 'message': '検索クエリが指定されていません'}), 400
    
    # Gmailサービスを取得
    service = get_gmail_service()
    if not service:
        return jsonify({'status': 'error', 'message': 'Gmailサービスに接続できません。認証が必要です。'}), 401
    
    try:
        # メッセージを検索
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=10  # 最大10件のメールを取得
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        # 各メッセージの詳細を取得
        for msg in messages:
            message = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            
            # メタデータから必要な情報を抽出
            headers = {}
            for header in message.get('payload', {}).get('headers', []):
                headers[header['name'].lower()] = header['value']
            
            email_data = {
                'id': message['id'],
                'subject': headers.get('subject', '(件名なし)'),
                'from': headers.get('from', '送信者不明'),
                'snippet': message.get('snippet', ''),
                'date': headers.get('date', '')
            }
            emails.append(email_data)
        
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

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

# Gmail認証用のエンドポイント
@app.route('/gmail/auth')
def gmail_auth():
    # OAuth2フローの設定
    flow = Flow.from_client_secrets_file(
        'credentials.json',  # ダウンロードしたOAuth2クライアントIDのJSONファイル
        scopes=['https://www.googleapis.com/auth/gmail.readonly'],
        redirect_uri=url_for('gmail_auth_callback', _external=True)
    )
    
    # 認証URLを生成してリダイレクト
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # セッションに状態を保存
    session['state'] = state
    
    return redirect(authorization_url)

# Gmail認証コールバック用のエンドポイント
@app.route('/gmail/auth/callback')
def gmail_auth_callback():
    state = session.get('state')
    
    if not state:
        return jsonify({'status': 'error', 'message': 'State parameter not found in session'}), 400
    
    # フローの再構築
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=['https://www.googleapis.com/auth/gmail.readonly'],
        state=state,
        redirect_uri=url_for('gmail_auth_callback', _external=True)
    )
    
    # 認証コードを取得
    flow.fetch_token(authorization_response=request.url)
    
    # 認証情報を取得
    credentials = flow.credentials
    
    # トークンを保存
    with open('token.pickle', 'wb') as token:
        pickle.dump(credentials, token)
    
    return redirect(url_for('index'))

# Gmail認証状態確認用のエンドポイント
@app.route('/api/gmail/auth/status')
def gmail_auth_status():
    if 'credentials' not in session:
        return jsonify({'authenticated': False})
    
    credentials = Credentials(**session['credentials'])
    return jsonify({
        'authenticated': True,
        'email': credentials.client_id  # 実際には適切なメールアドレスを取得する必要あり
    })

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
        
        conn = get_db()
        c = conn.cursor()
        
        # スキルに基づいて案件を検索
        query = '''
        SELECT p.*, 
               COUNT(DISTINCT pr.skill) as match_count,
               GROUP_CONCAT(DISTINCT pr.skill) as required_skills_list
        FROM projects p
        LEFT JOIN project_requirements pr ON p.id = pr.project_id
        WHERE pr.skill IN ({})
        GROUP BY p.id
        HAVING match_count > 0
        ORDER BY match_count DESC
        LIMIT 20
        '''.format(','.join(['?'] * len(skills)))
        
        c.execute(query, skills)
        projects = [dict(row) for row in c.fetchall()]
        
        # マッチしたスキルをハイライト
        for project in projects:
            required_skills = project['required_skills_list'].split(',') if project['required_skills_list'] else []
            matched_skills = [skill for skill in skills if skill in required_skills]
            project['matched_skills'] = matched_skills
            project['match_percentage'] = int((len(matched_skills) / len(required_skills)) * 100) if required_skills else 0
            
            # 不要なフィールドを削除
            if 'required_skills_list' in project:
                del project['required_skills_list']
        
        return jsonify({
            'status': 'success',
            'projects': projects
        })
        
    except Exception as e:
        print(f'Error searching projects: {str(e)}')
        return jsonify({'status': 'error', 'message': '案件の検索中にエラーが発生しました'}), 500

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
    
    # セッション用の秘密鍵を設定
    app.secret_key = os.urandom(24)
    
    # アプリケーションを実行
    app.run(debug=True, port=5000, host='0.0.0.0')
