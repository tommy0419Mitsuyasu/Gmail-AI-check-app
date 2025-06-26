"""
高度なスキル抽出モジュール
- コンテキストを考慮したスキル抽出
- 経験年数の自動検出
- スキルの重要度スコアリング
"""
import re
import os
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
import math
import logging

# Rezume Parser をインポート
try:
    from rezume_parser import RezumeParser
    REZUME_PARSER_AVAILABLE = True
except ImportError as e:
    REZUME_PARSER_AVAILABLE = False
    logging.warning(f"Rezume Parser が利用できません: {str(e)}")
    logging.warning("pip install nltk を実行してインストールしてください。")

# 外部モジュールのインポート
try:
    from .external_skill_service import external_skill_service
except ImportError:
    # 相対インポートに失敗した場合は絶対パスで再試行
    try:
        from external_skill_service import external_skill_service
    except ImportError:
        logging.warning("外部スキルサービスモジュールのインポートに失敗しました。外部スキル機能は無効化されます。")
        external_skill_service = None

# スキルの重要度キーワード
IMPORTANCE_KEYWORDS = {
    '経験': 0.3,
    '実務': 0.4,
    '開発': 0.2,
    '設計': 0.3,
    '運用': 0.2,
    '構築': 0.3,
    'リーダー': 0.4,
    '責任者': 0.5,
    'リード': 0.4,
    'メイン': 0.3
}

# スキルのカテゴリ
SKILL_CATEGORIES = {
    'language': 'プログラミング言語',
    'framework': 'フレームワーク',
    'cloud': 'クラウド/インフラ',
    'database': 'データベース',
    'devops': 'DevOps',
    'tool': '開発ツール',
    'platform': 'プラットフォーム',
    'other': 'その他'
}

# 拡張されたスキル辞書
SKILL_DB = {
    # プログラミング言語
    'Python': {
        'type': 'language',
        'aliases': ['py', 'python3', 'python2'],
        'categories': ['backend', 'data-science', 'automation', 'scripting'],
        'related': ['Django', 'Flask', 'FastAPI', 'pandas', 'numpy', 'scikit-learn']
    },
    'JavaScript': {'type': 'language', 'aliases': ['js', 'es6', 'es2015']},
    'TypeScript': {'type': 'language', 'aliases': ['ts']},
    'Java': {'type': 'language'},
    'C#': {'type': 'language', 'aliases': ['csharp']},
    'C++': {'type': 'language', 'aliases': ['cpp']},
    'Go': {'type': 'language', 'aliases': ['golang']},
    'Ruby': {'type': 'language'},
    'PHP': {'type': 'language'},
    'Swift': {'type': 'language'},
    'Kotlin': {'type': 'language'},
    'Rust': {'type': 'language'},
    'Scala': {'type': 'language'},
    'Dart': {'type': 'language'},
    
    # フレームワーク
    'Django': {'type': 'framework', 'category': 'backend'},
    'Flask': {'type': 'framework', 'category': 'backend'},
    'FastAPI': {'type': 'framework', 'category': 'backend'},
    'React': {'type': 'framework', 'category': 'frontend'},
    'Vue.js': {'type': 'framework', 'category': 'frontend', 'aliases': ['vue']},
    'Angular': {'type': 'framework', 'category': 'frontend'},
    'Node.js': {'type': 'framework', 'category': 'backend', 'aliases': ['node']},
    'Spring': {'type': 'framework', 'category': 'backend'},
    'Laravel': {'type': 'framework', 'category': 'backend'},
    'Ruby on Rails': {'type': 'framework', 'category': 'backend', 'aliases': ['rails']},
    'Express': {'type': 'framework', 'category': 'backend'},
    'Next.js': {'type': 'framework', 'category': 'frontend', 'aliases': ['next']},
    'Nuxt.js': {'type': 'framework', 'category': 'frontend', 'aliases': ['nuxt']},
    
    # クラウド/インフラ
    'AWS': {'type': 'cloud', 'category': 'infrastructure'},
    'Azure': {'type': 'cloud', 'category': 'infrastructure'},
    'GCP': {'type': 'cloud', 'category': 'infrastructure', 'aliases': ['Google Cloud']},
    'Docker': {'type': 'devops', 'category': 'container'},
    'Kubernetes': {'type': 'devops', 'category': 'container', 'aliases': ['k8s']},
    'Terraform': {'type': 'devops', 'category': 'iac'},
    'Ansible': {'type': 'devops', 'category': 'configuration'},
    'Jenkins': {'type': 'devops', 'category': 'ci_cd'},
    'GitHub Actions': {'type': 'devops', 'category': 'ci_cd'},
    'GitLab CI/CD': {'type': 'devops', 'category': 'ci_cd'},
    
    # データベース
    'MySQL': {'type': 'database', 'category': 'relational'},
    'PostgreSQL': {'type': 'database', 'category': 'relational', 'aliases': ['postgres']},
    'MongoDB': {'type': 'database', 'category': 'nosql'},
    'Redis': {'type': 'database', 'category': 'key-value'},
    'Elasticsearch': {'type': 'database', 'category': 'search'},
    'Oracle': {'type': 'database', 'category': 'relational'},
    'SQL Server': {'type': 'database', 'category': 'relational'},
    'SQLite': {'type': 'database', 'category': 'relational'},
}

