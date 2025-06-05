from flask import Flask, jsonify, request, g
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

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
