import os
import re
import json
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import PyPDF2
from datetime import datetime, timedelta
from collections import defaultdict
from skill_matcher import SkillMatcher

# 髢狗匱迺ｰ蠅・畑縺ｮ險ｭ螳夲ｼ域悽逡ｪ迺ｰ蠅・〒縺ｯ蜑企勁縺ｾ縺溘・繧ｳ繝｡繝ｳ繝医い繧ｦ繝茨ｼ・os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

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
    """繝・・繧ｿ繝吶・繧ｹ繧貞・譛溷喧縺吶ｋ"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 繝・・繝悶Ν菴懈・
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
    
    # 繧ｵ繝ｳ繝励Ν繝・・繧ｿ縺ｮ謖ｿ蜈･
    c.execute("SELECT COUNT(*) FROM engineers")
    if c.fetchone()[0] == 0:
        # 繧ｵ繝ｳ繝励Ν繧ｨ繝ｳ繧ｸ繝九い
        c.execute('''
        INSERT INTO engineers (name, email, current_role, location, experience_years)
        VALUES (?, ?, ?, ?, ?)
        ''', ('螻ｱ逕ｰ螟ｪ驛・, 'yamada@example.com', '繧ｷ繝九い繧ｨ繝ｳ繧ｸ繝九い', '譚ｱ莠ｬ', 8.5))
        
        engineer_id = c.lastrowid
        
        # 繧ｹ繧ｭ繝ｫ
        c.executemany('''
        INSERT INTO skills (engineer_id, name, level) VALUES (?, ?, ?)
        ''', [
            (engineer_id, 'Python', 'expert'),
            (engineer_id, 'JavaScript', 'intermediate')
        ])
        
        # 繝励Ο繧ｸ繧ｧ繧ｯ繝・        c.execute('''
        INSERT INTO projects (name, client_name, description, location, work_type, duration_months, min_budget, max_budget)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('EC繧ｵ繧､繝磯幕逋ｺ', '譬ｪ蠑丈ｼ夂､ｾABC', '螟ｧ謇句ｰ丞｣ｲ讌ｭ蜷代￠EC繧ｵ繧､繝医・髢狗匱', '譚ｱ莠ｬ', '繝ｪ繝｢繝ｼ繝亥庄', 6, 5000000, 8000000))
        
        project_id = c.lastrowid
        
        # 繝励Ο繧ｸ繧ｧ繧ｯ繝郁ｦ∽ｻｶ
        c.executemany('''
        INSERT INTO project_requirements (project_id, skill, level, weight) VALUES (?, ?, ?, ?)
        ''', [
            (project_id, 'Python', 'expert', 3),
            (project_id, 'JavaScript', 'intermediate', 2)
        ])
    
    conn.commit()
    conn.close()

# 繧｢繝・・繝ｭ繝ｼ繝芽ｨｭ螳・UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
DB_FILE = 'database.db'
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB 蛻ｶ髯・
# 繧｢繝・・繝ｭ繝ｼ繝峨ヵ繧ｩ繝ｫ繝縺悟ｭ伜惠縺吶ｋ縺狗｢ｺ隱・os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ縺ｮ蛻晄悄蛹・app = Flask(__name__)
# 繧ｻ繧ｭ繝･繧｢縺ｪ繧ｻ繝・す繝ｧ繝ｳ險ｭ螳・app.secret_key = os.urandom(24)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600,  # 1譎る俣
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=MAX_FILE_SIZE,
    SQLALCHEMY_DATABASE_URI=f'sqlite:///{DB_FILE}',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# 繝ｭ繧ｮ繝ｳ繧ｰ縺ｮ險ｭ螳・import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# CORS縺ｨCSP縺ｮ險ｭ螳・CORS(app)  # CORS繧呈怏蜉ｹ蛹・
# Gmail隱崎ｨｼ迥ｶ諷九ｒ遒ｺ隱阪☆繧矩未謨ｰ
def check_gmail_auth():
    """Gmail隱崎ｨｼ迥ｶ諷九ｒ遒ｺ隱阪＠縲∬ｪ崎ｨｼ縺輔ｌ縺ｦ縺・↑縺・ｴ蜷医・False繧定ｿ斐☆"""
    if 'credentials' not in session:
        app.logger.debug("No credentials in session")
        return False
    
    try:
        # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ隱崎ｨｼ諠・ｱ繧貞ｾｩ蜈・        creds_dict = session['credentials']
        
        # 譛牙柑譛滄剞繧壇atetime繧ｪ繝悶ず繧ｧ繧ｯ繝医↓螟画鋤
        if 'expiry' in creds_dict and isinstance(creds_dict['expiry'], str):
            creds_dict['expiry'] = datetime.fromisoformat(creds_dict['expiry'])
        
        credentials = Credentials(**creds_dict)
        
        # 繝医・繧ｯ繝ｳ縺ｮ譛牙柑譛滄剞繧堤｢ｺ隱搾ｼ・0蛻・ｻ･蜀・↓蛻・ｌ繧句ｴ蜷医・繝ｪ繝輔Ξ繝・す繝･繧定ｩｦ縺ｿ繧具ｼ・        if credentials.expired or (credentials.expiry and 
                                 (credentials.expiry - datetime.utcnow().replace(tzinfo=timezone.utc)).total_seconds() < 600):
            app.logger.info("Token expired or about to expire, attempting to refresh...")
            if credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    # 譖ｴ譁ｰ縺励◆隱崎ｨｼ諠・ｱ繧偵そ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ・                    session['credentials'] = {
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

# 隱崎ｨｼ縺悟ｿ・ｦ√↑繝ｫ繝ｼ繝医・繝溘ラ繝ｫ繧ｦ繧ｧ繧｢
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 隱崎ｨｼ荳崎ｦ√↑繝代せ縺ｯ繧ｹ繧ｭ繝・・
        if request.path in ['/', '/gmail/auth', '/gmail/auth/callback', '/api/auth/status']:
            return f(*args, **kwargs)
            
        # 隱崎ｨｼ迥ｶ諷九ｒ遒ｺ隱・        if not check_gmail_auth():
            # 迴ｾ蝨ｨ縺ｮURL繧偵そ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ・            session['next'] = request.url
            return redirect(url_for('gmail_auth'))
        return f(*args, **kwargs)
    return decorated_function

# 繧ｻ繧ｭ繝･繝ｪ繝・ぅ繝倥ャ繝繝ｼ繧定ｿｽ蜉縺吶ｋ繝溘ラ繝ｫ繧ｦ繧ｧ繧｢
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Content Security Policy (CSP) 縺ｮ險ｭ螳・    csp_policy = """
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

# 繧ｹ繧ｭ繝ｫ繝槭ャ繝√Ε繝ｼ繧貞・譛溷喧
skill_matcher = SkillMatcher()

# 繧ｹ繧ｭ繝ｫ繝槭ャ繝斐Φ繧ｰ・井ｺ呈鋤諤ｧ縺ｮ縺溘ａ谿九☆・・SKILL_KEYWORDS = list(skill_matcher.skill_normalization_map.keys())
    'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Terraform', 'Ansible',
    'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch',
    '讖滓｢ｰ蟄ｦ鄙・, '豺ｱ螻､蟄ｦ鄙・, '繝・・繧ｿ蛻・梵', '繝・・繧ｿ繝吶・繧ｹ', 'API髢狗匱', '繧ｻ繧ｭ繝･繝ｪ繝・ぅ',
    '繝・せ繝・, 'CI/CD', 'DevOps', '繧｢繧ｸ繝｣繧､繝ｫ', '繧ｹ繧ｯ繝ｩ繝', 'Git', 'GitHub', 'GitLab', 'Bitbucket'
]

