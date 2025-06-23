import os
import re
import json
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import PyPDF2
from datetime import datetime, timedelta
from collections import defaultdict
from skill_matcher import SkillMatcher

# アプリケーションの初期化
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# CORSの設定
CORS(app, resources={
    r"/api/*": {"origins": "*"},
    r"/gmail/*": {"origins": "*"}
})

# データベースの設定
DB_FILE = 'database.db'
app.config['DATABASE'] = DB_FILE

# スキルマッパーの初期化
skill_matcher = SkillMatcher()

# その他のインポート
from flask import Flask, jsonify, request, g, send_from_directory, url_for, render_template, redirect, send_file, session, flash, make_response, current_app
from werkzeug.utils import secure_filename
from ruamel import yaml
from flask_cors import CORS
from googleapiclient.discovery import build
import sqlite3
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
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
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# その他の関数定義...

if __name__ == '__main__':
    # アップロードフォルダが存在するか確認
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # データベースの初期化
    with app.app_context():
        if not os.path.exists(DB_FILE):
            init_db()
    
    # アプリケーションを実行
    app.run(debug=True, port=5000, host='0.0.0.0')
