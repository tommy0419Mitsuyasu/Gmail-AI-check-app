
import sqlite3
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import json
import os

class DBManager:
    def __init__(self, db_path: str = 'ses_projects.db'):
        """
        データベースマネージャーの初期化
        
        Args:
            db_path (str): データベースファイルのパス
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(db_path):
            self.db_path = os.path.join(base_dir, db_path)
        else:
            self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """データベース接続を取得する"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            raise

    def _init_db(self):
        """データベースとテーブルの初期化"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # WALモード有効化（同時実行性能向上）
            cursor.execute('PRAGMA journal_mode=WAL;')

            # 1. メール原文テーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                message_id TEXT PRIMARY KEY,
                subject TEXT,
                sender TEXT,
                received_at DATETIME,
                body TEXT,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                raw_data TEXT  -- JSON形式でメタデータを保存
            )
            ''')

            # 2. 案件情報テーブル
            # 1つのメールに複数の案件が含まれる可能性があるため、email_idと紐付け
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_message_id TEXT,
                title TEXT,
                description TEXT,
                
                -- 単価情報 (数値で保持して範囲検索可能にする)
                min_price INTEGER,
                max_price INTEGER,
                price_text TEXT,  -- 元の表記（例: "60-70万円"）
                
                -- 精算幅
                min_hours INTEGER,
                max_hours INTEGER,
                
                -- その他条件
                location TEXT,
                commercial_flow TEXT,
                remote_type TEXT,  -- フルリモート/週3リモートなど
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_message_id) REFERENCES emails(message_id)
            )
            ''')

            # 3. スキルマスタ
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
            ''')

            # 4. 案件-スキル関連付け（多対多）
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_skills (
                project_id INTEGER,
                skill_id INTEGER,
                type TEXT, -- 'must' or 'want'
                
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (skill_id) REFERENCES skills(id),
                PRIMARY KEY (project_id, skill_id)
            )
            ''')

            # 5. FTS5 仮想テーブル（全文検索用）
            # 独立したテーブルとして定義し、アプリ側で同期を行う
            cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS projects_fts USING fts5(
                title, 
                description, 
                location, 
                commercial_flow,
                skills_text
            )
            ''')
            
            # トリガーは削除（アプリ側で制御するため）
            # 既存のトリガーがあれば削除
            cursor.execute('DROP TRIGGER IF EXISTS projects_ai')
            cursor.execute('DROP TRIGGER IF EXISTS projects_ad')
            cursor.execute('DROP TRIGGER IF EXISTS projects_au')

            conn.commit()
            logging.info("Database initialized successfully.")

        except sqlite3.Error as e:
            logging.error(f"Database initialization failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_email(self, message_id: str, subject: str, sender: str, 
                  received_at: str, body: str, raw_data: Dict = None) -> bool:
        """メール原文を保存する"""
        conn = self._get_connection()
        try:
            conn.execute('''
            INSERT OR IGNORE INTO emails (message_id, subject, sender, received_at, body, raw_data)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (message_id, subject, sender, received_at, body, 
                  json.dumps(raw_data) if raw_data else None))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Failed to save email {message_id}: {e}")
            return False
        finally:
            conn.close()

    def save_project(self, email_message_id: str, project_data: Dict, skills: List[Dict]) -> int:
        """
        抽出された案件情報を保存する
        
        Args:
            email_message_id: 元メールのID
            project_data: 案件情報の辞書 (title, description, min_price...)
            skills: スキルリスト [{'name': 'Java', 'type': 'must'}, ...]
            
        Returns:
            int: 作成されたProject ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. 案件情報の保存
            cursor.execute('''
            INSERT INTO projects (
                email_message_id, title, description, 
                min_price, max_price, price_text,
                min_hours, max_hours,
                location, commercial_flow, remote_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_message_id,
                project_data.get('title'),
                project_data.get('description'),
                project_data.get('min_price'),
                project_data.get('max_price'),
                project_data.get('price_text'),
                project_data.get('min_hours'),
                project_data.get('max_hours'),
                project_data.get('location'),
                project_data.get('commercial_flow'),
                project_data.get('remote_type')
            ))
            
            project_id = cursor.lastrowid
            
            # 2. スキル情報の保存と紐付け
            skill_names = []
            for skill in skills:
                name = skill.get('name')
                skill_type = skill.get('type', 'must')
                
                if not name:
                    continue
                    
                skill_names.append(name)
                
                # スキルマスタへの登録（存在しなければ）
                cursor.execute('INSERT OR IGNORE INTO skills (name) VALUES (?)', (name,))
                
                # スキルIDの取得
                cursor.execute('SELECT id FROM skills WHERE name = ?', (name,))
                skill_id = cursor.fetchone()[0]
                
                # 紐付け
                cursor.execute('''
                INSERT OR IGNORE INTO project_skills (project_id, skill_id, type)
                VALUES (?, ?, ?)
                ''', (project_id, skill_id, skill_type))
            
            # 3. FTSインデックスへの登録
            skills_text = ' '.join(skill_names)
            cursor.execute('''
            INSERT INTO projects_fts (rowid, title, description, location, commercial_flow, skills_text)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                project_id,
                project_data.get('title', ''),
                project_data.get('description', ''),
                project_data.get('location', ''),
                project_data.get('commercial_flow', ''),
                skills_text
            ))

            conn.commit()
            return project_id

        except sqlite3.Error as e:
            logging.error(f"Failed to save project: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def search_projects(self, 
                       keywords: str = None, 
                       min_price: int = None,
                       max_price: int = None,
                       skills: List[str] = None,
                       limit: int = 20, 
                       offset: int = 0) -> List[Dict]:
        """
        案件を検索する
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        
        try:
            query_parts = ["SELECT p.*, e.received_at FROM projects p JOIN emails e ON p.email_message_id = e.message_id"]
            params = []
            where_clauses = []
            
            # 1. 全文検索 (FTS)
            if keywords:
                # FTSテーブルとのJOIN
                query_parts[0] += " JOIN projects_fts fts ON p.id = fts.rowid"
                where_clauses.append("projects_fts MATCH ?")
                params.append(keywords)
            
            # 1.5 人材系・ノイズ除去（件名除外）
            # 明示的に人材情報を除外
            exclude_terms = ['人材', '要員', 'スキルシート', '経歴書', 'ナレッジ', '報告', '連絡']
            for term in exclude_terms:
                where_clauses.append("p.title NOT LIKE ?")
                params.append(f'%{term}%')

            # 2. 単価範囲 (厳密化: ユーザー希望範囲に収まる/満たす案件のみ)
            # ユーザーが「80万〜」としたら、「60万〜」は除外する（下限が80万以上の案件のみ）
            if min_price:
                # 案件の下限が指定以上、または下限不明だが上限が指定以上
                where_clauses.append("((p.min_price IS NOT NULL AND p.min_price >= ?) OR (p.min_price IS NULL AND p.max_price >= ?))")
                params.append(min_price)
                params.append(min_price)
                
            if max_price:
                # ユーザーが「〜100万」としたら、「〜120万」は除外する（上限が100万以下の案件のみ）
                # 案件の上限が指定以下、または上限不明だが下限が指定以下
                where_clauses.append("((p.max_price IS NOT NULL AND p.max_price <= ?) OR (p.max_price IS NULL AND p.min_price <= ?))")
                params.append(max_price)
                params.append(max_price)
                
            # 3. スキルタグ検索
            if skills:
                for skill in skills:
                    where_clauses.append("""
                    EXISTS (
                        SELECT 1 FROM project_skills ps 
                        JOIN skills s ON ps.skill_id = s.id 
                        WHERE ps.project_id = p.id AND s.name = ?
                    )
                    """)
                    params.append(skill)
            
            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))
                
            query_parts.append("ORDER BY e.received_at DESC LIMIT ? OFFSET ?")
            params.extend([limit, offset])
            
            full_query = " ".join(query_parts)
            cursor = conn.execute(full_query, params)
            
            results = []
            for row in cursor:
                # 辞書に変換
                row_dict = dict(row)
                
                # 関連スキルを取得
                skill_cursor = conn.execute('''
                SELECT s.name, ps.type 
                FROM skills s 
                JOIN project_skills ps ON s.id = ps.skill_id 
                WHERE ps.project_id = ?
                ''', (row['id'],))
                
                row_dict['skills'] = [dict(s) for s in skill_cursor.fetchall()]
                results.append(row_dict)
                
            return results

        except sqlite3.Error as e:
            logging.error(f"Search failed: {e}")
            return []
        finally:
            conn.close()

# グローバルインスタンス
db_manager = DBManager()
