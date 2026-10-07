
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
                raw_data TEXT,  -- 今後は使用しないが既存データ互換のため残す
                status TEXT DEFAULT 'pending',
                simhash_val TEXT
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
                
                -- ベクトル検索用
                embedding BLOB,
                
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
            cursor.execute("SELECT sql FROM sqlite_master WHERE name = 'projects_fts'")
            row = cursor.fetchone()
            if not row or 'trigram' not in row[0].lower():
                if row:
                    cursor.execute('DROP TABLE projects_fts')
                cursor.execute('''
                CREATE VIRTUAL TABLE projects_fts USING fts5(
                    title, 
                    description, 
                    location, 
                    commercial_flow,
                    skills_text,
                    tokenize='trigram'
                )
                ''')
                # 既存データの移行（すでにテーブルがあった場合）
                if row:
                    cursor.execute('''
                    INSERT INTO projects_fts(rowid, title, description, location, commercial_flow, skills_text)
                    SELECT p.id, p.title, p.description, p.location, p.commercial_flow, 
                           (SELECT GROUP_CONCAT(s.name, ' ') FROM project_skills ps JOIN skills s ON ps.skill_id = s.id WHERE ps.project_id = p.id)
                    FROM projects p
                    ''')
            
            # トリガーは削除（アプリ側で制御するため）
            # 既存のトリガーがあれば削除
            cursor.execute('DROP TRIGGER IF EXISTS projects_ai')
            cursor.execute('DROP TRIGGER IF EXISTS projects_ad')
            cursor.execute('DROP TRIGGER IF EXISTS projects_au')

            # 6. フィードバック用テーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                candidate_skills TEXT, -- 検索時のスキルリスト(JSON)
                is_good BOOLEAN, -- 良いマッチか悪いマッチか
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            ''')

            # インデックスの作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_projects_email ON projects(email_message_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_project_skills_skill ON project_skills(skill_id)')

            # 既存DBへの embedding カラム追加
            try:
                cursor.execute("ALTER TABLE projects ADD COLUMN embedding BLOB")
            except sqlite3.OperationalError:
                pass
                
            # 既存DB用のカラム追加処理（既に存在する場合はエラーになるため無視）
            try:
                cursor.execute("ALTER TABLE emails ADD COLUMN status TEXT DEFAULT 'pending'")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE emails ADD COLUMN simhash_val TEXT")
            except sqlite3.OperationalError:
                pass

            # 同期状態管理テーブル
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            ''')

            conn.commit()
            logging.info("Database initialized successfully.")

        except sqlite3.Error as e:
            logging.error(f"Database initialization failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_email(self, message_id: str, subject: str, sender: str, 
                  received_at: str, body: str, raw_data: Dict = None,
                  status: str = 'pending', simhash_val: str = None) -> bool:
        """メール原文を保存する"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM emails WHERE message_id = ?', (message_id,))
            if cursor.fetchone():
                return False

            cursor.execute('''
            INSERT INTO emails (message_id, subject, sender, received_at, body, raw_data, status, simhash_val)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (message_id, subject, sender, received_at, body, 
                  json.dumps(raw_data) if raw_data else None, status, simhash_val))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Failed to save email {message_id}: {e}")
            return False
        finally:
            conn.close()

    def get_sync_state(self, key: str) -> str:
        """同期状態（historyIdなど）を取得する"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM sync_state WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def set_sync_state(self, key: str, value: str):
        """同期状態を保存する"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO sync_state (key, value) VALUES (?, ?)', (key, str(value)))
            conn.commit()
        finally:
            conn.close()

    def get_email_status(self, message_id: str) -> str:
        """メールの処理状態を取得する"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM emails WHERE message_id = ?', (message_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def update_email_status(self, message_id: str, status: str):
        """メールの処理状態を更新する"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('UPDATE emails SET status = ? WHERE message_id = ?', (status, message_id))
            conn.commit()
        finally:
            conn.close()

    def get_existing_simhashes(self) -> List[str]:
        """重複判定用に既存のSimHash一覧を取得する（直近10000件程度）"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT simhash_val FROM emails WHERE simhash_val IS NOT NULL ORDER BY received_at DESC LIMIT 10000')
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def save_project(self, email_message_id: str, project_data: Dict, skills: List[Dict], embedding: bytes = None) -> int:
        """
        抽出された案件情報を保存する
        
        Args:
            email_message_id: 元メールのID
            project_data: 案件情報の辞書 (title, description, min_price...)
            skills: スキルリスト [{'name': 'Java', 'type': 'must'}, ...]
            embedding: 計算済みのベクトルデータ（bytes形式、オプション）
            
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
                location, commercial_flow, remote_type,
                embedding
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                project_data.get('remote_type'),
                embedding
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
            # クエリの基本部分を構築 (email_bodyも取得するよう変更)
            query_parts = ["SELECT p.*, e.received_at, e.body as email_body FROM projects p JOIN emails e ON p.email_message_id = e.message_id"]
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
            project_ids = []
            for row in cursor:
                # 辞書に変換
                row_dict = dict(row)
                row_dict['skills'] = []
                results.append(row_dict)
                project_ids.append(row_dict['id'])
                
            if project_ids:
                placeholders = ','.join('?' * len(project_ids))
                skill_cursor = conn.execute(f'''
                SELECT ps.project_id, s.name, ps.type 
                FROM skills s 
                JOIN project_skills ps ON s.id = ps.skill_id 
                WHERE ps.project_id IN ({placeholders})
                ''', project_ids)
                
                skills_by_project = {}
                for s in skill_cursor.fetchall():
                    pid = s['project_id']
                    if pid not in skills_by_project:
                        skills_by_project[pid] = []
                    skills_by_project[pid].append({'name': s['name'], 'type': s['type']})
                    
                for row_dict in results:
                    row_dict['skills'] = skills_by_project.get(row_dict['id'], [])
                    
            return results

        except sqlite3.Error as e:
            logging.error(f"Search failed: {e}")
            return []
        finally:
            conn.close()

    def search_projects_hybrid(self, query_text: str, query_embedding, limit: int = 300, min_price: int = None, max_price: int = None, remote_only: bool = False, date_threshold: str = None) -> List[Dict]:
        """BM25とベクトル類似度のハイブリッド検索を行う"""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            where_clauses = []
            params = []
            
            # ハードフィルタ
            if min_price:
                where_clauses.append("((p.min_price IS NOT NULL AND p.min_price >= ?) OR (p.min_price IS NULL AND p.max_price >= ?))")
                params.extend([min_price, min_price])
            if max_price:
                where_clauses.append("((p.max_price IS NOT NULL AND p.max_price <= ?) OR (p.max_price IS NULL AND p.min_price <= ?))")
                params.extend([max_price, max_price])
            if remote_only:
                where_clauses.append("(p.remote_type LIKE '%リモート%')")
            if date_threshold:
                where_clauses.append("e.received_at >= ?")
                params.append(date_threshold)
                
            fts_match = ""
            if query_text:
                safe_query = " OR ".join([f'"{q}"' for q in query_text.split() if q.strip()])
                if safe_query:
                    fts_match = f"projects_fts MATCH '{safe_query}'"

            base_sql = """
            SELECT p.id, p.title, p.description, p.min_price, p.max_price, 
                   p.location, p.commercial_flow, p.remote_type, p.embedding,
                   e.received_at, e.subject, e.sender, e.message_id
            FROM projects p
            JOIN emails e ON p.email_message_id = e.message_id
            """
            
            if fts_match:
                base_sql += f" JOIN projects_fts fts ON p.id = fts.rowid WHERE {fts_match}"
                if where_clauses:
                    base_sql += " AND " + " AND ".join(where_clauses)
            else:
                if where_clauses:
                    base_sql += " WHERE " + " AND ".join(where_clauses)
                    
            base_sql += " ORDER BY e.received_at DESC LIMIT 10000"
            
            cursor = conn.execute(base_sql, params)
            
            results = []
            import numpy as np
            from vector_engine import vector_engine
            
            for row in cursor:
                row_dict = dict(row)
                row_dict['skills'] = []
                emb_bytes = row_dict.pop('embedding', None)
                
                similarity = 0.0
                if emb_bytes and query_embedding is not None and len(query_embedding) > 0:
                    proj_emb = np.frombuffer(emb_bytes, dtype=np.float32)
                    similarity = vector_engine.calculate_similarity(query_embedding, proj_emb)
                    
                row_dict['vector_score'] = similarity
                results.append(row_dict)
                
            results.sort(key=lambda x: x['vector_score'], reverse=True)
            top_results = results[:limit]
            
            if top_results:
                project_ids = [r['id'] for r in top_results]
                placeholders = ','.join('?' * len(project_ids))
                skill_cursor = conn.execute(f'''
                SELECT ps.project_id, s.name, ps.type 
                FROM skills s 
                JOIN project_skills ps ON s.id = ps.skill_id 
                WHERE ps.project_id IN ({placeholders})
                ''', project_ids)
                
                skills_by_project = {}
                for s in skill_cursor.fetchall():
                    pid = s['project_id']
                    if pid not in skills_by_project:
                        skills_by_project[pid] = []
                    skills_by_project[pid].append({'name': s['name'], 'type': s['type']})
                    
                for row_dict in top_results:
                    row_dict['skills'] = skills_by_project.get(row_dict['id'], [])
                    
            return top_results
            
        except sqlite3.Error as e:
            import logging
            logging.error(f"Hybrid search failed: {e}")
            return []
        finally:
            conn.close()

    def save_feedback(self, project_id: int, candidate_skills: str, is_good: bool, comment: str = None) -> bool:
        """マッチング結果に対するフィードバックを保存する"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO match_feedback (project_id, candidate_skills, is_good, comment)
            VALUES (?, ?, ?, ?)
            ''', (project_id, candidate_skills, is_good, comment))
            conn.commit()
            return True
        except sqlite3.Error as e:
            import logging
            logging.error(f"Failed to save feedback: {e}")
            return False
        finally:
            conn.close()

# グローバルインスタンス
db_manager = DBManager()
