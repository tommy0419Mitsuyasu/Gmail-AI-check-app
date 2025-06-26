import os
import re
import json
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import PyPDF2
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv  # 環境変数の読み込み用
from skill_extractor import SkillExtractor

# スキル抽出器を初期化（外部スキルAPIを有効にするかどうかを環境変数から読み込む）
skill_extractor = SkillExtractor(enable_external_skills=os.getenv('ENABLE_EXTERNAL_SKILL_API', 'false').lower() == 'true')

from skill_matcher import SkillMatcher  # SkillMatcher クラスをインポート
import skill_matcher
from skill_matcher_enhanced import enhance_skill_matching  # 新しいマッチング機能をインポート

# 環境変数の読み込み
load_dotenv()

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
from urllib.parse import quote

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
        script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://unpkg.com https://cdnjs.cloudflare.com;
        style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com;
        img-src 'self' data: https: http:;
        font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;
        connect-src 'self' http://localhost:5000 https://api.gmail.com https://www.googleapis.com;
        frame-ancestors 'self';
        frame-src 'self' https://accounts.google.com;
    """.replace('\n', ' ').replace('  ', '').strip()
    
    response.headers['Content-Security-Policy'] = csp_policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=()'
    
    return response

# スキルマッチャーを初期化
skill_matcher = SkillMatcher()

# スキルマッピング（互換性のため残す）
SKILL_KEYWORDS = list(skill_matcher.skill_normalization_map.keys()) + [
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

from skill_extractor import SkillExtractor

def analyze_resume(text: str) -> Dict[str, Any]:
    """
    レジュメを分析してスキルを抽出する
    
    Args:
        text: レジュメのテキスト
        
    Returns:
        分析結果の辞書
        {
            'skills': {
                'カテゴリ名': [
                    {
                        'name': 'スキル名',
                        'importance': 0.0-1.0の重要度スコア,
                        'experience': 経験年数（あれば）,
                        'context': 'スキルが検出された文脈',
                        'categories': ['関連カテゴリ1', '関連カテゴリ2'],
                        'related_skills': ['関連スキル1', '関連スキル2']
                    },
                    ...
                ],
                ...
            },
            'summary': {
                'total_skills': 総スキル数,
                'categories': カテゴリ数,
                'top_skills': [
                    {'name': 'スキル名', 'importance': 重要度},
                    ...
                ]
            },
            'status': 'success|error',
            'error': 'エラーメッセージ（エラー時のみ）'
        }
    """
    if not text:
        return {
            "status": "error",
            "error": "テキストが空です"
        }
    
    try:
        # スキル抽出
        skills = extract_skills(text)
        
        # サマリー情報を生成
        total_skills = sum(len(skills[cat]) for cat in skills)
        category_count = len(skills)
        
        # トップスキルを抽出（重要度順に最大5つ）
        all_skills = []
        for category, skill_list in skills.items():
            for skill in skill_list:
                all_skills.append({
                    'name': skill['name'],
                    'importance': skill.get('importance', 0),
                    'category': category
                })
        
        # 重要度でソート
        top_skills = sorted(all_skills, key=lambda x: x['importance'], reverse=True)[:5]
        
        return {
            "skills": skills,
            "summary": {
                "total_skills": total_skills,
                "categories": category_count,
                "top_skills": top_skills
            },
            "status": "success"
        }
        
    except Exception as e:
        error_msg = f"レジュメ分析中にエラーが発生しました: {str(e)}"
        print(error_msg)
        return {
            "status": "error",
            "error": error_msg
        }

def extract_skills(text: str) -> Dict[str, List[Dict]]:
    """
    テキストからスキルを抽出する
    
    Args:
        text: 抽出対象のテキスト
        
    Returns:
        カテゴリ別のスキル情報を含む辞書
        {
            'カテゴリ名': [
                {
                    'name': 'スキル名',
                    'importance': 0.0-1.0の重要度スコア,
                    'experience': 経験年数（あれば）,
                    'context': 'スキルが検出された文脈',
                    'categories': ['関連カテゴリ1', '関連カテゴリ2'],
                    'related_skills': ['関連スキル1', '関連スキル2']
                },
                ...
            ],
            ...
            'その他': []
        }
    """
    print("\n=== スキル抽出を開始します ===")
    print(f"入力テキスト長: {len(text)}文字")
    
    if not text:
        print("エラー: テキストが空です")
        return {}
    
    # スキル抽出モジュールの初期化
    print("スキル抽出モジュールを初期化中...")
    extractor = SkillExtractor()
    
    try:
        # スキル抽出を実行
        print("スキル抽出を実行中...")
        skills = extractor.extract_skills(text)
        
        if not skills:
            print("警告: 抽出されたスキルがありません")
            return {}
            
        print(f"抽出されたスキルカテゴリ数: {len(skills)}")
        
        # 結果をフォーマット
        print("スキル情報をフォーマット中...")
        formatted_skills = {}
        for category, skill_list in skills.items():
            print(f"カテゴリ '{category}': {len(skill_list)}スキル")
            formatted_skills[category] = []
            
            for skill in skill_list:
                try:
                    formatted_skill = {
                        'name': skill.get('name', skill.get('skill', '不明なスキル')),  # 両方のキーを確認
                        'importance': float(skill.get('importance', 0.5)),
                        'experience': skill.get('experience', skill.get('experience_years')),  # 両方のキーを確認
                        'context': skill.get('context', ''),
                        'categories': skill.get('categories', []),
                        'related_skills': skill.get('related_skills', [])
                    }
                    formatted_skills[category].append(formatted_skill)
                    print(f"  - スキル: {formatted_skill['name']}, 重要度: {formatted_skill['importance']}")
                except Exception as e:
                    print(f"スキルのフォーマット中にエラーが発生しました: {str(e)}")
                    print(f"問題のスキルデータ: {skill}")
        
        # 結果のサマリーを表示
        total_skills = sum(len(skills) for skills in formatted_skills.values())
        print(f"\n=== スキル抽出完了 ===")
        print(f"合計スキル数: {total_skills}")
        for category, skills in formatted_skills.items():
            print(f"{category}: {len(skills)}スキル")
        
        return formatted_skills
        
    except Exception as e:
        import traceback
        error_msg = f"スキル抽出中にエラーが発生しました: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {}   

def analyze_resume(file_path: str) -> Dict:
    """スキルシートを解析してスキルを抽出する"""
    print("\n=== レジュメ解析を開始します ===")
    print(f"解析対象ファイル: {file_path}")
    
    file_extension = Path(file_path).suffix.lower()
    print(f"ファイル拡張子: {file_extension}")
    
    try:
        # ファイルの存在確認
        if not os.path.exists(file_path):
            error_msg = f"エラー: ファイルが見つかりません: {file_path}"
            print(error_msg)
            return {'status': 'error', 'message': error_msg}
        
        # ファイルサイズの確認（10MB以下）
        file_size = os.path.getsize(file_path)
        print(f"ファイルサイズ: {file_size} バイト")
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            error_msg = f"エラー: ファイルサイズが大きすぎます（{file_size/1024/1024:.2f}MB > 10MB）"
            print(error_msg)
            return {'status': 'error', 'message': error_msg}
        
        # ファイルの種類に応じてテキスト抽出
        text = ""
        try:
            print(f"ファイルからテキストを抽出中...")
            if file_extension == '.pdf':
                print("PDFファイルを処理中...")
                text = extract_text_from_pdf(file_path)
            elif file_extension in ['.docx', '.doc']:
                print("Wordファイルを処理中...")
                text = extract_text_from_docx(file_path)
            else:
                error_msg = f"エラー: サポートされていないファイル形式です: {file_extension}"
                print(error_msg)
                return {'status': 'error', 'message': error_msg}
            
            # テキストが空でないか確認
            if not text or not text.strip():
                error_msg = "エラー: ファイルからテキストを抽出できませんでした"
                print(error_msg)
                return {'status': 'error', 'message': error_msg}
                
            print(f"抽出されたテキストの長さ: {len(text)} 文字")
            print("抽出されたテキストの先頭100文字:", text[:100] + ("..." if len(text) > 100 else ""))
                
        except Exception as e:
            import traceback
            error_msg = f"ファイルの解析中にエラーが発生しました: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {'status': 'error', 'message': f'ファイルの解析中にエラーが発生しました: {str(e)}'}
        
        # スキル抽出
        try:
            print("\nスキル抽出を開始します...")
            skills = extract_skills(text)
            
            if not skills:
                print("警告: スキルが1つも抽出されませんでした")
                return {
                    'status': 'success',
                    'file_type': file_extension,
                    'text_length': len(text),
                    'skills': {},
                    'extracted_text': text[:1000] + ('...' if len(text) > 1000 else '')
                }
            
            # 抽出されたスキルの統計情報を表示
            total_skills = sum(len(skills) for skills in skills.values())
            print(f"\n=== スキル抽出完了 ===")
            print(f"合計スキル数: {total_skills}")
            for category, skill_list in skills.items():
                print(f"{category}: {len(skill_list)}スキル")
            
            result = {
                'status': 'success',
                'file_type': file_extension,
                'text_length': len(text),
                'skills': skills,
                'extracted_text': text[:1000] + ('...' if len(text) > 1000 else '')  # プレビュー用に最初の1000文字を返す
            }
            
            return result
            
        except Exception as e:
            import traceback
            error_msg = f"スキル抽出中にエラーが発生しました: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {'status': 'error', 'message': f'スキル抽出中にエラーが発生しました: {str(e)}'}
            
    except Exception as e:
        import traceback
        error_msg = f"レジュメ解析中に予期せぬエラーが発生しました: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {'status': 'error', 'message': f'レジュメ解析中にエラーが発生しました: {str(e)}'}
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
    # セッションから認証状態を確認
    is_authenticated = False
    
    if 'credentials' in session:
        try:
            creds_info = session['credentials']
            creds = Credentials(
                token=creds_info['token'],
                refresh_token=creds_info.get('refresh_token'),
                token_uri=creds_info['token_uri'],
                client_id=creds_info['client_id'],
                client_secret=creds_info['client_secret'],
                scopes=creds_info['scopes']
            )
            
            # トークンの有効期限を確認
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # 新しいトークンでセッションを更新
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
                    is_authenticated = True
                except Exception as refresh_error:
                    app.logger.error(f"トークンの更新に失敗しました: {refresh_error}")
                    session.pop('credentials', None)
            else:
                is_authenticated = True
                
        except Exception as e:
            app.logger.error(f"認証情報の読み込みエラー: {e}")
            session.pop('credentials', None)
    
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
                
                # 件名と送信者を取得
                subject = headers.get('subject', '(件名なし)')
                sender = headers.get('from', '送信者不明')
                date = headers.get('date', '')
                
                # メール本文を取得
                email_body = ''
                payload = message.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                            email_body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'body' in payload and 'data' in payload['body']:
                    email_body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                
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
                    'body': email_body,
                    'source': 'gmail'
                }
                
                # スキルマッチング情報を追加（件名と本文の両方でマッチング）
                search_text = f"{project['name']} {project['snippet']} {email_body}"
                project['matched_skills'] = [s for s in normalized_skills if s.lower() in search_text.lower()]
                project['match_count'] = len(project['matched_skills'])
                project['match_score'] = project['match_count']
                project['match_percentage'] = min(project['match_count'] * 20, 100)  # 1スキルあたり20%と仮定
                
                emails.append(project)
                
            except Exception as e:
                print(f"メールの処理中にエラーが発生しました: {e}")
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
    # 既に認証済みで有効なトークンがある場合はプロジェクト一覧にリダイレクト
    if 'credentials' in session:
        try:
            creds = Credentials(
                token=session['credentials']['token'],
                refresh_token=session['credentials']['refresh_token'],
                token_uri=session['credentials']['token_uri'],
                client_id=session['credentials']['client_id'],
                client_secret=session['credentials']['client_secret'],
                scopes=session['credentials']['scopes']
            )
            
            # トークンの有効期限をチェック
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # 新しいトークンでセッションを更新
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
            
            # 既に認証済みの場合はプロジェクト一覧にリダイレクト
            app.logger.info("Already authenticated, redirecting to projects")
            return redirect(url_for('get_projects'))
            
        except Exception as e:
            app.logger.warning(f"Existing token validation failed: {str(e)}")
            # トークンが無効な場合はセッションから削除
            session.pop('credentials', None)
    
    # リファラ（元のページ）をセッションに保存
    referrer = request.referrer or url_for('get_projects')
    session['next'] = referrer
    
    try:
        app.logger.debug("Starting Gmail authentication process")
        # リダイレクトURIを明示的に指定
        redirect_uri = 'http://127.0.0.1:5000/gmail/auth/callback'
        app.logger.debug(f"Using redirect_uri: {redirect_uri}")
        
        # credentials.jsonの存在を確認
        if not os.path.exists('credentials.json'):
            app.logger.error("credentials.json not found")
            flash('認証に必要な設定ファイルが見つかりません。', 'error')
            return redirect(url_for('get_projects'))
            
        # OAuth2フローの設定
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/gmail.readonly'],
            redirect_uri=redirect_uri
        )
        
        # CSRF対策のための状態トークンを生成
        state = secrets.token_urlsafe(16)
        
        # 認証URLを生成（一度だけ承認を求める）
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # 明示的な同意を求める
        )
        
        # フローデータをセッションに保存
        session['oauth_flow'] = {
            'state': state,
            'redirect_uri': redirect_uri,
            'timestamp': datetime.now().timestamp(),
            'next': referrer
        }
        session.modified = True
        
        app.logger.info("Redirecting to Google OAuth URL")
        return redirect(auth_url)
        
    except Exception as e:
        app.logger.error(f"Error in gmail_auth: {str(e)}", exc_info=True)
        flash(f'認証の開始中にエラーが発生しました: {str(e)}', 'error')
        return redirect(session.get('next', url_for('get_projects')))

# Gmail認証コールバック用のエンドポイント
@app.route('/gmail/auth/callback')
def gmail_auth_callback():
    app.logger.debug("Entered gmail_auth_callback")
    
    # セッションから状態を取得
    oauth_flow = session.get('oauth_flow')
    if not oauth_flow:
        app.logger.error("OAuth flow data not found in session")
        flash('セッションが無効です。最初からやり直してください。', 'error')
        return redirect(url_for('get_projects'))
    
    # 状態の検証
    expected_state = oauth_flow.get('state')
    if not expected_state or expected_state != request.args.get('state'):
        app.logger.error(f"Invalid state parameter. Expected: {expected_state}, Got: {request.args.get('state')}")
        flash('無効なリクエストです。最初からやり直してください。', 'error')
        return redirect(url_for('get_projects'))
    
    # タイムアウトチェック（30分以内）
    if datetime.now().timestamp() - oauth_flow.get('timestamp', 0) > 1800:
        app.logger.error("OAuth flow timed out")
        session.pop('oauth_flow', None)
        session.modified = True
        flash('セッションの有効期限が切れました。もう一度お試しください。', 'error')
        return redirect(url_for('get_projects'))
    
    # エラーチェック
    if 'error' in request.args:
        error_msg = request.args.get('error_description', request.args.get('error', '不明なエラー'))
        app.logger.error(f"OAuth error: {error_msg}")
        flash(f'認証エラーが発生しました: {error_msg}', 'error')
        return redirect(url_for('get_projects'))
    
    # 認証コードの確認
    if 'code' not in request.args:
        app.logger.error("No authorization code in callback")
        flash('認証コードが提供されていません。', 'error')
        return redirect(url_for('get_projects'))
    
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
            flash(f'認証トークンの取得に失敗しました: {str(e)}', 'error')
            return redirect(url_for('get_projects'))
        
        # 認証情報を取得
        credentials = flow.credentials
        if not credentials:
            app.logger.error("No credentials received from OAuth flow")
            flash('認証情報が返されませんでした。', 'error')
            return redirect(url_for('get_projects'))
            
        if not hasattr(credentials, 'valid') or not credentials.valid:
            app.logger.error(f"Invalid credentials received. Credentials: {credentials.__dict__}")
            flash('無効な認証情報が返されました。', 'error')
            return redirect(url_for('get_projects'))
            
        app.logger.debug(f"Received valid credentials. Token expires at: {getattr(credentials, 'expiry', 'Not specified')}")
        
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
        session['gmail_authenticated'] = True
        session.modified = True
        
        # リダイレクト先を取得（デフォルトはプロジェクト一覧）
        next_page = oauth_flow.get('next', url_for('get_projects'))
        
        # セッションから一時データをクリア
        session.pop('oauth_flow', None)
        session.pop('oauth_state', None)
        session.pop('next', None)
        
        app.logger.info(f"Successfully authenticated with Gmail API, redirecting to: {next_page}")
        flash('Gmail認証が完了しました。', 'success')
        return redirect(next_page)
        
    except Exception as e:
        app.logger.error(f"Error in gmail_auth_callback: {str(e)}", exc_info=True)
        # エラーが発生した場合は認証状態をクリア
        session.pop('credentials', None)
        session.pop('oauth_flow', None)
        session.pop('oauth_state', None)
        session.pop('gmail_authenticated', None)
        session.modified = True
        
        flash(f'認証処理中にエラーが発生しました: {str(e)}', 'error')
        return redirect(url_for('get_projects'))

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
        credentials = get_credentials_from_session()
        if not credentials.valid:
            return jsonify({'authenticated': False, 'message': 'Token expired'})
        return jsonify({'authenticated': True, 'message': 'Authenticated'})
    except Exception as e:
        return jsonify({'authenticated': False, 'message': str(e)})

def get_date_days_ago(days):
    """指定日数前の日付をdatetimeオブジェクトで返す"""
    from datetime import datetime, timedelta
    return datetime.now() - timedelta(days=days)


def get_credentials_from_session() -> Credentials:
    """セッションに保存されている資格情報を安全に復元するヘルパー関数"""
    from datetime import datetime
    creds_dict = session.get('credentials')
    if not creds_dict:
        raise RuntimeError('Gmail credentials not found in session')
    # 文字列の場合は datetime に変換
    if isinstance(creds_dict.get('expiry'), str):
        try:
            creds_dict = creds_dict.copy()
            creds_dict['expiry'] = datetime.fromisoformat(creds_dict['expiry'])
        except Exception:
            # パースできない場合は expiry を削除して後続でリフレッシュさせる
            creds_dict.pop('expiry', None)
    return Credentials(**creds_dict)

def search_gmail_emails(service, skills, normalized_skills):
    """Gmailからメールを検索して案件情報を返す
    
    Args:
        service: Gmail API サービスオブジェクト
        skills: 検索対象のスキルリスト
        normalized_skills: 正規化されたスキルリスト
        
    Returns:
        案件情報のリスト（各案件は辞書形式）
    """
    try:
        # 除外するキーワード
        EXCLUDE_KEYWORDS = [
            # 人材関連
            '人材情報', '個人事業主', 'フリーランス', 'エージェント',
            'スカウト', '転職', '採用情報', '採用募集', '採用担当者様',
            '人材紹介', 'エンジニア情報', '応募', '履歴書', '職務経歴書',
            'レジュメ', 'CV', 'プロフィール', 'ご登録', 'ご案内',
            # その他のノイズ
            'メルマガ', 'ニュースレター', 'セミナー', 'イベント', '勉強会'
        ]
        
        def should_exclude(subject: str, snippet: str) -> bool:
            """除外すべきメールかどうかを判定"""
            if not subject:
                return True
                
            text = f"{subject} {snippet}".lower()
            
            # 除外キーワードのチェック
            for keyword in EXCLUDE_KEYWORDS:
                if keyword in text:
                    return True
            
            # 特定のパターンに一致するメールを除外
            exclude_patterns = [
                r'\d{1,2}\/\d{1,2}\s*【.*】',  # 日付+【】形式の件名
                r'^Re:|^Fw:',                       # 転送・返信メール
                r'^\[.*\]',                         # 【】で始まる件名
                r'^【.*】',                          # 【】で始まる件名（全角）
                r'応募.*[0-9]',                     # 応募番号を含む
                r'履歴書|職務経歴書'                 # 履歴書関連
            ]
            
            for pattern in exclude_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            
            return False

        # 検索クエリを作成
        date_str = get_date_days_ago(30).strftime('%Y/%m/%d')  # 30日前まで遡る
        query_parts = [
            'to:sales@artwize.co.jp',  # 送信先が自社のメールのみ
            f'after:{date_str}',
            'in:inbox',                # 受信トレイのみ
            '-has:attachment',          # 添付ファイルなし
            '(案件 OR 求人 OR 募集 OR プロジェクト)'
        ]
        
        if skills:
            query_parts.append(f"({' OR '.join(skills)})")
        
        query = ' '.join(query_parts)
        
        # メールを検索（メタデータのみ取得）
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=20  # 最大20件に制限
        ).execute()
        
        messages = results.get('messages', [])
        projects = []
        
        print(f"[API] Gmail検索クエリ: {query}")
        print(f"[API] 該当メッセージ数: {len(messages)}")
        
        for msg in messages:
            try:
                # メールの詳細を取得（メタデータのみ）
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                
                # メタデータから必要な情報を抽出
                headers = {h['name'].lower(): h['value'] 
                          for h in message.get('payload', {}).get('headers', [])}
                
                subject = headers.get('subject', '')
                snippet = message.get('snippet', '')
                
                # 除外すべきメールかチェック
                if should_exclude(subject, snippet):
                    continue
                
                # メール本文を取得（スニペットで代用）
                email_body = snippet
                
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
                    'name': subject or '(件名なし)',
                    'client_name': headers.get('from', '送信者不明'),
                    'date': email_date,
                    'snippet': snippet,
                    'body': email_body,
                    'source': 'gmail',
                    'matched_skills': [],
                    'match_count': 0,
                    'match_score': 0,
                    'match_percentage': 0
                }
                
                # スキルマッチング情報を追加
                search_text = f"{subject} {snippet} {email_body}".lower()
                project['matched_skills'] = [
                    s for s in normalized_skills 
                    if s.lower() in search_text
                ]
                project['match_count'] = len(project['matched_skills'])
                project['match_score'] = project['match_count']
                project['match_percentage'] = min(project['match_count'] * 20, 100)
                
                # マッチするスキルがある場合のみ追加
                if project['match_count'] > 0:
                    projects.append(project)
                
            except Exception as e:
                print(f"メールの処理中にエラーが発生しました: {e}")
                continue
        
        # マッチスコアの高い順にソート
        projects.sort(key=lambda x: x['match_score'], reverse=True)
        
        return projects
        
    except Exception as e:
        print(f"Gmail検索中にエラーが発生しました: {e}")
        return []  # エラー時は空リストを返す
        raise

# このエンドポイントは /api/projects に統合されました

# スキルを保存するAPIエンドポイント
@app.route('/api/save_skills', methods=['POST'])
def save_skills():
    try:
        data = request.get_json()
        
        # 必須パラメータのバリデーション
        if not data:
            return jsonify({'status': 'error', 'message': 'リクエストボディが空です'}), 400
            
        if 'skills' not in data or not data['skills']:
            return jsonify({'status': 'error', 'message': 'スキルが指定されていません'}), 400
            
        # engineerIdが指定されていない場合はデフォルト値（'1'）を使用
        engineer_id = data.get('engineerId', '1')
        skills = data['skills']
        
        # スキルの型チェック（リストまたは文字列のカンマ区切りをサポート）
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(',') if s.strip()]
        elif not isinstance(skills, list):
            return jsonify({'status': 'error', 'message': '無効なスキル形式です。配列またはカンマ区切りの文字列を指定してください。'}), 400
        
        # スキルをカンマ区切りの文字列に変換（オブジェクト配列にも対応）
        processed_skills = []
        for s in skills:
            if isinstance(s, dict):
                # オブジェクトの場合、name または skill_name を使用
                processed_skills.append(s.get('name') or s.get('skill_name') or '')
            else:
                processed_skills.append(str(s))
        # 空文字列を除外
        processed_skills = [ps.strip() for ps in processed_skills if ps.strip()]
        skills_str = ','.join(processed_skills)
        
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
        
        # セッションにも保存（大文字化して後続のフィルタで使いやすくする）
        session['skills'] = [s.upper() for s in processed_skills]
        session.modified = True
        app.logger.debug(f"セッションskills更新: {session['skills']}")
        
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
                dt_parser = parser.parse(date)
                date = dt_parser.strftime('%Y-%m-%d %H:%M:%S')
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

def extract_skills_from_email(body: str, min_confidence: float = 0.4) -> List[Dict[str, Any]]:
    """メール本文からスキルを抽出して詳細な情報を返す（強化版）
    
    Args:
        body: メール本文
        min_confidence: 採用する最小信頼度 (0.0-1.0)
        
    Returns:
        抽出されたスキルのリスト。各スキルは以下のキーを持つ辞書:
        - name: スキル名
        - confidence: 信頼度 (0.0-1.0)
        - categories: カテゴリのリスト
        - experience_years: 経験年数（推測）
        - context: スキルが検出された文脈
    """
    if not body:
        return []
    
    # テキストを前処理（不要な改行やスペースを削除）
    clean_body = ' '.join(body.split())
    
    # スキル抽出器を使用
    extractor = SkillExtractor()
    skills_data = extractor.extract_skills(clean_body)
    
    # 結果を整形
    extracted_skills = []
    added_skills = set()
    
    # カテゴリごとに処理
    for category, skills in skills_data.items():
        for skill_data in skills:
            skill_name = skill_data['name']
            
            # 重複をスキップ
            if skill_name.lower() in added_skills:
                continue
                
            # 重要度が閾値以上のスキルのみを採用
            if skill_data.get('importance', 0) >= min_confidence:
                extracted_skills.append({
                    'name': skill_name,
                    'confidence': skill_data.get('importance', 0.5),
                    'categories': skill_data.get('categories', []),
                    'experience_years': skill_data.get('experience_years', 0),
                    'context': skill_data.get('context', '')
                })
                added_skills.add(skill_name.lower())
    
    # 信頼度でソート（高い順）
    extracted_skills.sort(key=lambda x: x['confidence'], reverse=True)
    
    return extracted_skills

def find_matching_engineers(project_requirements: List[Dict[str, Any]], project_context: str = "") -> List[Dict[str, Any]]:
    """プロジェクト要件に基づいてマッチするエンジニアを検索
    
    Args:
        project_requirements: プロジェクト要件のリスト。各要素は以下のキーを持つ辞書:
            - skill: スキル名 (必須)
            - level: 必要とされるレベル (オプション)
            - weight: 重み (デフォルト: 1.0)
        project_context: プロジェクトのコンテキスト（スキルの重み付けに使用）
        
    Returns:
        マッチしたエンジニアのリスト（マッチスコアの高い順にソート）
    """
    if not project_requirements:
        return []
    
    conn = get_db()
    cursor = conn.cursor()
    
    # エンジニアを取得（スキル情報とともに）
    cursor.execute("""
        SELECT e.*, 
               s.name as skill_name,
               es.level as skill_level,
               es.experience_years as experience_years
        FROM engineers e
        LEFT JOIN engineer_skills es ON e.id = es.engineer_id
        LEFT JOIN skills s ON es.skill_id = s.id
        ORDER BY e.id
    """)
    
    # エンジニアごとにスキルをグループ化
    engineers_skills = defaultdict(list)
    for row in cursor.fetchall():
        if row['skill_name']:  # スキルがある場合のみ追加
            engineers_skills[row['id']].append({
                'name': row['skill_name'],
                'level': row['skill_level'],
                'experience_years': row['experience_years']
            })
    
    # 各エンジニアのマッチングを計算
    matched_engineers = []
    for engineer_id, skills in engineers_skills.items():
        # 新しいマッチング機能を使用
        result = enhance_skill_matching(
            project_requirements=project_requirements,
            candidate_skills=skills
        )
        
        # マッチしたスキルの詳細を取得
        matched_skills_details = [
            {
                'required_skill': m.get('required_skill', ''),
                'matched_skill': m.get('matched_skill', ''),
                'level': m.get('level', ''),
                'score': m.get('score', 0),
                'match_type': m.get('match_type', 'unknown')
            }
            for m in result.get('matches', [])
        ]
        
        # エンジニア情報を取得
        cursor.execute("SELECT * FROM engineers WHERE id = ?", (engineer_id,))
        engineer = dict(cursor.fetchone())
        
        # マッチング結果を追加
        matched_engineers.append({
            'engineer': engineer,
            'match_score': result.get('match_ratio', 0),
            'match_ratio': result.get('match_ratio', 0),
            'matched_skills': [m.get('required_skill', '') for m in result.get('matches', []) if 'required_skill' in m],
            'matched_skills_details': matched_skills_details,
            'missed_skills': result.get('missed_skills', []),
            'total_required_skills': len(project_requirements),
            'matched_skills_count': len(result.get('matches', [])),
            'matching_algorithm': 'enhanced'  # 使用したマッチングアルゴリズムを記録
        })
    
    # マッチスコアの高い順にソート
    matched_engineers.sort(key=lambda x: x['match_score'], reverse=True)
    
    return matched_engineers

def detect_sections(text: str) -> Dict[str, str]:
    """テキストからセクションを検出する"""
    sections = {
        'skills': '',
        'experience': '',
        'projects': '',
        'education': '',
        'certifications': '',
        'other': ''
    }
    
    # 簡単なキーワードベースのセクション検出
    section_keywords = {
        'skills': ['スキル', '技術', 'skills', 'technology'],
        'experience': ['経験', '職務', 'work', 'experience'],
        'projects': ['プロジェクト', '開発', 'project', 'development'],
        'education': ['学歴', '教育', 'education'],
        'certifications': ['資格', '認定', 'certification']
    }
    
    # テキストを行に分割
    lines = text.split('\n')
    current_section = 'other'
    
    for line in lines:
        line_lower = line.lower().strip()
        
        # セクションヘッダーを検出
        for section, keywords in section_keywords.items():
            if any(keyword in line_lower for keyword in keywords):
                current_section = section
                break
        
        # 現在のセクションにテキストを追加
        sections[current_section] += line + ' '
    
    return sections

def estimate_experience_years(skill_data: Dict[str, Any], context: str) -> float:
    """経験年数を推定する"""
    # スキルデータから経験年数を取得
    exp_years = skill_data.get('experience_years', 0)
    
    # コンテキストから経験年数を推定
    year_matches = re.findall(r'(\d+)\s*年', context)
    if year_matches:
        exp_years = max(exp_years, float(year_matches[0]))
    
    return exp_years

def determine_skill_level(exp_years: float, skill_data: Dict[str, Any]) -> str:
    """スキルレベルを決定する"""
    if exp_years >= 5:
        return 'リード'
    elif exp_years >= 3:
        return '上級'
    elif exp_years >= 1:
        return '中級'
    else:
        return '初級'

def find_related_skills(skill_name: str, skills_data: Dict[str, List[Dict]]):
    """関連するスキルを見つける"""
    related = set()
    
    # 同じカテゴリのスキルを関連スキルとして追加
    for category, skills in skills_data.items():
        for skill in skills:
            if skill['name'] != skill_name:
                related.add(skill['name'])
    
    return list(related)

def extract_project_requirements(text: str, min_confidence: float = 0.4) -> List[Dict[str, Any]]:
    """テキストからプロジェクト要件を抽出する（強化版）
    
    Args:
        text: 抽出元のテキスト
        min_confidence: 採用する最小信頼度 (0.0-1.0)
        
    Returns:
        プロジェクト要件のリスト。各要件は以下のキーを持つ辞書:
        - skill: スキル名
        - level: 必要とされるレベル (初級/中級/上級/リード)
        - weight: 重み (0.0-1.0)
        - categories: スキルのカテゴリリスト
        - experience_years: 経験年数
        - context: スキルが使用された文脈
        - related_skills: 関連するスキルのリスト
    """
    if not text:
        return []
    
    # テキストを前処理（不要な改行やスペースを削除）
    clean_text = ' '.join(text.split())
    
    # セクションを検出
    sections = detect_sections(clean_text)
    
    # スキル抽出器を使用して詳細なスキル情報を取得
    extractor = SkillExtractor()
    
    # プロジェクト要件に変換
    requirements = []
    added_skills = set()  # 重複を防ぐため
    
    # セクションごとに処理
    for section_type, section_text in sections.items():
        # セクションタイプに基づいて重みを調整
        section_weight = {
            'skills': 1.0,
            'experience': 0.9,
            'projects': 0.8,
            'education': 0.6,
            'certifications': 0.7,
            'other': 0.5
        }.get(section_type, 0.5)
        
        # スキルを抽出
        skills_data = extractor.extract_skills(section_text)
        
        # スキルを処理
        for category, skills in skills_data.items():
            for skill_data in skills:
                skill_name = skill_data['name']
                
                # 重複をスキップ
                skill_key = f"{skill_name.lower()}_{category.lower()}"
                if skill_key in added_skills:
                    continue
                
                # 重要度が閾値以上のスキルのみを採用
                importance = skill_data.get('importance', 0) * section_weight
                if importance >= min_confidence:
                    # 経験年数からレベルを推測
                    exp_years = estimate_experience_years(skill_data, section_text)
                    level = determine_skill_level(exp_years, skill_data)
                    
                    # 関連スキルを取得
                    related_skills = find_related_skills(skill_name, skills_data)
                    
                    requirements.append({
                        'skill': skill_name,
                        'level': level,
                        'weight': importance,
                        'categories': skill_data.get('categories', []) + [category],
                        'experience_years': exp_years,
                        'context': skill_data.get('context', ''),
                        'related_skills': related_skills
                    })
                    added_skills.add(skill_key)
    
    # 重みでソート（重みの高い順）
    requirements.sort(key=lambda x: x['weight'], reverse=True)
    
    return requirements

@app.route('/api/projects', methods=['GET'])
def get_projects_api():
    """
    Gmailから案件情報を取得して検索・並び替えができるAPIエンドポイント
    sales@artwize.co.jp に送信されたメールから案件を取得する
    
    クエリパラメータ:
    - q: 検索クエリ（件名・本文から検索）
    - sort: ソート順（date, salary, relevance, match_score）
    - min_salary: 最低給与（万円）
    - max_salary: 最高給与（万円）
    - skills: カンマ区切りのスキルリスト（例: Python,JavaScript,React）
    - days: 何日前までのメールを取得するか（デフォルト: 30日）
    - min_match: 最低マッチ率（0.0-1.0、デフォルト: 0.3）
    """
    # セッションから認証情報を確認
    if 'credentials' not in session:
        return jsonify({'status': 'error', 'message': 'Gmail認証が必要です'}), 401
    
    try:
        # クエリパラメータを取得
        search_query = request.args.get('q', '').lower()
        sort_by = request.args.get('sort', 'date')
        min_salary = request.args.get('min_salary')
        max_salary = request.args.get('max_salary')
        skills_param = request.args.get('skills', '')
        
        try:
            days = int(request.args.get('days', 30))
            min_match = float(request.args.get('min_match', 0.3))
        except (ValueError, TypeError) as e:
            return jsonify({
                'status': 'error',
                'message': '無効なパラメータです。daysは整数、min_matchは数値を指定してください。'
            }), 400
        
        # スキルフィルターを処理
        skills_filter = [s.strip() for s in skills_param.split(',') if s.strip()]
        
        # Gmailサービスを初期化
        credentials = get_credentials_from_session()
        service = build('gmail', 'v1', credentials=credentials)
        
        # 検索クエリを構築
        query = f'to:sales@artwize.co.jp newer_than:{days}d'
        if search_query:
            query += f' {search_query}'
            
        # メッセージを検索
        # メッセージを検索
        response = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=50
        ).execute()
        
        messages = response.get('messages', [])
        projects = []
        
        # 各メッセージを処理
        for msg in messages:
            try:
                # メッセージの詳細を取得
                msg_data = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # メール情報を抽出
                headers = {}
                for header in msg_data.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 件名を取得してフィルタリング
                subject = headers.get('subject', '').lower()
                if any(keyword in subject for keyword in ['人材情報', '個人事業主', 'エンジニア情報', '人材紹介']):
                    continue
                
                # 添付ファイルがあるかチェック
                has_attachments = any(
                    part.get('filename') 
                    for part in msg_data.get('payload', {}).get('parts', [])
                    if part.get('filename')  # ファイル名があるパートのみをチェック
                )
                if has_attachments:
                    continue
                
                # 件名と送信者を取得
                subject = headers.get('subject', '(件名なし)')
                sender = headers.get('from', '送信者不明')
                date = headers.get('date', '')
                
                # メール本文を取得
                body = ''
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            break
                
                # プロジェクト要件を抽出
                project_requirements = extract_project_requirements(f"{subject}\n\n{body}")
                
                # スキルフィルターが指定されている場合はマッチングを確認
                if skills_filter:
                    # スキルマッチングを実行
                    matched_skills = [
                        req['skill'] for req in project_requirements 
                        if any(skill.lower() in req['skill'].lower() for skill in skills_filter)
                    ]
                    
                    # マッチ率を計算
                    match_ratio = len(matched_skills) / len(skills_filter) if skills_filter else 0
                    
                    # 最低マッチ率に満たない場合はスキップ
                    if match_ratio < min_match:
                        continue
                else:
                    matched_skills = []
                    match_ratio = 0
                
                # メール本文を整形
                email_body = body
                email_content = f"{subject} {email_body}".upper()
                
                # スキルマッチングを実行
                matched_skills = []
                if skills_filter:
                    for skill in skills_filter:
                        if skill.upper() in email_content:
                            matched_skills.append(skill)
                    
                    # スキルが1つもマッチしない場合はスキップ
                    if not matched_skills:
                        continue
                
                # マッチ率を計算
                match_count = len(matched_skills)
                match_percentage = int((match_count / len(skills_filter)) * 100) if skills_filter else 0
                
                # 日付をフォーマット
                timestamp = 0
                formatted_date = date
                try:
                    if date:
                        dt_parser = parser.parse(date)
                        timestamp = int(dt_parser.timestamp())
                        formatted_date = dt_parser.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
                
                # 給与情報を抽出（あれば）
                salary = None
                salary_match = re.search(r'(給与|報酬|単価)[:：]\s*([0-9,]+)', email_body, re.IGNORECASE)
                if salary_match:
                    try:
                        salary = int(salary_match.group(2).replace(',', ''))
                        # 給与フィルターを適用
                        if min_salary and salary < int(min_salary):
                            continue
                        if max_salary and salary > int(max_salary):
                            continue
                    except (ValueError, AttributeError):
                        pass
                
                # 勤務地を抽出
                location_match = re.search(r'勤務地[：:]([^\n]+)', email_body)
                location = location_match.group(1).strip() if location_match else '未記載'
                
                # スニペットを作成
                snippet = email_body[:200] + ('...' if len(email_body) > 200 else '')
                
                    # プロジェクトオブジェクトを作成
                project = {
                    'id': msg['id'],
                    'title': subject or '無題の案件',
                    'subject': subject,
                    'snippet': snippet,
                    'description': snippet,
                    'created_at': formatted_date,
                    'from': sender,
                    'salary': salary,
                    'location': location,
                    'body': email_body[:500] + '...' if len(email_body) > 500 else email_body,
                    'matched_skills': matched_skills,
                    'match_count': match_count,
                    'match_percentage': match_percentage,
                    'timestamp': timestamp,
                    'thread_id': msg.get('threadId', ''),
                    'message_id': msg['id'],
                    'gmail_url': f"https://mail.google.com/mail/u/0/#all/{msg.get('threadId', '')}" if msg.get('threadId') else f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{quote(msg['id'])}"
                }
                
                projects.append(project)
                
            except Exception as e:
                print(f"[API] メール処理エラー (ID: {msg.get('id', 'unknown')}): {str(e)}")
                # エラーが発生した場合はこのメールの処理をスキップ
                continue
        
        # ソート処理
        if sort_by == 'date':
            projects.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        elif sort_by == 'salary':
            projects.sort(key=lambda x: x.get('salary', 0), reverse=True)
        elif sort_by == 'relevance':
            # 関連度が高い順（マッチ率の高い順）にソート
            projects.sort(key=lambda x: (x.get('match_percentage', 0), x.get('timestamp', 0)), reverse=True)
        
        return jsonify({
            'status': 'success',
            'data': projects,
            'total': len(projects),
            'query': {
                'search_query': search_query,
                'skills': skills_filter,
                'days': days,
                'sort_by': sort_by,
                'min_salary': min_salary,
                'max_salary': max_salary,
                'min_match': min_match
            }
        })
            
    except Exception as e:
        error_msg = f'API処理中にエラーが発生しました: {str(e)}'
        app.logger.error(f'[API] エラー: {error_msg}', exc_info=True)
        return jsonify({
            'status': 'error',
            'message': error_msg,
            'error_type': str(type(e).__name__)
        }), 500

@app.route('/projects', methods=['GET'])
def get_projects():
    """
    プロジェクト一覧ページを表示する
    スキルシートに基づいて sales@artwize.co.jp に送信されたメールから案件を検索して表示
    """
    try:
        # セッションから認証情報を取得
        if 'credentials' not in session:
            return redirect(url_for('gmail_auth'))
            
        # セッションからスキルを取得（必須）
        skills = session.get('skills')
        if not skills:
            return render_template('projects.html',
                               projects=[],
                               error_message='スキルシートがアップロードされていません。まずはスキルシートをアップロードしてください。')
        
        # Gmailサービスを初期化
        credentials = get_credentials_from_session()
        service = build('gmail', 'v1', credentials=credentials)
        
        # デバッグ用ログ
        print(f"[プロジェクト検索] スキル: {skills}")
        
        # スキルでGmail案件を検索（to:sales@artwize.co.jp でフィルタリング）
        query_parts = [f'to:sales@artwize.co.jp', f'after:{get_date_days_ago(30)}']
        if skills:
            query_parts.append(f"({' OR '.join(skills)})")
        
        query = ' '.join(query_parts)
        print(f"[プロジェクト検索] Gmail検索クエリ: {query}")
        
        # Gmailからメールを検索
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=50
        ).execute()
        
        messages = results.get('messages', [])
        print(f"[プロジェクト検索] 該当メッセージ数: {len(messages)}")
        
        # メッセージから案件情報を抽出
        projects = []
        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # メールヘッダーから基本情報を抽出
                headers = {}
                for header in message.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # メール本文を抽出
                email_body = ''
                payload = message.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                            email_body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'body' in payload and 'data' in payload['body']:
                    email_body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                
                # スキルマッチング
                matched_skills = []
                email_content = f"{headers.get('subject', '')} {email_body}".lower()
                
                for skill in skills:
                    if skill.lower() in email_content:
                        matched_skills.append(skill)
                
                # メッセージIDとスレッドIDを取得
                message_id = msg['id']
                thread_id = message.get('threadId')
                gmail_url = f"https://mail.google.com/mail/u/0/#all/{thread_id}" if thread_id else f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{quote(message_id)}"
                
                # メッセージから案件情報を抽出
                project = {
                    'id': message_id,
                    'thread_id': thread_id,
                    'gmail_url': gmail_url,
                    'title': headers.get('subject', '（件名なし）'),
                    'description': email_body[:200] + '...' if len(email_body) > 200 else email_body,
                    'created_at': headers.get('date', ''),
                    'from': headers.get('from', '送信者不明'),
                    'location': location,
                    'salary': salary,
                    'required_skills': matched_skills,
                    'match_count': len(matched_skills),
                    'match_percentage': int((len(matched_skills) / len(skills)) * 100) if skills else 0
                }
                projects.append(project)
                    
            except Exception as e:
                print(f"[プロジェクト検索] メール処理エラー (ID: {msg.get('id')}): {str(e)}")
                continue
        
        # マッチ率の高い順にソート
        projects.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
        
        print(f"[プロジェクト検索] マッチした案件数: {len(projects)}")
        
        # テンプレートにプロジェクトデータを渡してレンダリング
        return render_template('projects.html', projects=projects)
        
    except Exception as e:
        error_msg = f'プロジェクトの取得中にエラーが発生しました: {str(e)}'
        app.logger.error(f'[プロジェクト検索] エラー: {error_msg}', exc_info=True)
        return render_template('projects.html', 
                            projects=[], 
                            error_message=error_msg)

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
        # セッションから認証情報を取得
        creds_info = session['credentials']
        creds = Credentials(
            token=creds_info['token'],
            refresh_token=creds_info.get('refresh_token'),  # refresh_tokenは初回のみの可能性があるためgetを使用
            token_uri=creds_info['token_uri'],
            client_id=creds_info['client_id'],
            client_secret=creds_info['client_secret'],
            scopes=creds_info['scopes']
        )
        
        # トークンの有効期限をチェックして必要に応じて更新
        if creds.expired and creds.refresh_token:
            try:
                app.logger.info("Refreshing expired token")
                creds.refresh(Request())
                
                # 更新した認証情報をセッションに保存
                session['credentials'] = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,  # 新しいリフレッシュトークン（あれば）
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None
                }
                session.modified = True
                app.logger.info("Token refreshed successfully")
                
            except Exception as e:
                app.logger.error(f"Failed to refresh token: {str(e)}", exc_info=True)
                # 認証情報が無効な場合はセッションから削除
                session.pop('credentials', None)
                session.pop('gmail_authenticated', None)
                return None
        
        # 認証情報が有効か確認
        if not creds.valid:
            app.logger.warning("Invalid credentials")
            session.pop('credentials', None)
            session.pop('gmail_authenticated', None)
            return None
            
        # Gmail APIサービスを構築して返す
        try:
            service = build('gmail', 'v1', credentials=creds)
            return service
            
        except Exception as e:
            app.logger.error(f"Failed to create Gmail service: {str(e)}", exc_info=True)
            # サービス作成に失敗した場合は認証情報を無効化
            session.pop('credentials', None)
            session.pop('gmail_authenticated', None)
            return None
            
    except Exception as e:
        app.logger.error(f"Error in get_gmail_service: {str(e)}", exc_info=True)
        # エラーが発生した場合は認証情報をクリア
        session.pop('credentials', None)
        session.pop('gmail_authenticated', None)
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
