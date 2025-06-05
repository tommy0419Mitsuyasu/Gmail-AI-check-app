from flask import Flask, jsonify, request, g, send_from_directory, url_for
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import PyPDF2
from typing import List, Dict, Any, Optional

# アップロード設定
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# エラーメッセージ
error_messages = {
    'no_file': 'ファイルが選択されていません',
    'invalid_extension': '許可されていないファイル形式です。PDFまたはWord文書をアップロードしてください。',
    'file_too_large': f'ファイルサイズが大きすぎます。{MAX_FILE_SIZE // (1024*1024)}MB以下のファイルをアップロードしてください。',
    'upload_failed': 'ファイルのアップロードに失敗しました。',
    'processing_error': 'ファイルの処理中にエラーが発生しました。',
    'invalid_file': 'ファイルが破損しているか、サポートされていない形式です。'
}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# ファイルの拡張子チェック
def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# PDFからテキストを抽出
def extract_text_from_pdf(filepath: str) -> str:
    text = ""
    try:
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        app.logger.error(f"PDFの解析中にエラーが発生しました: {e}")
    return text

# Word文書からテキストを抽出
def extract_text_from_docx(filepath: str) -> str:
    try:
        import docx2txt
        return docx2txt.process(filepath)
    except Exception as e:
        app.logger.error(f"Word文書の解析中にエラーが発生しました: {e}")
        return ""

# スキルカテゴリ定義
SKILL_CATEGORIES = {
    'programming': {
        'name': 'プログラミング言語',
        'keywords': {
            'Python': {'aliases': ['python', 'パイソン'], 'level': 3},
            'JavaScript': {'aliases': ['javascript', 'js', 'ジャバスクリプト'], 'level': 3},
            'TypeScript': {'aliases': ['typescript', 'ts'], 'level': 3},
            'Java': {'aliases': ['java', 'ジャバ'], 'level': 3},
            'C++': {'aliases': ['c++', 'cpp', 'シープラスプラス'], 'level': 3},
            'C#': {'aliases': ['c#', 'csharp', 'シーシャープ'], 'level': 3},
            'Ruby': {'aliases': ['ruby', 'ルビー'], 'level': 3},
            'PHP': {'aliases': ['php', 'ピーエイチピー'], 'level': 3},
            'Go': {'aliases': ['go', 'golang', 'ゴー'], 'level': 3},
            'Rust': {'aliases': ['rust', 'ラスト'], 'level': 2},
            'Swift': {'aliases': ['swift', 'スウィフト'], 'level': 2},
            'Kotlin': {'aliases': ['kotlin', 'コトリン'], 'level': 2},
        }
    },
    'framework': {
        'name': 'フレームワーク',
        'keywords': {
            'Django': {'aliases': ['django', 'ジャンゴ'], 'level': 3},
            'Flask': {'aliases': ['flask', 'フラスク'], 'level': 3},
            'FastAPI': {'aliases': ['fastapi', 'ファストエーピーアイ'], 'level': 3},
            'React': {'aliases': ['react', 'リアクト'], 'level': 3},
            'Vue.js': {'aliases': ['vue', 'vue.js', 'ビュージェーエス'], 'level': 3},
            'Angular': {'aliases': ['angular', 'アンギュラー'], 'level': 3},
            'Node.js': {'aliases': ['node', 'node.js', 'ノード'], 'level': 3},
            'Spring': {'aliases': ['spring', 'スプリング'], 'level': 3},
            'Laravel': {'aliases': ['laravel', 'ララベル'], 'level': 2},
            'Ruby on Rails': {'aliases': ['rails', 'ruby on rails', 'ルビーオンレイルズ'], 'level': 2},
        }
    },
    'cloud': {
        'name': 'クラウド',
        'keywords': {
            'AWS': {'aliases': ['aws', 'amazon web services'], 'level': 3},
            'Azure': {'aliases': ['azure', 'アジュール'], 'level': 3},
            'GCP': {'aliases': ['gcp', 'google cloud', 'google cloud platform'], 'level': 3},
            'Docker': {'aliases': ['docker', 'ドッカー'], 'level': 3},
            'Kubernetes': {'aliases': ['kubernetes', 'k8s', 'クバネティス'], 'level': 3},
            'Terraform': {'aliases': ['terraform', 'テラフォーム'], 'level': 2},
            'Ansible': {'aliases': ['ansible', 'アンシブル'], 'level': 2},
            'Serverless': {'aliases': ['serverless', 'サーバーレス'], 'level': 2},
        }
    },
    'database': {
        'name': 'データベース',
        'keywords': {
            'SQL': {'aliases': ['sql', 'エスキューエル'], 'level': 3},
            'PostgreSQL': {'aliases': ['postgresql', 'postgres', 'ポストグレ'], 'level': 3},
            'MySQL': {'aliases': ['mysql', 'マイエスキューエル'], 'level': 3},
            'MongoDB': {'aliases': ['mongodb', 'モンゴ'], 'level': 3},
            'Redis': {'aliases': ['redis', 'レディス'], 'level': 3},
            'Oracle': {'aliases': ['oracle', 'オラクル'], 'level': 2},
            'SQLite': {'aliases': ['sqlite', 'エスキューライト'], 'level': 2},
            'DynamoDB': {'aliases': ['dynamodb', 'ダイナモ'], 'level': 2},
        }
    },
    'ai_ml': {
        'name': 'AI/機械学習',
        'keywords': {
            '機械学習': {'aliases': ['machine learning', 'マシンラーニング'], 'level': 3},
            '深層学習': {'aliases': ['deep learning', 'ディープラーニング'], 'level': 3},
            'データ分析': {'aliases': ['data analysis', 'データアナリシス'], 'level': 3},
            'データサイエンス': {'aliases': ['data science', 'データサイエンス'], 'level': 3},
            'AI': {'aliases': ['ai', '人工知能', 'artificial intelligence'], 'level': 3},
            'TensorFlow': {'aliases': ['tensorflow', 'テンソルフロー'], 'level': 2},
            'PyTorch': {'aliases': ['pytorch', 'パイトーチ'], 'level': 2},
            'scikit-learn': {'aliases': ['scikit-learn', 'sklearn', 'サイキットラーン'], 'level': 2},
        }
    },
    'devops': {
        'name': 'DevOps/ツール',
        'keywords': {
            'Git': {'aliases': ['git', 'ギット'], 'level': 3},
            'GitHub': {'aliases': ['github', 'ギットハブ'], 'level': 3},
            'GitLab': {'aliases': ['gitlab', 'ギットラボ'], 'level': 3},
            'CI/CD': {'aliases': ['ci/cd', 'continuous integration', '継続的インテグレーション'], 'level': 3},
            'Jenkins': {'aliases': ['jenkins', 'ジェンキンス'], 'level': 3},
            'GitHub Actions': {'aliases': ['github actions', 'ギットハブアクションズ'], 'level': 3},
            'CircleCI': {'aliases': ['circleci', 'サークルシーアイ'], 'level': 2},
            'Docker Compose': {'aliases': ['docker-compose', 'docker compose', 'ドッカーコンポーズ'], 'level': 2},
        }
    },
    'methodology': {
        'name': '開発手法',
        'keywords': {
            'アジャイル': {'aliases': ['agile', 'アジャイル開発'], 'level': 3},
            'スクラム': {'aliases': ['scrum', 'スクラム開発'], 'level': 3},
            'DevOps': {'aliases': ['devops', 'デブオプス'], 'level': 3},
            'TDD': {'aliases': ['tdd', 'テスト駆動開発'], 'level': 2},
            'BDD': {'aliases': ['bdd', '振る舞い駆動開発'], 'level': 2},
            'CI/CD': {'aliases': ['ci/cd', '継続的インテグレーション/デプロイ'], 'level': 3},
            'マイクロサービス': {'aliases': ['microservice', 'マイクロサービスアーキテクチャ'], 'level': 2},
        }
    }
}