# エイリアスの逆引き辞書を作成
ALIAS_MAP = {}
for skill, data in SKILL_DB.items():
    ALIAS_MAP[skill.lower()] = skill
    for alias in data.get('aliases', []):
        ALIAS_MAP[alias.lower()] = skill

class SkillExtractor:
    def __init__(self, enable_external_skills: bool = False):
        """
        スキル抽出器の初期化
        
        Args:
            enable_external_skills: 外部スキルサービスを有効にするかどうか
        """
        self.skill_db = SKILL_DB
        self.alias_map = ALIAS_MAP
        self.enable_external_skills = enable_external_skills
        self.external_service = external_skill_service if external_skill_service and enable_external_skills else None
        
        # Rezume Parser の初期化
        self.rezume_parser = RezumeParser() if REZUME_PARSER_AVAILABLE else None
        if self.rezume_parser:
            logging.info("Rezume Parser が有効化されました。")
        else:
            logging.warning("Rezume Parser は無効です。スキル抽出は基本機能のみが使用されます。")
        
        if self.enable_external_skills and not self.external_service:
            logging.warning("外部スキルサービスが有効ですが、初期化に失敗しました。外部スキル機能は無効化されます。")
            self.enable_external_skills = False
            
        self._build_skill_index()
    
    def _build_skill_index(self):
        """スキル検索用のインデックスを構築"""
        self.skill_index = defaultdict(list)
        for skill, data in self.skill_db.items():
            # スキル名でインデックス
            for word in skill.lower().split():
                self.skill_index[word].append((skill, data))
            # エイリアスでもインデックス
            for alias in data.get('aliases', []):
                for word in alias.lower().split():
                    self.skill_index[word].append((skill, data))
    
    def preprocess_text(self, text: str) -> str:
        """テキストの前処理"""
        if not text:
            return ""
            
        # 改行とタブをスペースに変換
        text = text.replace('\n', ' ').replace('\t', ' ')
        # 連続するスペースを1つに
        text = re.sub(r'\s+', ' ', text)
        # 特殊文字を適切に処理
        text = re.sub(r'[^\w\s#+.-]', ' ', text)
        return text.strip()
    
    def extract_candidate_skills(self, text: str) -> List[Dict]:
        """テキストからスキル候補を抽出（コンテキスト付き）"""
        skills_found = []
        text_lower = text.lower()
        
        # 1. スキルセクションを特定する
        skill_sections = self._find_skill_sections(text)
        
        # 2. スキルセクション内でのみスキルを抽出
        for section in skill_sections:
            # セクションに必要なキーがあるか確認
            if not isinstance(section, dict) or 'text' not in section:
                continue
                
            section_text = section.get('text', '')
            section_lower = section_text.lower()
            
            # 3. 既知のスキルを直接マッチング
            for skill, data in self.skill_db.items():
                # スキル名とエイリアスで検索
                patterns = [skill.lower()] + [a.lower() for a in data.get('aliases', [])]
                
                for pattern in patterns:
                    for match in re.finditer(r'\b' + re.escape(pattern) + r'\b', section_lower):
                        start, end = match.span()
                        context = self._get_context(section_text, start, end)
                        
                        # スキルの重要度を計算
                        importance = self._calculate_importance(skill, context)
                        
                        # 経験年数を抽出
                        experience = self._extract_experience(context, skill)
                        
                        # スキルが既に追加されていないか確認
                        skill_exists = any(s['skill'] == skill for s in skills_found)
                        
                        if not skill_exists:
                            skills_found.append({
                                'skill': skill,
                                'type': data['type'],
                                'context': context,
                                'importance': importance,
                                'experience_years': experience,
                                'categories': data.get('categories', []),
                                'related_skills': data.get('related', [])
                            })
        
        # 2. 大文字で始まる専門用語を抽出（新規スキルの検出）
        words = re.findall(r'(?:^|\s)([A-Z][a-z]+(?:[A-Z][a-z]+)*)', text)
        for word in words:
            if word not in self.skill_db:  # 既知のスキルでない場合のみ処理
                context = self._get_context(text, text.find(word), text.find(word) + len(word))
                skills_found.append({
                    'skill': word,
                    'type': 'other',
                    'context': context,
                    'importance': self._calculate_importance(word, context),
                    'experience_years': self._extract_experience(context, word),
                    'categories': [],
                    'related_skills': []
                })
        
        return skills_found
    
    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """スキル周辺のコンテキストを取得"""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()
    
    def _find_skill_sections(self, text: str) -> List[Dict]:
        """スキルが記載されているセクションを特定する
        
        Args:
            text: 検索対象のテキスト
            
        Returns:
            セクションのリスト。各セクションは以下のキーを持つ辞書:
            - text: セクションのテキスト
            - type: セクションのタイプ（'skills', 'experience' など）
        """
        if not text:
            return [{'text': '', 'type': 'full_text'}]
            
        sections = []
        
        # スキル関連の見出しパターン
        skill_headers = [
            r'スキル',
            r'技術',
            r'資格',
            r'できること',
            r'得意',
            r'経験技術',
            r'skills?',
            r'qualifications?',
            r'certifications?',
            r'technologies?',
            r'abilities',
            r'competencies'
        ]
        
        # 経験関連の見出しパターン
        exp_headers = [
            r'経験',
            r'職務経歴',
            r'職歴',
            r'経験業務',
            r'実務経験',
            r'experience',
            r'work history',
            r'employment',
            r'professional experience',
            r'work experience'
        ]
        
        # セクションを分割
        lines = text.split('\n')
        current_section = []
        current_type = 'other'
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # セクションヘッダーを検出
            is_skill_header = any(re.search(pat, line, re.IGNORECASE) for pat in skill_headers)
            is_exp_header = any(re.search(pat, line, re.IGNORECASE) for pat in exp_headers)
            
            if is_skill_header or is_exp_header:
                # 現在のセクションを保存
                if current_section:
                    sections.append({
                        'text': '\n'.join(current_section),
                        'type': current_type
                    })
                
                # 新しいセクションを開始
                current_section = [line]
                current_type = 'skills' if is_skill_header else 'experience'
            else:
                current_section.append(line)
        
        # 最後のセクションを追加
        if current_section:
            sections.append({
                'text': '\n'.join(current_section),
                'type': current_type
            })
        
        # スキルセクションがない場合は全文を1つのセクションとして扱う
        if not sections or not any(s.get('type') == 'skills' for s in sections):
            return [{'text': text, 'type': 'full_text'}]
        
        # 各セクションに必要なキーが存在することを確認
        valid_sections = []
        for section in sections:
            if 'text' in section and 'type' in section:
                valid_sections.append({
                    'text': section['text'],
                    'type': section['type']
                })
            
        return valid_sections if valid_sections else [{'text': text, 'type': 'full_text'}]
    
    def _calculate_importance(self, skill: str, context: str) -> float:
        """スキルの重要度を計算"""
        score = 0.0
        context_lower = context.lower()
        
        # 出現回数（重みを下げる）
        count = context_lower.count(skill.lower())
        score += min(count * 0.1, 0.5)  # 最大0.5
        
        # 大文字表記（固有名詞としての重要度）
        if skill[0].isupper() and skill in context:
            score += 0.3
            
        # 重要キーワードとの共起
        for keyword, weight in IMPORTANCE_KEYWORDS.items():
            if keyword in context:
                score += weight
        
        # スキルが文の先頭にある場合
        if context.strip().startswith(skill):
            score += 0.2
            
        return min(score, 1.0)  # 最大1.0に正規化
    
    def extract_skills(self, text: str, use_rezume: bool = True, use_external: bool = None) -> Dict[str, List[Dict]]:
        """
        テキストからスキルを抽出
        
        Args:
            text: 抽出元のテキスト
            use_rezume: Rezume Parser を使用するかどうか
            use_external: 外部サービスを使用するかどうか（Noneの場合は設定に従う）
            
        Returns:
            カテゴリ別に分類されたスキルの辞書
        """
        if not text.strip():
            return {}
            
        # テキストの前処理
        text = self.preprocess_text(text)
        
        # スキル候補を抽出
        candidate_skills = self.extract_candidate_skills(text)
        
        # Rezume Parser を使用する場合
        if use_rezume and self.rezume_parser:
            try:
                parsed_data = self.rezume_parser.parse_resume(text)
                for skill in parsed_data.get('skills', []):
                    skill_name = skill.get('name', '')
                    if skill_name and not any(s['skill'].lower() == skill_name.lower() for s in candidate_skills):
                        candidate_skills.append({
                            'skill': skill_name,
                            'type': skill.get('type', 'TECH'),
                            'context': '',
                            'importance': 0.7,  # デフォルトの重要度
                            'experience_years': parsed_data.get('experience_years', 0)
                        })
                logging.info(f"Rezume Parser により {len(parsed_data.get('skills', []))} 個のスキルを追加")
            except Exception as e:
                logging.error(f"Rezume Parser の使用中にエラーが発生しました: {str(e)}")
        
        # 外部サービスを使用する場合
        if (use_external is None and self.enable_external_skills) or use_external:
            if self.external_service and self.external_service.enabled:
                try:
                    # 外部サービスから関連スキルを取得
                    enhanced_skills = self.external_service.enhance_skill_extraction(
                        candidate_skills, text
                    )
                    # 重複を避けてスキルを追加
                    skill_names = {s["skill"].lower() for s in candidate_skills}
                    for skill in enhanced_skills:
                        if skill["name"].lower() not in skill_names:
                            candidate_skills.append({
                                'skill': skill['name'],
                                'type': skill.get('type', 'TECH'),
                                'context': '',
                                'importance': skill.get('importance', 0.5),
                                'experience_years': skill.get('experience_years', 0)
                            })
                            skill_names.add(skill["name"].lower())
                except Exception as e:
                    logging.error(f"外部スキルサービスの使用中にエラーが発生しました: {str(e)}")
        
        # スキルをカテゴリ別に分類
        categorized_skills = self.categorize_skills(candidate_skills)
        
        return categorized_skills
        
    def _extract_experience(self, context: str, skill: str) -> Optional[float]:
        """スキルに関連する経験年数を抽出"""
        # パターン1: 「X年(間)」
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:年|years?|y)(?:間|程度|以上|以下)?',
            r'(\d+(?:\.\d+)?)\s*(?:years?|y)(?:\s*of experience|\s*exp)?',
            r'経験\s*(\d+(?:\.\d+)?)\s*(?:年|years?|y)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, context, re.IGNORECASE)
            for match in matches:
                try:
                    years = float(match.group(1))
                    # スキル名が近くにあるか確認
                    skill_pos = context.lower().find(skill.lower())
                    if skill_pos != -1 and abs(match.start() - skill_pos) < 50:
                        return years
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def normalize_skill(self, skill: str) -> Optional[str]:
        """スキル名を正規化"""
        if not skill:
            return None
            
        skill = skill.strip()
        
        # 既知のエイリアスで検索
        normalized = self.alias_map.get(skill.lower())
        if normalized:
            return normalized
        
        # バージョン番号を除去 (例: Python 3.8 → Python)
        base_skill = re.sub(r'\s*\d+(\.\d+)*\s*$', '', skill).strip()
        if base_skill and base_skill.lower() in self.alias_map:
            return self.alias_map[base_skill.lower()]
        
        return None
    
    def categorize_skills(self, skills: List[Dict]) -> Dict[str, List[Dict]]:
        """スキルをカテゴリ別に分類"""
        categories = {cat: [] for cat in SKILL_CATEGORIES.values()}
        
        for skill_data in skills:
            skill_type = skill_data.get('type', 'other')
            category = SKILL_CATEGORIES.get(skill_type, 'その他')
            categories[category].append(skill_data)
        
        # 重要度でソート
        for category in categories:
            categories[category].sort(key=lambda x: x.get('importance', 0), reverse=True)
            
        return categories
        
    def _find_skill_sections(self, text: str) -> List[Dict]:
        """スキルが記載されているセクションを特定する"""
        sections = []
            
        # スキルが記載されていそうな見出しを検索
        skill_headers = [
            r'スキル',
            r'技術スタック',
            r'開発経験',
            r'技術スキル',
            r'得意技術',
            r'経験技術',
            r'使用技術',
            r'開発環境',
            r'プログラミング言語',
            r'フレームワーク',
            r'ツール',
            r'インフラ',
            r'データベース'
        ]
        
        # テキストを行に分割
        lines = text.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 見出しかどうかをチェック
            is_header = any(header in line for header in skill_headers)
            
            if is_header:
                if current_section:
                    sections.append(current_section)
                current_section = {
                    'title': line,
                    'content': [],
                    'line_number': i + 1
                }
            elif current_section is not None:
                current_section['content'].append(line)
        
        # 最後のセクションを追加
        if current_section:
            sections.append(current_section)
            
        return sections
    
    def format_skills_output(self, categorized_skills: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """スキルを表示用にフォーマット"""
        formatted = {}
        
        for category, skills in categorized_skills.items():
            if skills:
                # 重要度の高い順にソート
                sorted_skills = sorted(
                    skills,
                    key=lambda x: x['importance'],
                    reverse=True
                )
                
                # 必要な情報のみを抽出
                formatted_skills = []
                for skill in sorted_skills:
                    formatted_skill = {
                        'name': skill['skill'],
                        'importance': skill['importance'],
                        'experience': skill.get('experience_years'),
                        'context': skill.get('context', ''),
                        'categories': skill.get('categories', []),
                        'related_skills': skill.get('related_skills', [])
                    }
                    formatted_skills.append(formatted_skill)
                
                formatted[category] = formatted_skills
        
        return formatted

# シングルトンインスタンス
skill_extractor = SkillExtractor()