def extract_text_from_pdf(file_path: str) -> str:
    """
    PDF繝輔ぃ繧､繝ｫ縺九ｉ繝・く繧ｹ繝医ｒ謚ｽ蜃ｺ縺吶ｋ
    
    Args:
        file_path (str): 謚ｽ蜃ｺ縺吶ｋPDF繝輔ぃ繧､繝ｫ縺ｮ繝代せ
        
    Returns:
        str: 謚ｽ蜃ｺ縺輔ｌ縺溘ユ繧ｭ繧ｹ繝・        
    Raises:
        Exception: 繝輔ぃ繧､繝ｫ縺ｮ隱ｭ縺ｿ霎ｼ縺ｿ繧・ユ繧ｭ繧ｹ繝域歓蜃ｺ縺ｫ螟ｱ謨励＠縺溷ｴ蜷・    """
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ''
            
            # 繝代せ繝ｯ繝ｼ繝峨〒菫晁ｭｷ縺輔ｌ縺蘖DF縺ｮ蜃ｦ逅・            if reader.is_encrypted:
                try:
                    # 遨ｺ縺ｮ繝代せ繝ｯ繝ｼ繝峨〒隧ｦ陦・                    reader.decrypt('')
                except:
                    # 繝代せ繝ｯ繝ｼ繝峨′蠢・ｦ√↑蝣ｴ蜷医・繧ｨ繝ｩ繝ｼ繧偵せ繝ｭ繝ｼ
                    raise Exception('繝代せ繝ｯ繝ｼ繝峨〒菫晁ｭｷ縺輔ｌ縺蘖DF縺ｮ縺溘ａ縲√ユ繧ｭ繧ｹ繝医ｒ謚ｽ蜃ｺ縺ｧ縺阪∪縺帙ｓ')
            
            # 蜷・・繝ｼ繧ｸ縺九ｉ繝・く繧ｹ繝医ｒ謚ｽ蜃ｺ
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
            
            # 繝・く繧ｹ繝医′遨ｺ縺ｮ蝣ｴ蜷医・繧ｨ繝ｩ繝ｼ繧偵せ繝ｭ繝ｼ
            if not text.strip():
                raise Exception('PDF縺九ｉ繝・く繧ｹ繝医ｒ謚ｽ蜃ｺ縺ｧ縺阪∪縺帙ｓ縺ｧ縺励◆縲ら判蜒上・縺ｿ縺ｮPDF縺ｮ蜿ｯ閭ｽ諤ｧ縺後≠繧翫∪縺吶・)
                
            return text
            
    except Exception as e:
        raise Exception(f'PDF縺ｮ蜃ｦ逅・ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}')

def extract_text_from_docx(file_path: str) -> str:
    """
    Word譁・嶌(.docx, .doc)縺九ｉ繝・く繧ｹ繝医ｒ謚ｽ蜃ｺ縺吶ｋ
    
    Args:
        file_path (str): 謚ｽ蜃ｺ縺吶ｋWord繝輔ぃ繧､繝ｫ縺ｮ繝代せ
        
    Returns:
        str: 謚ｽ蜃ｺ縺輔ｌ縺溘ユ繧ｭ繧ｹ繝・        
    Raises:
        Exception: 繝輔ぃ繧､繝ｫ縺ｮ隱ｭ縺ｿ霎ｼ縺ｿ繧・ユ繧ｭ繧ｹ繝域歓蜃ｺ縺ｫ螟ｱ謨励＠縺溷ｴ蜷・    """
    try:
        import docx2txt
        
        # 繝輔ぃ繧､繝ｫ縺悟ｭ伜惠縺吶ｋ縺狗｢ｺ隱・        if not os.path.exists(file_path):
            raise FileNotFoundError('謖・ｮ壹＆繧後◆繝輔ぃ繧､繝ｫ縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ')
            
        # 繝輔ぃ繧､繝ｫ諡｡蠑ｵ蟄舌ｒ遒ｺ隱・        _, ext = os.path.splitext(file_path)
        if ext.lower() not in ['.docx', '.doc']:
            raise ValueError('繧ｵ繝昴・繝医＆繧後※縺・↑縺・ヵ繧｡繧､繝ｫ蠖｢蠑上〒縺・)
            
        # 繝・く繧ｹ繝医ｒ謚ｽ蜃ｺ
        text = docx2txt.process(file_path)
        
        # 繝・く繧ｹ繝医′遨ｺ縺ｮ蝣ｴ蜷医・繧ｨ繝ｩ繝ｼ繧偵せ繝ｭ繝ｼ
        if not text or not text.strip():
            raise Exception('繝峨く繝･繝｡繝ｳ繝医°繧峨ユ繧ｭ繧ｹ繝医ｒ謚ｽ蜃ｺ縺ｧ縺阪∪縺帙ｓ縺ｧ縺励◆')
            
        return text
        
    except ImportError:
        raise ImportError('docx2txt繝ｩ繧､繝悶Λ繝ｪ縺後う繝ｳ繧ｹ繝医・繝ｫ縺輔ｌ縺ｦ縺・∪縺帙ｓ縲Ａpip install docx2txt`繧貞ｮ溯｡後＠縺ｦ繧､繝ｳ繧ｹ繝医・繝ｫ縺励※縺上□縺輔＞縲・)
    except Exception as e:
        raise Exception(f'Word譁・嶌縺ｮ蜃ｦ逅・ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}')

from skill_extractor import SkillExtractor

def analyze_resume(text: str) -> Dict[str, Any]:
    """
    繝ｬ繧ｸ繝･繝｡繧貞・譫舌＠縺ｦ繧ｹ繧ｭ繝ｫ繧呈歓蜃ｺ縺吶ｋ
    
    Args:
        text: 繝ｬ繧ｸ繝･繝｡縺ｮ繝・く繧ｹ繝・        
    Returns:
        蛻・梵邨先棡縺ｮ霎樊嶌
        {
            'skills': {
                '繧ｫ繝・ざ繝ｪ蜷・: [
                    {
                        'name': '繧ｹ繧ｭ繝ｫ蜷・,
                        'importance': 0.0-1.0縺ｮ驥崎ｦ∝ｺｦ繧ｹ繧ｳ繧｢,
                        'experience': 邨碁ｨ灘ｹｴ謨ｰ・医≠繧後・・・
                        'context': '繧ｹ繧ｭ繝ｫ縺梧､懷・縺輔ｌ縺滓枚閼・,
                        'categories': ['髢｢騾｣繧ｫ繝・ざ繝ｪ1', '髢｢騾｣繧ｫ繝・ざ繝ｪ2'],
                        'related_skills': ['髢｢騾｣繧ｹ繧ｭ繝ｫ1', '髢｢騾｣繧ｹ繧ｭ繝ｫ2']
                    },
                    ...
                ],
                ...
            },
            'summary': {
                'total_skills': 邱上せ繧ｭ繝ｫ謨ｰ,
                'categories': 繧ｫ繝・ざ繝ｪ謨ｰ,
                'top_skills': [
                    {'name': '繧ｹ繧ｭ繝ｫ蜷・, 'importance': 驥崎ｦ∝ｺｦ},
                    ...
                ]
            },
            'status': 'success|error',
            'error': '繧ｨ繝ｩ繝ｼ繝｡繝・そ繝ｼ繧ｸ・医お繝ｩ繝ｼ譎ゅ・縺ｿ・・
        }
    """
    if not text:
        return {
            "status": "error",
            "error": "繝・く繧ｹ繝医′遨ｺ縺ｧ縺・
        }
    
    try:
        # 繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ
        skills = extract_skills(text)
        
        # 繧ｵ繝槭Μ繝ｼ諠・ｱ繧堤函謌・        total_skills = sum(len(skills[cat]) for cat in skills)
        category_count = len(skills)
        
        # 繝医ャ繝励せ繧ｭ繝ｫ繧呈歓蜃ｺ・磯㍾隕∝ｺｦ鬆・↓譛螟ｧ5縺､・・        all_skills = []
        for category, skill_list in skills.items():
            for skill in skill_list:
                all_skills.append({
                    'name': skill['name'],
                    'importance': skill.get('importance', 0),
                    'category': category
                })
        
        # 驥崎ｦ∝ｺｦ縺ｧ繧ｽ繝ｼ繝・        top_skills = sorted(all_skills, key=lambda x: x['importance'], reverse=True)[:5]
        
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
        error_msg = f"繝ｬ繧ｸ繝･繝｡蛻・梵荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}"
        print(error_msg)
        return {
            "status": "error",
            "error": error_msg
        }

def extract_skills(text: str) -> Dict[str, List[Dict]]:
    """
    繝・く繧ｹ繝医°繧峨せ繧ｭ繝ｫ繧呈歓蜃ｺ縺吶ｋ
    
    Args:
        text: 謚ｽ蜃ｺ蟇ｾ雎｡縺ｮ繝・く繧ｹ繝・        
    Returns:
        繧ｫ繝・ざ繝ｪ蛻･縺ｮ繧ｹ繧ｭ繝ｫ諠・ｱ繧貞性繧霎樊嶌
        {
            '繧ｫ繝・ざ繝ｪ蜷・: [
                {
                    'name': '繧ｹ繧ｭ繝ｫ蜷・,
                    'importance': 0.0-1.0縺ｮ驥崎ｦ∝ｺｦ繧ｹ繧ｳ繧｢,
                    'experience': 邨碁ｨ灘ｹｴ謨ｰ・医≠繧後・・・
                    'context': '繧ｹ繧ｭ繝ｫ縺梧､懷・縺輔ｌ縺滓枚閼・,
                    'categories': ['髢｢騾｣繧ｫ繝・ざ繝ｪ1', '髢｢騾｣繧ｫ繝・ざ繝ｪ2'],
                    'related_skills': ['髢｢騾｣繧ｹ繧ｭ繝ｫ1', '髢｢騾｣繧ｹ繧ｭ繝ｫ2']
                },
                ...
            ],
            ...
            '縺昴・莉・: []
        }
    """
    print("\n=== 繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ繧帝幕蟋九＠縺ｾ縺・===")
    print(f"蜈･蜉帙ユ繧ｭ繧ｹ繝磯聞: {len(text)}譁・ｭ・)
    
    if not text:
        print("繧ｨ繝ｩ繝ｼ: 繝・く繧ｹ繝医′遨ｺ縺ｧ縺・)
        return {}
    
    # 繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ繝｢繧ｸ繝･繝ｼ繝ｫ縺ｮ蛻晄悄蛹・    print("繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ繝｢繧ｸ繝･繝ｼ繝ｫ繧貞・譛溷喧荳ｭ...")
    extractor = SkillExtractor()
    
    try:
        # 繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ繧貞ｮ溯｡・        print("繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ繧貞ｮ溯｡御ｸｭ...")
        skills = extractor.extract_skills(text)
        
        if not skills:
            print("隴ｦ蜻・ 謚ｽ蜃ｺ縺輔ｌ縺溘せ繧ｭ繝ｫ縺後≠繧翫∪縺帙ｓ")
            return {}
            
        print(f"謚ｽ蜃ｺ縺輔ｌ縺溘せ繧ｭ繝ｫ繧ｫ繝・ざ繝ｪ謨ｰ: {len(skills)}")
        
        # 邨先棡繧偵ヵ繧ｩ繝ｼ繝槭ャ繝・        print("繧ｹ繧ｭ繝ｫ諠・ｱ繧偵ヵ繧ｩ繝ｼ繝槭ャ繝井ｸｭ...")
        formatted_skills = {}
        for category, skill_list in skills.items():
            print(f"繧ｫ繝・ざ繝ｪ '{category}': {len(skill_list)}繧ｹ繧ｭ繝ｫ")
            formatted_skills[category] = []
            
            for skill in skill_list:
                try:
                    formatted_skill = {
                        'name': skill.get('name', skill.get('skill', '荳肴・縺ｪ繧ｹ繧ｭ繝ｫ')),  # 荳｡譁ｹ縺ｮ繧ｭ繝ｼ繧堤｢ｺ隱・                        'importance': float(skill.get('importance', 0.5)),
                        'experience': skill.get('experience', skill.get('experience_years')),  # 荳｡譁ｹ縺ｮ繧ｭ繝ｼ繧堤｢ｺ隱・                        'context': skill.get('context', ''),
                        'categories': skill.get('categories', []),
                        'related_skills': skill.get('related_skills', [])
                    }
                    formatted_skills[category].append(formatted_skill)
                    print(f"  - 繧ｹ繧ｭ繝ｫ: {formatted_skill['name']}, 驥崎ｦ∝ｺｦ: {formatted_skill['importance']}")
                except Exception as e:
                    print(f"繧ｹ繧ｭ繝ｫ縺ｮ繝輔か繝ｼ繝槭ャ繝井ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}")
                    print(f"蝠城｡後・繧ｹ繧ｭ繝ｫ繝・・繧ｿ: {skill}")
        
        # 邨先棡縺ｮ繧ｵ繝槭Μ繝ｼ繧定｡ｨ遉ｺ
        total_skills = sum(len(skills) for skills in formatted_skills.values())
        print(f"\n=== 繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ螳御ｺ・===")
        print(f"蜷郁ｨ医せ繧ｭ繝ｫ謨ｰ: {total_skills}")
        for category, skills in formatted_skills.items():
            print(f"{category}: {len(skills)}繧ｹ繧ｭ繝ｫ")
        
        return formatted_skills
        
    except Exception as e:
        import traceback
        error_msg = f"繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {}   

def analyze_resume(file_path: str) -> Dict:
    """繧ｹ繧ｭ繝ｫ繧ｷ繝ｼ繝医ｒ隗｣譫舌＠縺ｦ繧ｹ繧ｭ繝ｫ繧呈歓蜃ｺ縺吶ｋ"""
    print("\n=== 繝ｬ繧ｸ繝･繝｡隗｣譫舌ｒ髢句ｧ九＠縺ｾ縺・===")
    print(f"隗｣譫仙ｯｾ雎｡繝輔ぃ繧､繝ｫ: {file_path}")
    
    file_extension = Path(file_path).suffix.lower()
    print(f"繝輔ぃ繧､繝ｫ諡｡蠑ｵ蟄・ {file_extension}")
    
    try:
        # 繝輔ぃ繧､繝ｫ縺ｮ蟄伜惠遒ｺ隱・        if not os.path.exists(file_path):
            error_msg = f"繧ｨ繝ｩ繝ｼ: 繝輔ぃ繧､繝ｫ縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ: {file_path}"
            print(error_msg)
            return {'status': 'error', 'message': error_msg}
        
        # 繝輔ぃ繧､繝ｫ繧ｵ繧､繧ｺ縺ｮ遒ｺ隱搾ｼ・0MB莉･荳具ｼ・        file_size = os.path.getsize(file_path)
        print(f"繝輔ぃ繧､繝ｫ繧ｵ繧､繧ｺ: {file_size} 繝舌う繝・)
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            error_msg = f"繧ｨ繝ｩ繝ｼ: 繝輔ぃ繧､繝ｫ繧ｵ繧､繧ｺ縺悟､ｧ縺阪☆縺弱∪縺呻ｼ・file_size/1024/1024:.2f}MB > 10MB・・
            print(error_msg)
            return {'status': 'error', 'message': error_msg}
        
        # 繝輔ぃ繧､繝ｫ縺ｮ遞ｮ鬘槭↓蠢懊§縺ｦ繝・く繧ｹ繝域歓蜃ｺ
        text = ""
        try:
            print(f"繝輔ぃ繧､繝ｫ縺九ｉ繝・く繧ｹ繝医ｒ謚ｽ蜃ｺ荳ｭ...")
            if file_extension == '.pdf':
                print("PDF繝輔ぃ繧､繝ｫ繧貞・逅・ｸｭ...")
                text = extract_text_from_pdf(file_path)
            elif file_extension in ['.docx', '.doc']:
                print("Word繝輔ぃ繧､繝ｫ繧貞・逅・ｸｭ...")
                text = extract_text_from_docx(file_path)
            else:
                error_msg = f"繧ｨ繝ｩ繝ｼ: 繧ｵ繝昴・繝医＆繧後※縺・↑縺・ヵ繧｡繧､繝ｫ蠖｢蠑上〒縺・ {file_extension}"
                print(error_msg)
                return {'status': 'error', 'message': error_msg}
            
            # 繝・く繧ｹ繝医′遨ｺ縺ｧ縺ｪ縺・°遒ｺ隱・            if not text or not text.strip():
                error_msg = "繧ｨ繝ｩ繝ｼ: 繝輔ぃ繧､繝ｫ縺九ｉ繝・く繧ｹ繝医ｒ謚ｽ蜃ｺ縺ｧ縺阪∪縺帙ｓ縺ｧ縺励◆"
                print(error_msg)
                return {'status': 'error', 'message': error_msg}
                
            print(f"謚ｽ蜃ｺ縺輔ｌ縺溘ユ繧ｭ繧ｹ繝医・髟ｷ縺・ {len(text)} 譁・ｭ・)
            print("謚ｽ蜃ｺ縺輔ｌ縺溘ユ繧ｭ繧ｹ繝医・蜈磯ｭ100譁・ｭ・", text[:100] + ("..." if len(text) > 100 else ""))
                
        except Exception as e:
            import traceback
            error_msg = f"繝輔ぃ繧､繝ｫ縺ｮ隗｣譫蝉ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {'status': 'error', 'message': f'繝輔ぃ繧､繝ｫ縺ｮ隗｣譫蝉ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'}
        
        # 繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ
        try:
            print("\n繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ繧帝幕蟋九＠縺ｾ縺・..")
            skills = extract_skills(text)
            
            if not skills:
                print("隴ｦ蜻・ 繧ｹ繧ｭ繝ｫ縺・縺､繧よ歓蜃ｺ縺輔ｌ縺ｾ縺帙ｓ縺ｧ縺励◆")
                return {
                    'status': 'success',
                    'file_type': file_extension,
                    'text_length': len(text),
                    'skills': {},
                    'extracted_text': text[:1000] + ('...' if len(text) > 1000 else '')
                }
            
            # 謚ｽ蜃ｺ縺輔ｌ縺溘せ繧ｭ繝ｫ縺ｮ邨ｱ險域ュ蝣ｱ繧定｡ｨ遉ｺ
            total_skills = sum(len(skills) for skills in skills.values())
            print(f"\n=== 繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ螳御ｺ・===")
            print(f"蜷郁ｨ医せ繧ｭ繝ｫ謨ｰ: {total_skills}")
            for category, skill_list in skills.items():
                print(f"{category}: {len(skill_list)}繧ｹ繧ｭ繝ｫ")
            
            result = {
                'status': 'success',
                'file_type': file_extension,
                'text_length': len(text),
                'skills': skills,
                'extracted_text': text[:1000] + ('...' if len(text) > 1000 else '')  # 繝励Ξ繝薙Η繝ｼ逕ｨ縺ｫ譛蛻昴・1000譁・ｭ励ｒ霑斐☆
            }
            
            return result
            
        except Exception as e:
            import traceback
            error_msg = f"繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return {'status': 'error', 'message': f'繧ｹ繧ｭ繝ｫ謚ｽ蜃ｺ荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'}
            
    except Exception as e:
        import traceback
        error_msg = f"繝ｬ繧ｸ繝･繝｡隗｣譫蝉ｸｭ縺ｫ莠域悄縺帙〓繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {'status': 'error', 'message': f'繝ｬ繧ｸ繝･繝｡隗｣譫蝉ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'}
        return {'status': 'error', 'message': f'莠域悄縺帙〓繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'}

# 繝・・繧ｿ繝吶・繧ｹ蛻晄悄蛹・with app.app_context():
    if not os.path.exists(DB_FILE):
        init_db()

# 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ邨ゆｺ・凾縺ｫ繝・・繧ｿ繝吶・繧ｹ謗･邯壹ｒ髢峨§繧・app.teardown_appcontext(close_db)

# 繝ｫ繝ｼ繝・RL
@app.route('/')
def index():
    # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ隱崎ｨｼ迥ｶ諷九ｒ遒ｺ隱・    is_authenticated = False
    
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
            
            # 繝医・繧ｯ繝ｳ縺ｮ譛牙柑譛滄剞繧堤｢ｺ隱・            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # 譁ｰ縺励＞繝医・繧ｯ繝ｳ縺ｧ繧ｻ繝・す繝ｧ繝ｳ繧呈峩譁ｰ
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
                    app.logger.error(f"繝医・繧ｯ繝ｳ縺ｮ譖ｴ譁ｰ縺ｫ螟ｱ謨励＠縺ｾ縺励◆: {refresh_error}")
                    session.pop('credentials', None)
            else:
                is_authenticated = True
                
        except Exception as e:
            app.logger.error(f"隱崎ｨｼ諠・ｱ縺ｮ隱ｭ縺ｿ霎ｼ縺ｿ繧ｨ繝ｩ繝ｼ: {e}")
            session.pop('credentials', None)
    
    return render_template('index.html', is_authenticated=is_authenticated)

# 繧｢繝・・繝ｭ繝ｼ繝峨ｒ險ｱ蜿ｯ縺吶ｋ諡｡蠑ｵ蟄・def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 髱咏噪繝輔ぃ繧､繝ｫ縺ｮ繝ｫ繝ｼ繝・ぅ繝ｳ繧ｰ
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# 繝輔ぃ繧､繝ｫ繧｢繝・・繝ｭ繝ｼ繝峨・繝ｼ繧ｸ縺ｮ陦ｨ遉ｺ
@app.route('/upload')
def upload_page():
    # 隱崎ｨｼ迥ｶ諷九ｒ遒ｺ隱・    is_authenticated = os.path.exists('token.pickle')
    return render_template('upload.html', is_authenticated=is_authenticated)

# 繝輔ぃ繧､繝ｫ繧｢繝・・繝ｭ繝ｼ繝臥畑縺ｮAPI繧ｨ繝ｳ繝峨・繧､繝ｳ繝・@app.route('/api/upload', methods=['POST'])
def upload_file():
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': '繝輔ぃ繧､繝ｫ縺碁∈謚槭＆繧後※縺・∪縺帙ｓ'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '繝輔ぃ繧､繝ｫ縺碁∈謚槭＆繧後※縺・∪縺帙ｓ'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'status': 'error', 'message': '險ｱ蜿ｯ縺輔ｌ縺ｦ縺・↑縺・ヵ繧｡繧､繝ｫ蠖｢蠑上〒縺・}), 400
    
    try:
        filename = secure_filename(file.filename)
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 繝輔ぃ繧､繝ｫ繧ｵ繧､繧ｺ縺ｮ讀懆ｨｼ・・6MB蛻ｶ髯撰ｼ・        if os.path.getsize(filepath) > app.config['MAX_CONTENT_LENGTH']:
            os.remove(filepath)  # 蛻ｶ髯舌ｒ雜・∴縺溘ヵ繧｡繧､繝ｫ縺ｯ蜑企勁
            return jsonify({
                'status': 'error',
                'message': f'繝輔ぃ繧､繝ｫ繧ｵ繧､繧ｺ縺悟､ｧ縺阪☆縺弱∪縺吶よ怙螟ｧ{app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)}MB縺ｾ縺ｧ縺ｮ繝輔ぃ繧､繝ｫ繧偵い繝・・繝ｭ繝ｼ繝峨〒縺阪∪縺吶・
            }), 400
        
        analysis_result = analyze_resume(filepath)
        
        if analysis_result.get('status') == 'error':
            return jsonify({
                'status': 'error',
                'message': analysis_result.get('message', '繝輔ぃ繧､繝ｫ縺ｮ隗｣譫蝉ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆')
            }), 400
            
        # 繧ｹ繧ｭ繝ｫ諠・ｱ繧偵そ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ・        if 'skills' in analysis_result:
            session['user_skills'] = analysis_result['skills']
        
        response = jsonify({
            'status': 'success',
            'message': '繝輔ぃ繧､繝ｫ縺ｮ繧｢繝・・繝ｭ繝ｼ繝峨→隗｣譫舌′螳御ｺ・＠縺ｾ縺励◆',
            'filename': filename,
            'skills': analysis_result.get('skills', []),
            'extracted_text': analysis_result.get('extracted_text', '')
        })
        
        return response
        
    except Exception as e:
        # 繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺溷ｴ蜷医√い繝・・繝ｭ繝ｼ繝峨＆繧後◆繝輔ぃ繧､繝ｫ繧貞炎髯､
        if 'filepath' in locals() and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
                
        return jsonify({
            'status': 'error',
            'message': f'繝輔ぃ繧､繝ｫ縺ｮ蜃ｦ逅・ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'
        }), 500

# Gmail讀懃ｴ｢逕ｨ縺ｮ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・@app.route('/search_gmail', methods=['POST'])
def search_gmail():
    # 繝ｪ繧ｯ繧ｨ繧ｹ繝医°繧画､懃ｴ｢繧ｯ繧ｨ繝ｪ繧貞叙蠕・    data = request.get_json()
    query = data.get('query', '')
    max_results = data.get('maxResults', 10)
    
    # Gmail繧ｵ繝ｼ繝薙せ繧貞叙蠕・    service = get_gmail_service()
    if not service:
        return jsonify({'status': 'error', 'message': 'Gmail繧ｵ繝ｼ繝薙せ縺ｫ謗･邯壹〒縺阪∪縺帙ｓ縲りｪ崎ｨｼ縺悟ｿ・ｦ√〒縺吶・}), 401
    
    try:
        # 迴ｾ蝨ｨ縺ｮ譌･莉倥→2譌･蜑阪・譌･莉倥ｒ蜿門ｾ・        from datetime import datetime, timedelta
        now = datetime.utcnow()
        two_days_ago = now - timedelta(days=2)
        
        # 譌･莉倥ｒRFC 2822蠖｢蠑上↓螟画鋤
        date_query = f'after:{two_days_ago.strftime("%Y/%m/%d")}'
        
        # 讀懃ｴ｢繧ｯ繧ｨ繝ｪ繧呈ｧ狗ｯ会ｼ・ales@artwize.co.jp螳帙※縺ｧ縲・℃蜴ｻ2譌･髢薙∵ｷｻ莉倥ヵ繧｡繧､繝ｫ縺ｪ縺暦ｼ・        full_query = f'to:sales@artwize.co.jp {date_query} {query} has:nouserlabels -has:attachment'
        
        # 繝｡繝・そ繝ｼ繧ｸ繧呈､懃ｴ｢
        results = service.users().messages().list(
            userId='me',
            q=full_query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        # 蜷・Γ繝・そ繝ｼ繧ｸ縺ｮ隧ｳ邏ｰ繧貞叙蠕・        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date', 'To']
                ).execute()
                
                # 繝｡繧ｿ繝・・繧ｿ縺九ｉ蠢・ｦ√↑諠・ｱ繧呈歓蜃ｺ
                headers = {}
                for header in message.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 豺ｻ莉倥ヵ繧｡繧､繝ｫ縺ｮ譛臥┌繧堤｢ｺ隱搾ｼ医ｈ繧顔｢ｺ螳溘↑譁ｹ豕包ｼ・                has_attachments = False
                
                # 1. 繝｡繝・そ繝ｼ繧ｸ縺ｮ豺ｻ莉倥ヵ繧｡繧､繝ｫ繧堤峩謗･遒ｺ隱・                if 'filename' in message.get('payload', {}) and message['payload']['filename']:
                    has_attachments = True
                
                # 2. 繝代・繝・ｒ蜀榊ｸｰ逧・↓繝√ぉ繝・け
                def check_parts(part):
                    if not part:
                        return False
                        
                    # 豺ｻ莉倥ヵ繧｡繧､繝ｫ縺ｨ縺励※謇ｱ縺・IME繧ｿ繧､繝・                    attachment_mime_types = {
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
                    
                    # 繝輔ぃ繧､繝ｫ蜷阪′縺ゅｋ蝣ｴ蜷医√∪縺溘・豺ｻ莉倥ヵ繧｡繧､繝ｫ縺ｨ縺励※謇ｱ縺・IME繧ｿ繧､繝励・蝣ｴ蜷・                    if (part.get('filename') and part['filename']) or \
                       (part.get('mimeType') and part['mimeType'] in attachment_mime_types):
                        return True
                        
                    # 繝阪せ繝医＆繧後◆繝代・繝・ｒ遒ｺ隱・                    for sub_part in part.get('parts', []):
                        if check_parts(sub_part):
                            return True
                            
                    return False
                
                # 繝｡繝・そ繝ｼ繧ｸ縺ｮ蜈ｨ繝代・繝・ｒ繝√ぉ繝・け
                if not has_attachments and 'parts' in message.get('payload', {}):
                    has_attachments = check_parts(message['payload'])
                
                # 豺ｻ莉倥ヵ繧｡繧､繝ｫ縺後≠繧句ｴ蜷医・繧ｹ繧ｭ繝・・
                if has_attachments:
                    print(f"豺ｻ莉倥ヵ繧｡繧､繝ｫ縺後≠繧九Γ繝ｼ繝ｫ繧偵せ繧ｭ繝・・縺励∪縺励◆: {message['id']}")
                    print(f"莉ｶ蜷・ {headers.get('subject', '(莉ｶ蜷阪↑縺・')}")
                    print(f"騾∽ｿ｡閠・ {headers.get('from', '騾∽ｿ｡閠・ｸ肴・')}")
                    print("-" * 50)
                    continue
                
                # 蜿嶺ｿ｡譌･譎ゅｒ繝輔か繝ｼ繝槭ャ繝・                email_date = headers.get('date', '')
                try:
                    from email.utils import parsedate_to_datetime
                    email_date = parsedate_to_datetime(email_date).strftime('%Y-%m-%d %H:%M:%S')
                except (TypeError, ValueError):
                    pass
                
                email_data = {
                    'id': message['id'],
                    'subject': headers.get('subject', '(莉ｶ蜷阪↑縺・'),
                    'from': headers.get('from', '騾∽ｿ｡閠・ｸ肴・'),
                    'to': headers.get('to', ''),
                    'snippet': message.get('snippet', ''),
                    'date': email_date,
                    'has_attachments': has_attachments
                }
                emails.append(email_data)
                
            except Exception as e:
                print(f"繝｡繝・そ繝ｼ繧ｸ縺ｮ蜿門ｾ嶺ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {e}")
                continue
        
        return jsonify({
            'status': 'success',
            'emails': emails
        })
        
    except Exception as e:
        app.logger.error(f"Gmail讀懃ｴ｢荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {e}")
        return jsonify({
            'status': 'error',
            'message': f'繝｡繝ｼ繝ｫ縺ｮ讀懃ｴ｢荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'
        }), 500

import secrets
from datetime import datetime
from functools import wraps
from flask import url_for, redirect, session, request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Gmail隱崎ｨｼ逕ｨ縺ｮ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・@app.route('/gmail/auth')
def gmail_auth():
    # 譌｢縺ｫ隱崎ｨｼ貂医∩縺ｧ譛牙柑縺ｪ繝医・繧ｯ繝ｳ縺後≠繧句ｴ蜷医・繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ縺ｫ繝ｪ繝繧､繝ｬ繧ｯ繝・    if 'credentials' in session:
        try:
            creds = Credentials(
                token=session['credentials']['token'],
                refresh_token=session['credentials']['refresh_token'],
                token_uri=session['credentials']['token_uri'],
                client_id=session['credentials']['client_id'],
                client_secret=session['credentials']['client_secret'],
                scopes=session['credentials']['scopes']
            )
            
            # 繝医・繧ｯ繝ｳ縺ｮ譛牙柑譛滄剞繧偵メ繧ｧ繝・け
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # 譁ｰ縺励＞繝医・繧ｯ繝ｳ縺ｧ繧ｻ繝・す繝ｧ繝ｳ繧呈峩譁ｰ
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
            
            # 譌｢縺ｫ隱崎ｨｼ貂医∩縺ｮ蝣ｴ蜷医・繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ縺ｫ繝ｪ繝繧､繝ｬ繧ｯ繝・            app.logger.info("Already authenticated, redirecting to projects")
            return redirect(url_for('get_projects'))
            
        except Exception as e:
            app.logger.warning(f"Existing token validation failed: {str(e)}")
            # 繝医・繧ｯ繝ｳ縺檎┌蜉ｹ縺ｪ蝣ｴ蜷医・繧ｻ繝・す繝ｧ繝ｳ縺九ｉ蜑企勁
            session.pop('credentials', None)
    
    # 繝ｪ繝輔ぃ繝ｩ・亥・縺ｮ繝壹・繧ｸ・峨ｒ繧ｻ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ・    referrer = request.referrer or url_for('get_projects')
    session['next'] = referrer
    
    try:
        app.logger.debug("Starting Gmail authentication process")
        # 繝ｪ繝繧､繝ｬ繧ｯ繝・RI繧呈・遉ｺ逧・↓謖・ｮ・        redirect_uri = 'http://127.0.0.1:5000/gmail/auth/callback'
        app.logger.debug(f"Using redirect_uri: {redirect_uri}")
        
        # credentials.json縺ｮ蟄伜惠繧堤｢ｺ隱・        if not os.path.exists('credentials.json'):
            app.logger.error("credentials.json not found")
            flash('隱崎ｨｼ縺ｫ蠢・ｦ√↑險ｭ螳壹ヵ繧｡繧､繝ｫ縺瑚ｦ九▽縺九ｊ縺ｾ縺帙ｓ縲・, 'error')
            return redirect(url_for('get_projects'))
            
        # OAuth2繝輔Ο繝ｼ縺ｮ險ｭ螳・        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/gmail.readonly'],
            redirect_uri=redirect_uri
        )
        
        # CSRF蟇ｾ遲悶・縺溘ａ縺ｮ迥ｶ諷九ヨ繝ｼ繧ｯ繝ｳ繧堤函謌・        state = secrets.token_urlsafe(16)
        
        # 隱崎ｨｼURL繧堤函謌撰ｼ井ｸ蠎ｦ縺縺第価隱阪ｒ豎ゅａ繧具ｼ・        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # 譏守､ｺ逧・↑蜷梧э繧呈ｱゅａ繧・        )
        
        # 繝輔Ο繝ｼ繝・・繧ｿ繧偵そ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ・        session['oauth_flow'] = {
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
        flash(f'隱崎ｨｼ縺ｮ髢句ｧ倶ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}', 'error')
        return redirect(session.get('next', url_for('get_projects')))

# Gmail隱崎ｨｼ繧ｳ繝ｼ繝ｫ繝舌ャ繧ｯ逕ｨ縺ｮ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・@app.route('/gmail/auth/callback')
def gmail_auth_callback():
    app.logger.debug("Entered gmail_auth_callback")
    
    # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ迥ｶ諷九ｒ蜿門ｾ・    oauth_flow = session.get('oauth_flow')
    if not oauth_flow:
        app.logger.error("OAuth flow data not found in session")
        flash('繧ｻ繝・す繝ｧ繝ｳ縺檎┌蜉ｹ縺ｧ縺吶よ怙蛻昴°繧峨ｄ繧顔峩縺励※縺上□縺輔＞縲・, 'error')
        return redirect(url_for('get_projects'))
    
    # 迥ｶ諷九・讀懆ｨｼ
    expected_state = oauth_flow.get('state')
    if not expected_state or expected_state != request.args.get('state'):
        app.logger.error(f"Invalid state parameter. Expected: {expected_state}, Got: {request.args.get('state')}")
        flash('辟｡蜉ｹ縺ｪ繝ｪ繧ｯ繧ｨ繧ｹ繝医〒縺吶よ怙蛻昴°繧峨ｄ繧顔峩縺励※縺上□縺輔＞縲・, 'error')
        return redirect(url_for('get_projects'))
    
    # 繧ｿ繧､繝繧｢繧ｦ繝医メ繧ｧ繝・け・・0蛻・ｻ･蜀・ｼ・    if datetime.now().timestamp() - oauth_flow.get('timestamp', 0) > 1800:
        app.logger.error("OAuth flow timed out")
        session.pop('oauth_flow', None)
        session.modified = True
        flash('繧ｻ繝・す繝ｧ繝ｳ縺ｮ譛牙柑譛滄剞縺悟・繧後∪縺励◆縲ゅｂ縺・ｸ蠎ｦ縺願ｩｦ縺励￥縺縺輔＞縲・, 'error')
        return redirect(url_for('get_projects'))
    
    # 繧ｨ繝ｩ繝ｼ繝√ぉ繝・け
    if 'error' in request.args:
        error_msg = request.args.get('error_description', request.args.get('error', '荳肴・縺ｪ繧ｨ繝ｩ繝ｼ'))
        app.logger.error(f"OAuth error: {error_msg}")
        flash(f'隱崎ｨｼ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {error_msg}', 'error')
        return redirect(url_for('get_projects'))
    
    # 隱崎ｨｼ繧ｳ繝ｼ繝峨・遒ｺ隱・    if 'code' not in request.args:
        app.logger.error("No authorization code in callback")
        flash('隱崎ｨｼ繧ｳ繝ｼ繝峨′謠蝉ｾ帙＆繧後※縺・∪縺帙ｓ縲・, 'error')
        return redirect(url_for('get_projects'))
    
    try:
        # 繝輔Ο繝ｼ縺ｮ蜀肴ｧ狗ｯ・        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/gmail.readonly'],
            state=expected_state,
            redirect_uri=oauth_flow['redirect_uri']
        )
        
        # 隱崎ｨｼ繧ｳ繝ｼ繝峨ｒ繝医・繧ｯ繝ｳ縺ｨ莠､謠・        try:
            flow.fetch_token(authorization_response=request.url)
        except Exception as e:
            app.logger.error(f"Error exchanging code for token: {str(e)}")
            flash(f'隱崎ｨｼ繝医・繧ｯ繝ｳ縺ｮ蜿門ｾ励↓螟ｱ謨励＠縺ｾ縺励◆: {str(e)}', 'error')
            return redirect(url_for('get_projects'))
        
        # 隱崎ｨｼ諠・ｱ繧貞叙蠕・        credentials = flow.credentials
        if not credentials:
            app.logger.error("No credentials received from OAuth flow")
            flash('隱崎ｨｼ諠・ｱ縺瑚ｿ斐＆繧後∪縺帙ｓ縺ｧ縺励◆縲・, 'error')
            return redirect(url_for('get_projects'))
            
        if not hasattr(credentials, 'valid') or not credentials.valid:
            app.logger.error(f"Invalid credentials received. Credentials: {credentials.__dict__}")
            flash('辟｡蜉ｹ縺ｪ隱崎ｨｼ諠・ｱ縺瑚ｿ斐＆繧後∪縺励◆縲・, 'error')
            return redirect(url_for('get_projects'))
            
        app.logger.debug(f"Received valid credentials. Token expires at: {getattr(credentials, 'expiry', 'Not specified')}")
        
        # 隱崎ｨｼ諠・ｱ繧偵そ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ・        session['credentials'] = {
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
        
        # 繝ｪ繝繧､繝ｬ繧ｯ繝亥・繧貞叙蠕暦ｼ医ョ繝輔か繝ｫ繝医・繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ・・        next_page = oauth_flow.get('next', url_for('get_projects'))
        
        # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ荳譎ゅョ繝ｼ繧ｿ繧偵け繝ｪ繧｢
        session.pop('oauth_flow', None)
        session.pop('oauth_state', None)
        session.pop('next', None)
        
        app.logger.info(f"Successfully authenticated with Gmail API, redirecting to: {next_page}")
        flash('Gmail隱崎ｨｼ縺悟ｮ御ｺ・＠縺ｾ縺励◆縲・, 'success')
        return redirect(next_page)
        
    except Exception as e:
        app.logger.error(f"Error in gmail_auth_callback: {str(e)}", exc_info=True)
        # 繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺溷ｴ蜷医・隱崎ｨｼ迥ｶ諷九ｒ繧ｯ繝ｪ繧｢
        session.pop('credentials', None)
        session.pop('oauth_flow', None)
        session.pop('oauth_state', None)
        session.pop('gmail_authenticated', None)
        session.modified = True
        
        flash(f'隱崎ｨｼ蜃ｦ逅・ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}', 'error')
        return redirect(url_for('get_projects'))

# Gmail隱崎ｨｼ迥ｶ諷狗｢ｺ隱咲畑縺ｮ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・@app.route('/api/gmail/auth/status')
def gmail_auth_status():
    """Gmail隱崎ｨｼ迥ｶ諷九ｒ遒ｺ隱阪☆繧九お繝ｳ繝峨・繧､繝ｳ繝茨ｼ域立繝舌・繧ｸ繝ｧ繝ｳ莠呈鋤逕ｨ・・""
    return auth_status()

# 隱崎ｨｼ迥ｶ諷狗｢ｺ隱咲畑縺ｮ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・@app.route('/api/auth/status')
def auth_status():
    """隱崎ｨｼ迥ｶ諷九ｒ遒ｺ隱阪☆繧九お繝ｳ繝峨・繧､繝ｳ繝・""
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
    """謖・ｮ壽律謨ｰ蜑阪・譌･莉倥ｒdatetime繧ｪ繝悶ず繧ｧ繧ｯ繝医〒霑斐☆"""
    from datetime import datetime, timedelta
    return datetime.now() - timedelta(days=days)


def get_credentials_from_session() -> Credentials:
    """繧ｻ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ倥＆繧後※縺・ｋ雉・ｼ諠・ｱ繧貞ｮ牙・縺ｫ蠕ｩ蜈・☆繧九・繝ｫ繝代・髢｢謨ｰ"""
    from datetime import datetime
    creds_dict = session.get('credentials')
    if not creds_dict:
        raise RuntimeError('Gmail credentials not found in session')
    # 譁・ｭ怜・縺ｮ蝣ｴ蜷医・ datetime 縺ｫ螟画鋤
    if isinstance(creds_dict.get('expiry'), str):
        try:
            creds_dict = creds_dict.copy()
            creds_dict['expiry'] = datetime.fromisoformat(creds_dict['expiry'])
        except Exception:
            # 繝代・繧ｹ縺ｧ縺阪↑縺・ｴ蜷医・ expiry 繧貞炎髯､縺励※蠕檎ｶ壹〒繝ｪ繝輔Ξ繝・す繝･縺輔○繧・            creds_dict.pop('expiry', None)
    return Credentials(**creds_dict)

def search_gmail_emails(service, skills, normalized_skills):
    """Gmail縺九ｉ繝｡繝ｼ繝ｫ繧呈､懃ｴ｢縺励※譯井ｻｶ諠・ｱ繧定ｿ斐☆"""
    try:
        # 讀懃ｴ｢繧ｯ繧ｨ繝ｪ繧剃ｽ懈・
        date_str = get_date_days_ago(2).strftime('%Y/%m/%d')
        query_parts = [
            f'(from:sales@artwize.co.jp OR to:sales@artwize.co.jp OR cc:sales@artwize.co.jp)',
            f'after:{date_str}',
            '(譯井ｻｶ OR 豎ゆｺｺ OR 蜍滄寔 OR 繝励Ο繧ｸ繧ｧ繧ｯ繝・'
        ]
        if skills:
            query_parts.append(f"({' OR '.join(skills)})")
        
        query = ' '.join(query_parts)
        
        # 繝｡繝ｼ繝ｫ繧呈､懃ｴ｢
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=10
        ).execute()
        
        messages = results.get('messages', [])
        projects = []
        
        print(f"[API] Gmail讀懃ｴ｢繧ｯ繧ｨ繝ｪ: {query}")
        print(f"[API] 隧ｲ蠖薙Γ繝・そ繝ｼ繧ｸ謨ｰ: {len(messages)}")
        
        for msg in messages:
            try:
                # 繝｡繝ｼ繝ｫ縺ｮ隧ｳ邏ｰ繧貞叙蠕暦ｼ域悽譁・ｂ蜷ｫ繧√ｋ・・                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # 繝｡繧ｿ繝・・繧ｿ縺九ｉ蠢・ｦ√↑諠・ｱ繧呈歓蜃ｺ
                headers = {}
                for header in message.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 繝｡繝ｼ繝ｫ譛ｬ譁・ｒ蜿門ｾ・                email_body = ''
                payload = message.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                            email_body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'body' in payload and 'data' in payload['body']:
                    email_body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                
                # 蜿嶺ｿ｡譌･譎ゅｒ繝輔か繝ｼ繝槭ャ繝・                email_date = headers.get('date', '')
                try:
                    from email.utils import parsedate_to_datetime
                    email_date = parsedate_to_datetime(email_date).strftime('%Y-%m-%d %H:%M:%S')
                except (TypeError, ValueError):
                    pass
                
                # 譯井ｻｶ諠・ｱ繧剃ｽ懈・
                project = {
                    'id': message['id'],
                    'name': headers.get('subject', '(莉ｶ蜷阪↑縺・'),
                    'client_name': headers.get('from', '騾∽ｿ｡閠・ｸ肴・'),
                    'date': email_date,
                    'snippet': message.get('snippet', ''),
                    'body': email_body,
                    'source': 'gmail'
                }
                
                # 繧ｹ繧ｭ繝ｫ繝槭ャ繝√Φ繧ｰ諠・ｱ繧定ｿｽ蜉・井ｻｶ蜷阪→譛ｬ譁・・荳｡譁ｹ縺ｧ繝槭ャ繝√Φ繧ｰ・・                search_text = f"{project['name']} {project['snippet']} {email_body}"
                project['matched_skills'] = [s for s in normalized_skills if s.lower() in search_text.lower()]
                project['match_count'] = len(project['matched_skills'])
                project['match_score'] = project['match_count']
                project['match_percentage'] = min(project['match_count'] * 20, 100)  # 1繧ｹ繧ｭ繝ｫ縺ゅ◆繧・0%縺ｨ莉ｮ螳・                
                projects.append(project)
                
            except Exception as e:
                print(f"繝｡繝ｼ繝ｫ縺ｮ蜃ｦ逅・ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {e}")
                continue
        
        return projects
        
    except Exception as e:
        print(f"Gmail讀懃ｴ｢荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {e}")
        raise

# 縺薙・繧ｨ繝ｳ繝峨・繧､繝ｳ繝医・ /api/projects 縺ｫ邨ｱ蜷医＆繧後∪縺励◆

# 繧ｹ繧ｭ繝ｫ繧剃ｿ晏ｭ倥☆繧帰PI繧ｨ繝ｳ繝峨・繧､繝ｳ繝・@app.route('/api/save_skills', methods=['POST'])
def save_skills():
    try:
        data = request.get_json()
        
        # 蠢・医ヱ繝ｩ繝｡繝ｼ繧ｿ縺ｮ繝舌Μ繝・・繧ｷ繝ｧ繝ｳ
        if not data:
            return jsonify({'status': 'error', 'message': '繝ｪ繧ｯ繧ｨ繧ｹ繝医・繝・ぅ縺檎ｩｺ縺ｧ縺・}), 400
            
        if 'skills' not in data or not data['skills']:
            return jsonify({'status': 'error', 'message': '繧ｹ繧ｭ繝ｫ縺梧欠螳壹＆繧後※縺・∪縺帙ｓ'}), 400
            
        # engineerId縺梧欠螳壹＆繧後※縺・↑縺・ｴ蜷医・繝・ヵ繧ｩ繝ｫ繝亥､・・1'・峨ｒ菴ｿ逕ｨ
        engineer_id = data.get('engineerId', '1')
        skills = data['skills']
        
        # 繧ｹ繧ｭ繝ｫ縺ｮ蝙九メ繧ｧ繝・け・医Μ繧ｹ繝医∪縺溘・譁・ｭ怜・縺ｮ繧ｫ繝ｳ繝槫玄蛻・ｊ繧偵し繝昴・繝茨ｼ・        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(',') if s.strip()]
        elif not isinstance(skills, list):
            return jsonify({'status': 'error', 'message': '辟｡蜉ｹ縺ｪ繧ｹ繧ｭ繝ｫ蠖｢蠑上〒縺吶る・蛻励∪縺溘・繧ｫ繝ｳ繝槫玄蛻・ｊ縺ｮ譁・ｭ怜・繧呈欠螳壹＠縺ｦ縺上□縺輔＞縲・}), 400
        
        # 繧ｹ繧ｭ繝ｫ繧偵き繝ｳ繝槫玄蛻・ｊ縺ｮ譁・ｭ怜・縺ｫ螟画鋤・医が繝悶ず繧ｧ繧ｯ繝磯・蛻励↓繧ょｯｾ蠢懶ｼ・        processed_skills = []
        for s in skills:
            if isinstance(s, dict):
                # 繧ｪ繝悶ず繧ｧ繧ｯ繝医・蝣ｴ蜷医］ame 縺ｾ縺溘・ skill_name 繧剃ｽｿ逕ｨ
                processed_skills.append(s.get('name') or s.get('skill_name') or '')
            else:
                processed_skills.append(str(s))
        # 遨ｺ譁・ｭ怜・繧帝勁螟・        processed_skills = [ps.strip() for ps in processed_skills if ps.strip()]
        skills_str = ','.join(processed_skills)
        
        # 繝・・繧ｿ繝吶・繧ｹ縺ｫ菫晏ｭ・        conn = get_db()
        c = conn.cursor()
        
        # 繧ｨ繝ｳ繧ｸ繝九い縺梧里縺ｫ蟄伜惠縺吶ｋ縺狗｢ｺ隱・        c.execute('SELECT id FROM engineers WHERE id = ?', (engineer_id,))
        engineer = c.fetchone()
        
        if engineer:
            # 譌｢蟄倥・繧ｨ繝ｳ繧ｸ繝九い縺ｮ繧ｹ繧ｭ繝ｫ繧呈峩譁ｰ
            c.execute('''
                UPDATE engineers 
                SET skills = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (skills_str, engineer_id))
        else:
            # 譁ｰ縺励＞繧ｨ繝ｳ繧ｸ繝九い縺ｨ縺励※逋ｻ骭ｲ
            c.execute('''
                INSERT INTO engineers (id, skills, created_at, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (engineer_id, skills_str))
        
        conn.commit()
        
        # 繧ｻ繝・す繝ｧ繝ｳ縺ｫ繧ゆｿ晏ｭ假ｼ亥､ｧ譁・ｭ怜喧縺励※蠕檎ｶ壹・繝輔ぅ繝ｫ繧ｿ縺ｧ菴ｿ縺・ｄ縺吶￥縺吶ｋ・・        session['skills'] = [s.upper() for s in processed_skills]
        session.modified = True
        app.logger.debug(f"繧ｻ繝・す繝ｧ繝ｳskills譖ｴ譁ｰ: {session['skills']}")
        
        return jsonify({
            'status': 'success',
            'message': '繧ｹ繧ｭ繝ｫ縺梧ｭ｣蟶ｸ縺ｫ菫晏ｭ倥＆繧後∪縺励◆',
            'engineer_id': engineer_id,
            'skills_count': len(skills)
        })
        
    except Exception as e:
        print(f'Error saving skills: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': '繧ｹ繧ｭ繝ｫ縺ｮ菫晏ｭ倅ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆',
            'error': str(e)
        }), 500

def get_recent_sales_emails(service, days=2, max_results=10):
    """謖・ｮ壹＆繧後◆譌･謨ｰ蛻・・繝｡繝ｼ繝ｫ繧貞叙蠕励☆繧・""
    from datetime import datetime, timedelta
    
    # 譌･莉倥・險育ｮ・    after_date = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
    
    # 讀懃ｴ｢繧ｯ繧ｨ繝ｪ縺ｮ讒狗ｯ・    query_parts = [
        f'after:{after_date}',
        '(from:sales@artwize.co.jp OR to:sales@artwize.co.jp OR cc:sales@artwize.co.jp)',
        '(譯井ｻｶ OR 豎ゆｺｺ OR 蜍滄寔 OR 繝励Ο繧ｸ繧ｧ繧ｯ繝・'
    ]
    
    query = ' '.join(query_parts)
    
    try:
        # 繝｡繝ｼ繝ｫID縺ｮ蜿門ｾ・        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        
        # 繝｡繝ｼ繝ｫ縺ｮ隧ｳ邏ｰ繧貞叙蠕・        detailed_messages = []
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
    """繝｡繝ｼ繝ｫ縺ｮ隧ｳ邏ｰ諠・ｱ繧貞叙蠕・""
    try:
        message = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='raw'
        ).execute()
        
        msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))
        mime_msg = message_from_bytes(msg_str)
        
        subject = mime_msg.get('subject', '莉ｶ蜷阪↑縺・)
        sender = mime_msg.get('from', '蟾ｮ蜃ｺ莠ｺ荳肴・')
        date = mime_msg.get('date', '')
        body = ''
        
        # 譌･莉倥ｒ繝輔か繝ｼ繝槭ャ繝・        try:
            if date:
                date_obj = parsedate_to_datetime(date)
                date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
        except:
            date = '譌･莉倅ｸ肴・'
        
        # 譛ｬ譁・・蜿門ｾ・        if mime_msg.is_multipart():
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

def extract_skills_from_email(body: str) -> List[Dict[str, Any]]:
    """繝｡繝ｼ繝ｫ譛ｬ譁・°繧峨せ繧ｭ繝ｫ繧呈歓蜃ｺ縺励※隧ｳ邏ｰ縺ｪ諠・ｱ繧定ｿ斐☆
    
    Args:
        body: 繝｡繝ｼ繝ｫ譛ｬ譁・        
    Returns:
        謚ｽ蜃ｺ縺輔ｌ縺溘せ繧ｭ繝ｫ縺ｮ繝ｪ繧ｹ繝医ょ推繧ｹ繧ｭ繝ｫ縺ｯ霎樊嶌蠖｢蠑上〒縲∽ｻ･荳九・繧ｭ繝ｼ繧貞性繧:
        - name: 繧ｹ繧ｭ繝ｫ蜷・        - confidence: 菫｡鬆ｼ蠎ｦ (0.0-1.0)
        - matched_terms: 繝槭ャ繝√＠縺溽畑隱槭・繝ｪ繧ｹ繝・    """
    if not body:
        return []
    
    # 繧ｹ繧ｭ繝ｫ繧呈歓蜃ｺ
    skill_matches = skill_matcher.extract_skills_from_text(body)
    
    # 邨先棡繧呈紛蠖｢
    extracted_skills = []
    for skill, match in skill_matches.items():
        extracted_skills.append({
            'name': skill,
            'confidence': match.confidence,
            'matched_terms': match.matched_terms
        })
    
    return extracted_skills

def find_matching_engineers(project_requirements: List[Dict[str, Any]], project_context: str = "") -> List[Dict[str, Any]]:
    """繝励Ο繧ｸ繧ｧ繧ｯ繝郁ｦ∽ｻｶ縺ｫ蝓ｺ縺･縺・※繝槭ャ繝√☆繧九お繝ｳ繧ｸ繝九い繧呈､懃ｴ｢
    
    Args:
        project_requirements: 繝励Ο繧ｸ繧ｧ繧ｯ繝郁ｦ∽ｻｶ縺ｮ繝ｪ繧ｹ繝医ょ推隕∫ｴ縺ｯ莉･荳九・繧ｭ繝ｼ繧呈戟縺､霎樊嶌:
            - skill: 繧ｹ繧ｭ繝ｫ蜷・(蠢・・
            - level: 蠢・ｦ√→縺輔ｌ繧九Ξ繝吶Ν (繧ｪ繝励す繝ｧ繝ｳ)
            - weight: 驥阪∩ (繝・ヵ繧ｩ繝ｫ繝・ 1.0)
        project_context: 繝励Ο繧ｸ繧ｧ繧ｯ繝医・繧ｳ繝ｳ繝・く繧ｹ繝茨ｼ医せ繧ｭ繝ｫ縺ｮ驥阪∩莉倥￠縺ｫ菴ｿ逕ｨ・・        
    Returns:
        繝槭ャ繝√＠縺溘お繝ｳ繧ｸ繝九い縺ｮ繝ｪ繧ｹ繝茨ｼ医・繝・メ繧ｹ繧ｳ繧｢縺ｮ鬮倥＞鬆・↓繧ｽ繝ｼ繝茨ｼ・    """
    if not project_requirements:
        return []
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 繧ｨ繝ｳ繧ｸ繝九い繧貞叙蠕暦ｼ医せ繧ｭ繝ｫ諠・ｱ縺ｨ縺ｨ繧ゅ↓・・    cursor.execute("""
        SELECT e.*, 
               s.name as skill_name,
               es.level as skill_level,
               es.experience_years as experience_years
        FROM engineers e
        LEFT JOIN engineer_skills es ON e.id = es.engineer_id
        LEFT JOIN skills s ON es.skill_id = s.id
        ORDER BY e.id
    """)
    
    # 繧ｨ繝ｳ繧ｸ繝九い縺斐→縺ｫ繧ｹ繧ｭ繝ｫ繧偵げ繝ｫ繝ｼ繝怜喧
    engineers_skills = defaultdict(list)
    for row in cursor.fetchall():
        if row['skill_name']:  # 繧ｹ繧ｭ繝ｫ縺後≠繧句ｴ蜷医・縺ｿ霑ｽ蜉
            engineers_skills[row['id']].append({
                'name': row['skill_name'],
                'level': row['skill_level'],
                'experience_years': row['experience_years']
            })
    
    # 蜷・お繝ｳ繧ｸ繝九い縺ｮ繝槭ャ繝√Φ繧ｰ繧定ｨ育ｮ・    matched_engineers = []
    for engineer_id, skills in engineers_skills.items():
        # 繝槭ャ繝√Φ繧ｰ繧定ｨ育ｮ・        result = skill_matcher.match_engineer_to_project(
            engineer_skills=skills,
            project_requirements=project_requirements,
            project_context=project_context
        )
        
        # 繝槭ャ繝√＠縺溘せ繧ｭ繝ｫ縺ｮ隧ｳ邏ｰ繧貞叙蠕・        matched_skills_details = [
            {
                'skill': m['required_skill'],
                'matched_skill': m['matched_skill'],
                'level': m['level'],
                'experience': m['experience'],
                'score': m['score']
            }
            for m in result['matches']
        ]
        
        # 繧ｨ繝ｳ繧ｸ繝九い諠・ｱ繧貞叙蠕・        cursor.execute("SELECT * FROM engineers WHERE id = ?", (engineer_id,))
        engineer = dict(cursor.fetchone())
        
        # 繝槭ャ繝√Φ繧ｰ邨先棡繧定ｿｽ蜉
        matched_engineers.append({
            'engineer': engineer,
            'match_score': result['match_ratio'],
            'match_ratio': result['match_ratio'],
            'matched_skills': [m['required_skill'] for m in result['matches']],
            'matched_skills_details': matched_skills_details,
            'missed_skills': result['missed_skills'],
            'total_required_skills': len(project_requirements),
            'matched_skills_count': len(result['matches'])
        })
    
    # 繝槭ャ繝√せ繧ｳ繧｢縺ｮ鬮倥＞鬆・↓繧ｽ繝ｼ繝・    matched_engineers.sort(key=lambda x: x['match_score'], reverse=True)
    
    return matched_engineers

def extract_project_requirements(text: str) -> List[Dict[str, Any]]:
    """繝・く繧ｹ繝医°繧峨・繝ｭ繧ｸ繧ｧ繧ｯ繝郁ｦ∽ｻｶ繧呈歓蜃ｺ縺吶ｋ
    
    Args:
        text: 謚ｽ蜃ｺ蜈・・繝・く繧ｹ繝・        
    Returns:
        繝励Ο繧ｸ繧ｧ繧ｯ繝郁ｦ∽ｻｶ縺ｮ繝ｪ繧ｹ繝医ょ推隕∽ｻｶ縺ｯ莉･荳九・繧ｭ繝ｼ繧呈戟縺､霎樊嶌:
        - skill: 繧ｹ繧ｭ繝ｫ蜷・        - level: 蠢・ｦ√→縺輔ｌ繧九Ξ繝吶Ν (繧ｪ繝励す繝ｧ繝ｳ)
        - weight: 驥阪∩ (繝・ヵ繧ｩ繝ｫ繝・ 1.0)
    """
    if not text:
        return []
        
    # 繧ｹ繧ｭ繝ｫ繧呈歓蜃ｺ
    extracted_skills = extract_skills_from_email(text)
    
    # 隕∽ｻｶ縺ｫ螟画鋤
    requirements = []
    skill_names = set()  # 驥崎､・ｒ驕ｿ縺代ｋ縺溘ａ
    
    for skill_info in extracted_skills:
        skill_name = skill_info['name']
        
        # 驥崎､・ｒ繧ｹ繧ｭ繝・・
        if skill_name.lower() in skill_names:
            continue
            
        skill_names.add(skill_name.lower())
        
        # 繝ｬ繝吶Ν繧呈歓蜃ｺ
        level = None
        if re.search(rf'(荳顔ｴ嘶繧ｷ繝九い|繝ｪ繝ｼ繝榎senior|lead|expert).*{re.escape(skill_name)}', text, re.IGNORECASE):
            level = 'senior'
        elif re.search(rf'(荳ｭ邏嘶繝溘ラ繝ｫ|middle|intermediate).*{re.escape(skill_name)}', text, re.IGNORECASE):
            level = 'mid'
        elif re.search(rf'(蛻晉ｴ嘶繧ｸ繝･繝九い|junior|entry).*{re.escape(skill_name)}', text, re.IGNORECASE):
            level = 'junior'
        
        # 驥阪∩繧定ｨ育ｮ・        weight = 1.0
        if re.search(rf'(蠢・・蠢・ｦ－must have|required).*{re.escape(skill_name)}', text, re.IGNORECASE):
            weight = 1.5
        elif re.search(rf'(蜆ｪ驕・豁楢ｿ旨plus|preferred).*{re.escape(skill_name)}', text, re.IGNORECASE):
            weight = 1.2
        
        requirements.append({
            'skill': skill_name,
            'level': level,
            'weight': weight,
            'confidence': skill_info.get('confidence', 0.7)  # 繝・ヵ繧ｩ繝ｫ繝亥､
        })
    
    return requirements

@app.route('/api/projects', methods=['GET'])
def get_projects_api():
    """
    Gmail縺九ｉ譯井ｻｶ諠・ｱ繧貞叙蠕励＠縺ｦ讀懃ｴ｢繝ｻ荳ｦ縺ｳ譖ｿ縺医′縺ｧ縺阪ｋAPI繧ｨ繝ｳ繝峨・繧､繝ｳ繝・    sales@artwize.co.jp 縺ｫ騾∽ｿ｡縺輔ｌ縺溘Γ繝ｼ繝ｫ縺九ｉ譯井ｻｶ繧貞叙蠕励☆繧・    
    繧ｯ繧ｨ繝ｪ繝代Λ繝｡繝ｼ繧ｿ:
    - q: 讀懃ｴ｢繧ｯ繧ｨ繝ｪ・井ｻｶ蜷阪・譛ｬ譁・°繧画､懃ｴ｢・・    - sort: 繧ｽ繝ｼ繝磯・ｼ・ate, salary, relevance, match_score・・    - min_salary: 譛菴守ｵｦ荳趣ｼ井ｸ・・・・    - max_salary: 譛鬮倡ｵｦ荳趣ｼ井ｸ・・・・    - skills: 繧ｫ繝ｳ繝槫玄蛻・ｊ縺ｮ繧ｹ繧ｭ繝ｫ繝ｪ繧ｹ繝茨ｼ井ｾ・ Python,JavaScript,React・・    - days: 菴墓律蜑阪∪縺ｧ縺ｮ繝｡繝ｼ繝ｫ繧貞叙蠕励☆繧九°・医ョ繝輔か繝ｫ繝・ 30譌･・・    - min_match: 譛菴弱・繝・メ邇・ｼ・.0-1.0縲√ョ繝輔か繝ｫ繝・ 0.3・・    """
    try:
        # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ隱崎ｨｼ諠・ｱ繧堤｢ｺ隱・        if 'credentials' not in session:
            return jsonify({'status': 'error', 'message': 'Gmail隱崎ｨｼ縺悟ｿ・ｦ√〒縺・}), 401
            
        # 繧ｯ繧ｨ繝ｪ繝代Λ繝｡繝ｼ繧ｿ繧貞叙蠕・        search_query = request.args.get('q', '').lower()
        sort_by = request.args.get('sort', 'date')
        min_salary = request.args.get('min_salary')
        max_salary = request.args.get('max_salary')
        skills_param = request.args.get('skills', '')
        days = int(request.args.get('days', 30))
        min_match = float(request.args.get('min_match', 0.3))
        
        # 繧ｹ繧ｭ繝ｫ繝輔ぅ繝ｫ繧ｿ繝ｼ繧貞・逅・        skills_filter = [s.strip() for s in skills_param.split(',') if s.strip()]
        
        # Gmail繧ｵ繝ｼ繝薙せ繧貞・譛溷喧
        credentials = get_credentials_from_session()
        service = build('gmail', 'v1', credentials=credentials)
        
        # 讀懃ｴ｢繧ｯ繧ｨ繝ｪ繧呈ｧ狗ｯ・        query = f'to:sales@artwize.co.jp newer_than:{days}d'
        if search_query:
            query += f' {search_query}'
            
        # 繝｡繝・そ繝ｼ繧ｸ繧呈､懃ｴ｢
        response = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=50
        ).execute()
        
        messages = response.get('messages', [])
        projects = []
        
        # 蜷・Γ繝・そ繝ｼ繧ｸ繧貞・逅・        for msg in messages:
            try:
                # 繝｡繝・そ繝ｼ繧ｸ縺ｮ隧ｳ邏ｰ繧貞叙蠕・                msg_data = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # 繝｡繝ｼ繝ｫ諠・ｱ繧呈歓蜃ｺ
                headers = {}
                for header in msg_data.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 莉ｶ蜷阪→騾∽ｿ｡閠・ｒ蜿門ｾ・                subject = headers.get('subject', '(莉ｶ蜷阪↑縺・')
                sender = headers.get('from', '騾∽ｿ｡閠・ｸ肴・')
                date = headers.get('date', '')
                
                # 繝｡繝ｼ繝ｫ譛ｬ譁・ｒ蜿門ｾ・                body = ''
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                            break
                
                # 繝励Ο繧ｸ繧ｧ繧ｯ繝郁ｦ∽ｻｶ繧呈歓蜃ｺ
                project_requirements = extract_project_requirements(f"{subject}\n\n{body}")
                
                # 繧ｹ繧ｭ繝ｫ繝輔ぅ繝ｫ繧ｿ繝ｼ縺梧欠螳壹＆繧後※縺・ｋ蝣ｴ蜷医・繝槭ャ繝√Φ繧ｰ繧堤｢ｺ隱・                if skills_filter:
                    # 繧ｹ繧ｭ繝ｫ繝槭ャ繝√Φ繧ｰ繧貞ｮ溯｡・                    matched_skills = [
                        req['skill'] for req in project_requirements 
                        if any(skill.lower() in req['skill'].lower() for skill in skills_filter)
                    ]
                    
                    # 繝槭ャ繝∫紫繧定ｨ育ｮ・                    match_ratio = len(matched_skills) / len(skills_filter) if skills_filter else 0
                    
                    # 譛菴弱・繝・メ邇・↓貅縺溘↑縺・ｴ蜷医・繧ｹ繧ｭ繝・・
                    if match_ratio < min_match:
                        continue
                else:
                    matched_skills = []
                    match_ratio = 0
                
                # 繝励Ο繧ｸ繧ｧ繧ｯ繝域ュ蝣ｱ繧定ｿｽ蜉
                project = {
                    'id': msg['id'],
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'snippet': body[:200] + ('...' if len(body) > 200 else ''),
                    'requirements': project_requirements,
                    'matched_skills': matched_skills,
                    'match_ratio': match_ratio
                }
                
                # 邨ｦ荳取ュ蝣ｱ繧呈歓蜃ｺ・医≠繧後・・・                salary_match = re.search(r'(邨ｦ荳旨蝣ｱ驟ｬ|蜊倅ｾ｡)[:・咯\s*([0-9,]+)', body, re.IGNORECASE)
                if salary_match:
                    try:
                        salary = int(salary_match.group(2).replace(',', ''))
                        project['salary'] = salary
                        
                        # 邨ｦ荳弱ヵ繧｣繝ｫ繧ｿ繝ｼ繧帝←逕ｨ
                        if min_salary and salary < int(min_salary):
                            continue
                        if max_salary and salary > int(max_salary):
                            continue
                    except (ValueError, AttributeError):
                        pass
                
                projects.append(project)
                
            except Exception as e:
                print(f"Error processing message {msg['id']}: {str(e)}")
                continue
        
        # 繧ｽ繝ｼ繝・        if sort_by == 'date':
            projects.sort(key=lambda x: x.get('date', ''), reverse=True)
        elif sort_by == 'salary':
            projects.sort(key=lambda x: x.get('salary', 0), reverse=True)
        elif sort_by == 'match_score':
            projects.sort(key=lambda x: x.get('match_ratio', 0), reverse=True)
        
        # 邨先棡繧定ｿ斐☆
        return jsonify({
            'status': 'success',
            'projects': projects,
            'count': len(projects)
        })
        
    except Exception as e:
        print(f"Error in get_projects_api: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
                payload = message.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                            email_body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'body' in payload and 'data' in payload['body']:
                    email_body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                
                # 繧ｹ繝九・繝・ヨ繧貞叙蠕暦ｼ域悽譁・・蜈磯ｭ200譁・ｭ暦ｼ・                snippet = email_body[:200] + '...' if len(email_body) > 200 else email_body
                
                # 譌･莉倥ｒ蜿門ｾ励＠縺ｦ繝輔か繝ｼ繝槭ャ繝・                date_str = headers.get('date', '')
                try:
                    from email.utils import parsedate_to_datetime
                    parsed_date = parsedate_to_datetime(date_str)
                    formatted_date = parsed_date.isoformat()
                    timestamp = parsed_date.timestamp()
                except (TypeError, ValueError):
                    # 譌･莉倥・繝代・繧ｹ縺ｫ螟ｱ謨励＠縺溷ｴ蜷医・迴ｾ蝨ｨ譎ょ綾繧剃ｽｿ逕ｨ
                    parsed_date = datetime.utcnow()
                    formatted_date = parsed_date.isoformat()
                    timestamp = parsed_date.timestamp()
                
                # 騾∽ｿ｡閠・ュ蝣ｱ繧貞叙蠕・                from_email = headers.get('from', '騾∽ｿ｡閠・ｸ肴・')
                
                # 邨ｦ荳取ュ蝣ｱ繧呈歓蜃ｺ・域ｭ｣隕剰｡ｨ迴ｾ縺ｧ謨ｰ蛟､繧呈､懃ｴ｢・・                salary = 0
                salary_match = re.search(r'(邨ｦ荳旨蟷ｴ蜿旨蝣ｱ驟ｬ|蜊倅ｾ｡)[:・咯?\s*([\d,]+)[\s\-~]*([\d,]*)', subject + ' ' + email_body)
                if salary_match:
                    try:
                        # 謨ｰ蛟､繧呈歓蜃ｺ縺励※蟷ｳ蝮・ｒ險育ｮ・                        min_sal = int(salary_match.group(2).replace(',', ''))
                        max_sal = int(salary_match.group(3).replace(',', '')) if salary_match.group(3) else min_sal
                        salary = (min_sal + max_sal) // 2
                    except (ValueError, AttributeError):
                        pass
                
                # 邨ｦ荳弱ヵ繧｣繝ｫ繧ｿ繝ｼ繧帝←逕ｨ
                if min_salary and salary < int(min_salary):
                    continue
                if max_salary and salary > int(max_salary) and int(max_salary) > 0:  # max_salary=0縺ｯ辟｡隕・                    continue
                
                # 蜍､蜍吝慍繧呈歓蜃ｺ
                location_match = re.search(r'蜍､蜍吝慍[・・]([^\n]+)', email_body)
                location = location_match.group(1).strip() if location_match else '譛ｪ險倩ｼ・
                
                # 繧ｹ繧ｭ繝ｫ繧呈歓蜃ｺ
                email_content = f"{subject} {email_body}".upper()
                matched_skills = []
                
                # 繧ｻ繝・す繝ｧ繝ｳ縺ｮ繧ｹ繧ｭ繝ｫ縺ｨ繝代Λ繝｡繝ｼ繧ｿ縺ｮ繧ｹ繧ｭ繝ｫ縺ｮ荳｡譁ｹ縺ｧ繝槭ャ繝√Φ繧ｰ
                for skill in skills_filter:
                    if skill.upper() in email_content:
                        matched_skills.append(skill)
                
                # 繧ｹ繧ｭ繝ｫ縺・縺､繧ゅ・繝・メ縺励↑縺・ｴ蜷医・繧ｹ繧ｭ繝・・・医せ繧ｭ繝ｫ繝輔ぅ繝ｫ繧ｿ繝ｼ縺梧欠螳壹＆繧後※縺・ｋ蝣ｴ蜷茨ｼ・                if skills_filter and not matched_skills:
                    continue
                
                # 繝槭ャ繝∫紫繧定ｨ育ｮ・                match_count = len(matched_skills)
                match_percentage = int((match_count / len(skills_filter)) * 100) if skills_filter else 0
                
                # 繝｡繝・そ繝ｼ繧ｸ縺ｮ繝倥ャ繝繝ｼ縺九ｉ蠢・ｦ√↑諠・ｱ繧呈歓蜃ｺ
                subject = headers.get('subject', '')
                from_email = headers.get('from', '')
                
                # Gmail URL繧堤函謌撰ｼ医せ繝ｬ繝・ラID繧剃ｽｿ逕ｨ・・                gmail_url = (
                    f"https://mail.google.com/mail/u/0/#all/{thread_id}"
                    if thread_id
                    else f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{quote(message_id)}"
                )
                print(f"[DEBUG] Gmail URL: {gmail_url}")  # 繝・ヰ繝・げ逕ｨ
                
                # 繝励Ο繧ｸ繧ｧ繧ｯ繝医が繝悶ず繧ｧ繧ｯ繝医ｒ菴懈・
                project = {
                    'id': message_id,
                    'title': subject or '辟｡鬘後・譯井ｻｶ',
                    'subject': subject,
                    'snippet': snippet,
                    'description': snippet,
                    'created_at': formatted_date,
                    'from': from_email,
                    'salary': salary,
                    'location': location,
                    'body': email_body[:500] + '...' if len(email_body) > 500 else email_body,
                    'matched_skills': matched_skills,
                    'match_count': match_count,
                    'match_percentage': match_percentage,
                    'timestamp': timestamp,
                    'thread_id': thread_id,
                    'message_id': message_id,
                    'gmail_url': gmail_url
                }
                
                projects.append(project)
                
            except Exception as e:
                print(f"[API] 繝｡繝ｼ繝ｫ蜃ｦ逅・お繝ｩ繝ｼ (ID: {msg.get('id', 'unknown')}): {str(e)}")
                continue
        
        # 繧ｽ繝ｼ繝亥・逅・        if sort_by == 'date':
            projects.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        elif sort_by == 'salary':
            projects.sort(key=lambda x: x.get('salary', 0), reverse=True)
        elif sort_by == 'relevance':
            # 髢｢騾｣蠎ｦ縺碁ｫ倥＞鬆・ｼ医・繝・メ邇・・鬮倥＞鬆・ｼ峨↓繧ｽ繝ｼ繝・            projects.sort(key=lambda x: (x.get('match_percentage', 0), x.get('timestamp', 0)), reverse=True)
        
        return jsonify({
            'status': 'success',
            'data': projects,
            'total': len(projects),
            'query': {
                'search_query': search_query,
                'skills': skills_filter,
                'days': days
            }
        })
        
    except Exception as e:
        error_msg = f'譯井ｻｶ縺ｮ讀懃ｴ｢荳ｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'
        app.logger.error(f'[API] 繧ｨ繝ｩ繝ｼ: {error_msg}', exc_info=True)
        return jsonify({
            'status': 'error',
            'message': error_msg,
            'error_type': str(type(e).__name__)
        }), 500

@app.route('/projects', methods=['GET'])
def get_projects():
    """
    繝励Ο繧ｸ繧ｧ繧ｯ繝井ｸ隕ｧ繝壹・繧ｸ繧定｡ｨ遉ｺ縺吶ｋ
    繧ｹ繧ｭ繝ｫ繧ｷ繝ｼ繝医↓蝓ｺ縺･縺・※ sales@artwize.co.jp 縺ｫ騾∽ｿ｡縺輔ｌ縺溘Γ繝ｼ繝ｫ縺九ｉ譯井ｻｶ繧呈､懃ｴ｢縺励※陦ｨ遉ｺ
    """
    try:
        # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ隱崎ｨｼ諠・ｱ繧貞叙蠕・        if 'credentials' not in session:
            return redirect(url_for('gmail_auth'))
            
        # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ繧ｹ繧ｭ繝ｫ繧貞叙蠕暦ｼ亥ｿ・茨ｼ・        skills = session.get('skills')
        if not skills:
            return render_template('projects.html',
                               projects=[],
                               error_message='繧ｹ繧ｭ繝ｫ繧ｷ繝ｼ繝医′繧｢繝・・繝ｭ繝ｼ繝峨＆繧後※縺・∪縺帙ｓ縲ゅ∪縺壹・繧ｹ繧ｭ繝ｫ繧ｷ繝ｼ繝医ｒ繧｢繝・・繝ｭ繝ｼ繝峨＠縺ｦ縺上□縺輔＞縲・)
        
        # Gmail繧ｵ繝ｼ繝薙せ繧貞・譛溷喧
        credentials = get_credentials_from_session()
        service = build('gmail', 'v1', credentials=credentials)
        
        # 繝・ヰ繝・げ逕ｨ繝ｭ繧ｰ
        print(f"[繝励Ο繧ｸ繧ｧ繧ｯ繝域､懃ｴ｢] 繧ｹ繧ｭ繝ｫ: {skills}")
        
        # 繧ｹ繧ｭ繝ｫ縺ｧGmail譯井ｻｶ繧呈､懃ｴ｢・・o:sales@artwize.co.jp 縺ｧ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ・・        query_parts = [f'to:sales@artwize.co.jp', f'after:{get_date_days_ago(30)}']
        if skills:
            query_parts.append(f"({' OR '.join(skills)})")
        
        query = ' '.join(query_parts)
        print(f"[繝励Ο繧ｸ繧ｧ繧ｯ繝域､懃ｴ｢] Gmail讀懃ｴ｢繧ｯ繧ｨ繝ｪ: {query}")
        
        # Gmail縺九ｉ繝｡繝ｼ繝ｫ繧呈､懃ｴ｢
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=50
        ).execute()
        
        messages = results.get('messages', [])
        print(f"[繝励Ο繧ｸ繧ｧ繧ｯ繝域､懃ｴ｢] 隧ｲ蠖薙Γ繝・そ繝ｼ繧ｸ謨ｰ: {len(messages)}")
        
        # 繝｡繝・そ繝ｼ繧ｸ縺九ｉ譯井ｻｶ諠・ｱ繧呈歓蜃ｺ
        projects = []
        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # 繝｡繝ｼ繝ｫ繝倥ャ繝繝ｼ縺九ｉ蝓ｺ譛ｬ諠・ｱ繧呈歓蜃ｺ
                headers = {}
                for header in message.get('payload', {}).get('headers', []):
                    headers[header['name'].lower()] = header['value']
                
                # 繝｡繝ｼ繝ｫ譛ｬ譁・ｒ謚ｽ蜃ｺ
                email_body = ''
                payload = message.get('payload', {})
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain' and 'body' in part and 'data' in part['body']:
                            email_body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'body' in payload and 'data' in payload['body']:
                    email_body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                
                # 繧ｹ繧ｭ繝ｫ繝槭ャ繝√Φ繧ｰ
                matched_skills = []
                email_content = f"{headers.get('subject', '')} {email_body}".lower()
                
                for skill in skills:
                    if skill.lower() in email_content:
                        matched_skills.append(skill)
                
                # 繝｡繝・そ繝ｼ繧ｸID縺ｨ繧ｹ繝ｬ繝・ラID繧貞叙蠕・                message_id = msg['id']
                thread_id = message.get('threadId')
                gmail_url = f"https://mail.google.com/mail/u/0/#all/{thread_id}" if thread_id else f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{quote(message_id)}"
                
                # 繝｡繝・そ繝ｼ繧ｸ縺九ｉ譯井ｻｶ諠・ｱ繧呈歓蜃ｺ
                project = {
                    'id': message_id,
                    'thread_id': thread_id,
                    'gmail_url': gmail_url,
                    'title': headers.get('subject', '・井ｻｶ蜷阪↑縺暦ｼ・),
                    'description': email_body[:200] + '...' if len(email_body) > 200 else email_body,
                    'created_at': headers.get('date', ''),
                    'from': headers.get('from', '騾∽ｿ｡閠・ｸ肴・'),
                    'location': location,
                    'salary': salary,
                    'required_skills': matched_skills,
                    'match_count': len(matched_skills),
                    'match_percentage': int((len(matched_skills) / len(skills)) * 100) if skills else 0
                }
                projects.append(project)
                    
            except Exception as e:
                print(f"[繝励Ο繧ｸ繧ｧ繧ｯ繝域､懃ｴ｢] 繝｡繝ｼ繝ｫ蜃ｦ逅・お繝ｩ繝ｼ (ID: {msg.get('id')}): {str(e)}")
                continue
        
        # 繝槭ャ繝∫紫縺ｮ鬮倥＞鬆・↓繧ｽ繝ｼ繝・        projects.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
        
        print(f"[繝励Ο繧ｸ繧ｧ繧ｯ繝域､懃ｴ｢] 繝槭ャ繝√＠縺滓｡井ｻｶ謨ｰ: {len(projects)}")
        
        # 繝・Φ繝励Ξ繝ｼ繝医↓繝励Ο繧ｸ繧ｧ繧ｯ繝医ョ繝ｼ繧ｿ繧呈ｸ｡縺励※繝ｬ繝ｳ繝繝ｪ繝ｳ繧ｰ
        return render_template('projects.html', projects=projects)
        
    except Exception as e:
        error_msg = f'繝励Ο繧ｸ繧ｧ繧ｯ繝医・蜿門ｾ嶺ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆: {str(e)}'
        app.logger.error(f'[繝励Ο繧ｸ繧ｧ繧ｯ繝域､懃ｴ｢] 繧ｨ繝ｩ繝ｼ: {error_msg}', exc_info=True)
        return render_template('projects.html', 
                            projects=[], 
                            error_message=error_msg)

# 繧ｨ繝ｩ繝ｼ繝｡繝・そ繝ｼ繧ｸ
error_messages = {
    'no_file': '繝輔ぃ繧､繝ｫ縺碁∈謚槭＆繧後※縺・∪縺帙ｓ',
    'invalid_extension': '險ｱ蜿ｯ縺輔ｌ縺ｦ縺・↑縺・ヵ繧｡繧､繝ｫ蠖｢蠑上〒縺吶１DF縺ｾ縺溘・Word譁・嶌繧偵い繝・・繝ｭ繝ｼ繝峨＠縺ｦ縺上□縺輔＞縲・,
    'file_too_large': f'繝輔ぃ繧､繝ｫ繧ｵ繧､繧ｺ縺悟､ｧ縺阪☆縺弱∪縺吶・MAX_FILE_SIZE // (1024*1024)}MB莉･荳九・繝輔ぃ繧､繝ｫ繧偵い繝・・繝ｭ繝ｼ繝峨＠縺ｦ縺上□縺輔＞縲・,
    'upload_failed': '繝輔ぃ繧､繝ｫ縺ｮ繧｢繝・・繝ｭ繝ｼ繝峨↓螟ｱ謨励＠縺ｾ縺励◆縲・,
    'processing_error': '繝輔ぃ繧､繝ｫ縺ｮ蜃ｦ逅・ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆縲・,
    'invalid_file': '繝輔ぃ繧､繝ｫ縺檎ｴ謳阪＠縺ｦ縺・ｋ縺九√し繝昴・繝医＆繧後※縺・↑縺・ｽ｢蠑上〒縺吶・
}

# Gmail API縺ｮ險ｭ螳・# Gmail API縺ｮ繧ｹ繧ｳ繝ｼ繝・SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Gmail API繧ｵ繝ｼ繝薙せ繧貞叙蠕励☆繧・""
    # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ隱崎ｨｼ諠・ｱ繧貞叙蠕・    if 'credentials' not in session:
        app.logger.debug("No credentials in session for get_gmail_service")
        return None
    
        
    try:
        # 繧ｻ繝・す繝ｧ繝ｳ縺九ｉ隱崎ｨｼ諠・ｱ繧貞叙蠕・        creds_info = session['credentials']
        creds = Credentials(
            token=creds_info['token'],
            refresh_token=creds_info.get('refresh_token'),  # refresh_token縺ｯ蛻晏屓縺ｮ縺ｿ縺ｮ蜿ｯ閭ｽ諤ｧ縺後≠繧九◆繧“et繧剃ｽｿ逕ｨ
            token_uri=creds_info['token_uri'],
            client_id=creds_info['client_id'],
            client_secret=creds_info['client_secret'],
            scopes=creds_info['scopes']
        )
        
        # 繝医・繧ｯ繝ｳ縺ｮ譛牙柑譛滄剞繧偵メ繧ｧ繝・け縺励※蠢・ｦ√↓蠢懊§縺ｦ譖ｴ譁ｰ
        if creds.expired and creds.refresh_token:
            try:
                app.logger.info("Refreshing expired token")
                creds.refresh(Request())
                
                # 譖ｴ譁ｰ縺励◆隱崎ｨｼ諠・ｱ繧偵そ繝・す繝ｧ繝ｳ縺ｫ菫晏ｭ・                session['credentials'] = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,  # 譁ｰ縺励＞繝ｪ繝輔Ξ繝・す繝･繝医・繧ｯ繝ｳ・医≠繧後・・・                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None
                }
                session.modified = True
                app.logger.info("Token refreshed successfully")
                
            except Exception as e:
                app.logger.error(f"Failed to refresh token: {str(e)}", exc_info=True)
                # 隱崎ｨｼ諠・ｱ縺檎┌蜉ｹ縺ｪ蝣ｴ蜷医・繧ｻ繝・す繝ｧ繝ｳ縺九ｉ蜑企勁
                session.pop('credentials', None)
                session.pop('gmail_authenticated', None)
                return None
        
        # 隱崎ｨｼ諠・ｱ縺梧怏蜉ｹ縺狗｢ｺ隱・        if not creds.valid:
            app.logger.warning("Invalid credentials")
            session.pop('credentials', None)
            session.pop('gmail_authenticated', None)
            return None
            
        # Gmail API繧ｵ繝ｼ繝薙せ繧呈ｧ狗ｯ峨＠縺ｦ霑斐☆
        try:
            service = build('gmail', 'v1', credentials=creds)
            return service
            
        except Exception as e:
            app.logger.error(f"Failed to create Gmail service: {str(e)}", exc_info=True)
            # 繧ｵ繝ｼ繝薙せ菴懈・縺ｫ螟ｱ謨励＠縺溷ｴ蜷医・隱崎ｨｼ諠・ｱ繧堤┌蜉ｹ蛹・            session.pop('credentials', None)
            session.pop('gmail_authenticated', None)
            return None
            
    except Exception as e:
        app.logger.error(f"Error in get_gmail_service: {str(e)}", exc_info=True)
        # 繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺溷ｴ蜷医・隱崎ｨｼ諠・ｱ繧偵け繝ｪ繧｢
        session.pop('credentials', None)
        session.pop('gmail_authenticated', None)
        return None

if __name__ == '__main__':
    # 繧｢繝・・繝ｭ繝ｼ繝峨ヵ繧ｩ繝ｫ繝縺悟ｭ伜惠縺吶ｋ縺狗｢ｺ隱・    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # 繝・Φ繝励Ξ繝ｼ繝医ヵ繧ｩ繝ｫ繝縺悟ｭ伜惠縺吶ｋ縺狗｢ｺ隱・    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 髢狗匱逕ｨ縺ｫ繝・ヰ繝・げ繝｢繝ｼ繝峨〒襍ｷ蜍・    app.run(debug=True, port=5000, host='0.0.0.0')