def extract_skills(text: str) -> List[Dict[str, Any]]:
    """
    テキストからスキルを抽出し、カテゴリと重要度を付与して返す
    
    Args:
        text (str): 解析対象のテキスト
        
    Returns:
        List[Dict[str, Any]]: 抽出されたスキルのリスト
            [
                {
                    'name': 'スキル名',
                    'category': 'カテゴリ名',
                    'level': 1-3,  # 1: 初心者, 2: 中級者, 3: 上級者
                    'level_name': '上級',
                    'category_name': 'プログラミング言語',
                    'matched_text': ['マッチしたテキスト1', 'マッチしたテキスト2']
                },
                ...
            ]
    """
    text_lower = text.lower()
    found_skills = {}
    
    # 各カテゴリのキーワードを検索
    for category_id, category_data in SKILL_CATEGORIES.items():
        for skill_name, skill_data in category_data['keywords'].items():
            # エイリアスを含むすべてのキーワードで検索
            search_terms = [skill_name.lower()] + skill_data['aliases']
            matched_texts = []
            
            for term in search_terms:
                if term in text_lower:
                    matched_texts.append(term)
            
            # いずれかのキーワードにマッチした場合
            if matched_texts:
                if skill_name not in found_skills:
                    found_skills[skill_name] = {
                        'name': skill_name,
                        'category': category_id,
                        'category_name': category_data['name'],
                        'level': skill_data['level'],
                        'level_name': get_level_name(skill_data['level']),
                        'matched_text': matched_texts,
                        'count': len(matched_texts)
                    }
                else:
                    # 既存のスキルにマッチしたテキストを追加
                    existing_matches = set(found_skills[skill_name]['matched_text'])
                    new_matches = set(matched_texts) - existing_matches
                    if new_matches:
                        found_skills[skill_name]['matched_text'].extend(new_matches)
                        found_skills[skill_name]['count'] = len(found_skills[skill_name]['matched_text'])
    
    # リストに変換して返す
    skills_list = list(found_skills.values())
    
    # 重要度（出現回数とレベルの積）でソート
    skills_list.sort(key=lambda x: (x['count'] * x['level']), reverse=True)
    
    return skills_list

def get_level_name(level: int) -> str:
    """スキルレベルを表す文字列を返す"""
    if level == 1:
        return '初級'
    elif level == 2:
        return '中級'
    else:
        return '上級'

# データベースファイル名
DB_FILE = 'ses_match.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """データベースを初期化する"""
    conn = get_db()
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

# 静的ファイルの提供
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ファイルアップロードAPI
@app.route('/api/upload', methods=['POST'])
def upload_file():
    # ファイルがリクエストに含まれているか確認
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': error_messages['no_file'],
            'code': 'NO_FILE'
        }), 400
    
    file = request.files['file']
    
    # ファイル名が空でないか確認
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': error_messages['no_file'],
            'code': 'NO_FILE_SELECTED'
        }), 400
    
    # ファイル拡張子の検証
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': error_messages['invalid_extension'],
            'code': 'INVALID_EXTENSION',
            'allowed_extensions': list(ALLOWED_EXTENSIONS)
        }), 400
        
    # ファイルサイズの検証
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    
    if file_length > MAX_FILE_SIZE:
        return jsonify({
            'success': False,
            'error': error_messages['file_too_large'],
            'code': 'FILE_TOO_LARGE',
            'max_size_mb': MAX_FILE_SIZE // (1024*1024),
            'file_size_mb': round(file_length / (1024*1024), 2)
        }), 400
    
    try:
        # 安全なファイル名に変換
        filename = secure_filename(file.filename)
        
        # アップロードディレクトリが存在することを確認
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # ファイルを保存
        try:
            file.save(filepath)
        except IOError as e:
            app.logger.error(f'ファイルの保存中にエラーが発生しました: {str(e)}')
            return jsonify({
                'success': False,
                'error': error_messages['upload_failed'],
                'code': 'UPLOAD_FAILED'
            }), 500
        
        # ファイルタイプに応じてテキストを抽出
        text = ""
        if filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(filepath)
        elif filename.lower().endswith(('.docx', '.doc')):
            text = extract_text_from_docx(filepath)
        else:
            return jsonify({
                'success': False,
                'error': error_messages['invalid_file'],
                'code': 'INVALID_FILE'
            }), 400
        
        if not text.strip():
            return jsonify({
                'success': False,
                'error': error_messages['invalid_file'],
                'code': 'INVALID_FILE'
            }), 400
        
        # スキルを抽出
        skills = extract_skills(text)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'skills': skills,
            'text_preview': text[:500] + '...' if len(text) > 500 else text
        })
        
    except Exception as e:
        app.logger.error(f'エラーが発生しました: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': error_messages['processing_error'],
            'code': 'PROCESSING_ERROR',
            'details': str(e)
        }), 500

# APIエンドポイント
@app.route('/')
def index():
    return jsonify({"message": "SESエンジンマッチングAPIへようこそ！"})

@app.route('/engineers/', methods=['GET', 'POST'])
def handle_engineers():
    if request.method == 'GET':
        try:
            conn = get_db()
            c = conn.cursor()
            
            engineers = []
            c.execute('SELECT * FROM engineers')
            for row in c.fetchall():
                engineer = dict(row)
                c2 = conn.cursor()
                c2.execute('SELECT name, level FROM skills WHERE engineer_id = ?', (engineer['id'],))
                engineer['skills'] = [dict(skill) for skill in c2.fetchall()]
                engineers.append(engineer)
            
            return jsonify({"status": "success", "data": engineers})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # 必須フィールドのバリデーション
            required_fields = ['name', 'email', 'skills']
            for field in required_fields:
                if field not in data:
                    return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400
            
            conn = get_db()
            c = conn.cursor()
            
            # エンジナーを登録
            c.execute('''
            INSERT INTO engineers (name, email, current_role, location, experience_years)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                data.get('name'),
                data.get('email'),
                data.get('current_role'),
                data.get('location'),
                data.get('experience_years')
            ))
            
            engineer_id = c.lastrowid
            
            # スキルを登録
            for skill in data['skills']:
                if 'name' not in skill or 'level' not in skill:
                    conn.rollback()
                    return jsonify({"status": "error", "message": "Each skill must have 'name' and 'level'"}), 400
                
                c.execute('''
                INSERT INTO skills (engineer_id, name, level)
                VALUES (?, ?, ?)
                ''', (engineer_id, skill['name'], skill['level']))
            
            conn.commit()
            
            return jsonify({
                "status": "success",
                "message": "Engineer added successfully",
                "engineer_id": engineer_id
            }), 201
            
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return jsonify({"status": "error", "message": "Email already exists"}), 400
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/projects/', methods=['GET', 'POST'])
def handle_projects():
    if request.method == 'GET':
        try:
            conn = get_db()
            c = conn.cursor()
            
            projects = []
            c.execute('SELECT * FROM projects')
            for row in c.fetchall():
                project = dict(row)
                c2 = conn.cursor()
                c2.execute('SELECT skill, level, weight FROM project_requirements WHERE project_id = ?', (project['id'],))
                project['requirements'] = [dict(req) for req in c2.fetchall()]
                projects.append(project)
            
            return jsonify({"status": "success", "data": projects})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # 必須フィールドのバリデーション
            required_fields = ['name', 'requirements']
            for field in required_fields:
                if field not in data:
                    return jsonify({"status": "error", "message": f"Missing required field: {field}"}), 400
            
            conn = get_db()
            c = conn.cursor()
            
            # プロジェクトを登録
            c.execute('''
            INSERT INTO projects (
                name, client_name, description, location, 
                work_type, start_date, duration_months, min_budget, max_budget
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('name'),
                data.get('client_name'),
                data.get('description'),
                data.get('location'),
                data.get('work_type'),
                data.get('start_date', datetime.now().strftime('%Y-%m-%d')),
                data.get('duration_months'),
                data.get('min_budget'),
                data.get('max_budget')
            ))
            
            project_id = c.lastrowid
            
            # 要件を登録
            for req in data['requirements']:
                if 'skill' not in req or 'level' not in req:
                    conn.rollback()
                    return jsonify({
                        "status": "error", 
                        "message": "Each requirement must have 'skill' and 'level'"
                    }), 400
                
                c.execute('''
                INSERT INTO project_requirements (project_id, skill, level, weight)
                VALUES (?, ?, ?, ?)
                ''', (
                    project_id, 
                    req['skill'], 
                    req['level'], 
                    req.get('weight', 1)
                ))
            
            conn.commit()
            
            return jsonify({
                "status": "success",
                "message": "Project added successfully",
                "project_id": project_id
            }), 201
            
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/matches/<int:project_id>', methods=['GET'])
def get_matches(project_id):
    try:
        conn = get_db()
        c = conn.cursor()
        
        # プロジェクトの取得
        c.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = c.fetchone()
        if not project:
            return jsonify({"status": "error", "message": "Project not found"}), 404
        
        project = dict(project)
        
        # プロジェクトの要件を取得
        c.execute('SELECT skill, level, weight FROM project_requirements WHERE project_id = ?', (project_id,))
        requirements = c.fetchall()
        
        # エンジニアのマッチングスコアを計算
        c.execute('SELECT * FROM engineers')
        engineers = []
        
        for eng in c.fetchall():
            eng_dict = dict(eng)
            
            # スキルを取得
            c2 = conn.cursor()
            c2.execute('SELECT name, level FROM skills WHERE engineer_id = ?', (eng['id'],))
            eng_skills = {s['name'].lower(): s['level'] for s in c2.fetchall()}
            
            # スコア計算
            score = 0
            matched_skills = []
            
            for req in requirements:
                req_skill = req['skill'].lower()
                if req_skill in eng_skills:
                    level_score = {
                        'beginner': 1,
                        'intermediate': 2,
                        'expert': 3
                    }.get(eng_skills[req_skill].lower(), 0)
                    
                    score += level_score * req['weight']
                    matched_skills.append({
                        'skill': req['skill'],
                        'required_level': req['level'],
                        'engineer_level': eng_skills[req_skill],
                        'match': eng_skills[req_skill].lower() == req['level'].lower()
                    })
            
            if score > 0:
                eng_dict['score'] = score
                eng_dict['matched_skills'] = matched_skills
                engineers.append(eng_dict)
        
        # スコアの高い順にソート
        engineers.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return jsonify({
            "status": "success",
            "data": {
                "project": project,
                "matches": engineers
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # データベース初期化
    if not os.path.exists(DB_FILE):
        init_db()
    
    # アプリケーションの実行
    app.run(debug=True, port=5000)
