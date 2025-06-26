"""
高度なスキル抽出モジュール
- コンテキストを考慮したスキル抽出
- 経験年数の自動検出
- スキルの重要度スコアリング
- エンジニアタイプ分析
"""
import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import unicodedata

# エンジニアタイプの定義
ENGINEER_TYPES = {
    'フロントエンド': {
        'skills': ['HTML', 'CSS', 'JavaScript', 'TypeScript', 'React', 'Vue.js', 'Angular', 'Svelte', 'jQuery', 'Next.js', 'Nuxt.js', 'Webpack', 'Babel'],
        'weight': 1.0,
        'description': 'ユーザーインターフェースの開発を専門とするエンジニア。Webアプリケーションの見た目や操作性を担当。'
    },
    'バックエンド': {
        'skills': ['Python', 'Java', 'C#', 'Node.js', 'Django', 'Flask', 'FastAPI', 'Spring', 'Laravel', 'Ruby on Rails', 'Express', 'Go', 'Rust', 'PHP'],
        'weight': 1.0,
        'description': 'サーバーサイドのロジックやデータベース連携を担当するエンジニア。'
    },
    'インフラ/DevOps': {
        'skills': ['Docker', 'Kubernetes', 'AWS', 'Azure', 'GCP', 'CI/CD', 'Git', 'Terraform', 'Ansible', 'Jenkins', 'GitHub Actions', 'Linux', 'Nginx', 'Apache'],
        'weight': 1.2,
        'description': 'インフラ構築や運用自動化を専門とするエンジニア。クラウド環境の構築・運用も担当。'
    },
    'データサイエンティスト/MLエンジニア': {
        'skills': ['Python', 'R', 'SQL', 'pandas', 'numpy', 'scikit-learn', 'TensorFlow', 'PyTorch', 'Data Analysis', 'Machine Learning', 'Deep Learning', 'Keras', 'Jupyter', 'Tableau'],
        'weight': 1.1,
        'description': 'データ分析や機械学習モデルの開発・運用を専門とするエンジニア。'
    },
    'モバイル': {
        'skills': ['Swift', 'Kotlin', 'Flutter', 'React Native', 'iOS', 'Android', 'Xamarin', 'SwiftUI', 'Jetpack Compose'],
        'weight': 1.0,
        'description': 'スマートフォン向けアプリケーションの開発を専門とするエンジニア。'
    },
    'フルスタック': {
        'skills': ['JavaScript', 'TypeScript', 'Node.js', 'React', 'Vue.js', 'Python', 'Django', 'Flask', 'SQL', 'Docker', 'AWS'],
        'weight': 0.9,
        'description': 'フロントエンドからバックエンドまで幅広く対応できるエンジニア。'
    },
    'QA/テストエンジニア': {
        'skills': ['Selenium', 'Jest', 'pytest', 'JUnit', 'TestNG', 'Cypress', 'Playwright', 'Appium', 'JMeter'],
        'weight': 1.0,
        'description': 'ソフトウェアの品質保証やテストを専門とするエンジニア。'
    }
}

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
        # スキルDBのロードを確認
        self.skill_db = SKILL_DB
        self.alias_map = ALIAS_MAP
        
        # スキルDBのログ出力
        logging.info(f"スキルDBに {len(self.skill_db)} 件のスキルが登録されています")
        if len(self.skill_db) < 10:  # スキルが少なすぎる場合は警告
            logging.warning("スキルDBの登録数が少なすぎます。設定を確認してください。")
        
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
        logging.info("スキル抽出器の初期化が完了しました")
    
    def _build_skill_index(self):
        """スキル検索用のインデックスを構築"""
        self.skill_index = defaultdict(list)
        for skill, data in self.skill_db.items():
            # スキル名でインデックス
            self.skill_index[skill.lower()].append((skill, 1.0))  # 完全一致は重み1.0
            
            # エイリアスでインデックス
            for alias in data.get('aliases', []):
                self.skill_index[alias.lower()].append((skill, 0.9))  # エイリアスは重み0.9
                
    def analyze_engineer_type(self, skills: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        抽出されたスキルからエンジニアのタイプを分析
        
        Args:
            skills: 抽出されたスキルのリスト
            
        Returns:
            エンジニアタイプとスコアの辞書（スコアの降順でソート済み）
        """
        if not skills:
            return {}
            
        # スキル名のセットを作成（高速化のため）
        skill_set = {s['skill'].lower() for s in skills if isinstance(s, dict) and 'skill' in s}
        
        type_scores = {}
        
        for type_name, type_info in ENGINEER_TYPES.items():
            score = 0.0
            matched_skills = []
            
            # 各タイプに紐づくスキルとマッチング
            for skill in type_info['skills']:
                if skill.lower() in skill_set:
                    # 必須スキルの場合はスコアを高く
                    skill_data = next((s for s in skills 
                                    if isinstance(s, dict) 
                                    and s.get('skill', '').lower() == skill.lower()), {})
                    
                    skill_score = 1.5 if skill_data.get('is_required', False) else 1.0
                    matched_skills.append((skill, skill_score))
            
            # スコア計算（マッチしたスキル数 × 重み）
            if matched_skills:
                base_score = sum(score for _, score in matched_skills)
                type_scores[type_name] = {
                    'score': round(base_score * type_info['weight'], 2),
                    'description': type_info['description'],
                    'matched_skills': [s[0] for s in matched_skills]
                }
                
                # デバッグ用ログ
                logging.debug(f"タイプ '{type_name}' にマッチしたスキル: {', '.join([s[0] for s in matched_skills])} (スコア: {type_scores[type_name]['score']:.2f})")
        
        # スコアが0より大きいものだけをフィルタリングし、スコアの降順でソート
        sorted_types = dict(sorted(
            {k: v for k, v in type_scores.items() if v['score'] > 0}.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        ))
        
        return sorted_types
    
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
    
    def _calculate_skill_confidence(self, skill: str, context: str) -> float:
        """スキルの信頼度を計算（0.0 〜 1.0）"""
        confidence = 0.5  # デフォルトの信頼度
        context_lower = context.lower()
        skill_lower = skill.lower()
        
        # 1. ポジティブな指標（信頼度を上げる）
        # 経験年数が明記されている
        if re.search(rf'(?:{re.escape(skill_lower)}).*?(\d+\+?\s*(?:年|years?|yrs?|ヶ月|か月|months?|m|月))', context_lower):
            confidence += 0.2
            
        # スキルレベルが明記されている（上級、中級、初心者など）
        skill_levels = [
            (r'(?:上級|上級者|エキスパート|expert|senior|advanced)', 0.3),
            (r'(?:中級|中級者|intermediate|mid-level)', 0.2),
            (r'(?:初心者|初級|beginner|junior)', 0.1)
        ]
        for level_pattern, level_boost in skill_levels:
            if re.search(rf'(?:{re.escape(skill_lower)}).*?{level_pattern}', context_lower):
                confidence += level_boost
                break
                
        # プロジェクトや業務で使用したという文脈
        project_indicators = [
            r'開発(?:に)?使用', r'使用(?:した|経験あり)', r'実務経験', 
            r'開発経験', r'業務で使用', r'used in', r'worked with',
            r'developed with', r'built with'
        ]
        if any(re.search(indicator, context_lower) for indicator in project_indicators):
            confidence += 0.15
            
        # 2. ネガティブな指標（信頼度を下げる）
        # 興味がある、学びたい、今後挑戦したいなど
        negative_indicators = [
            r'興味あり', r'勉強中', r'学習中', r'学びたい', r'挑戦したい',
            r'今後取り組みたい', r'初心者です', r'これから学びたい', 'interest',
            r'learning', r'want to learn', r'plan to learn'
        ]
        if any(re.search(indicator, context_lower) for indicator in negative_indicators):
            confidence -= 0.2
            
        # 3. コンテキストの長さ（長いほど信頼度が上がる）
        if len(context) > 100:  # 長い文脈の場合は信頼度を少し上げる
            confidence += 0.05
            
        # 4. スキルがリスト形式で列挙されている（スキルセクションの可能性が高い）
        if re.search(rf'^\s*[•\-*]\s*{re.escape(skill_lower)}\s*$', context_lower, re.MULTILINE):
            confidence += 0.1
            
        # 信頼度を0.1〜1.0の範囲に収める
        return max(0.1, min(1.0, confidence))
        
    def extract_candidate_skills(self, text: str, min_confidence: float = 0.6):
        """
        テキストからスキル候補を抽出（コンテキスト付き）
        
        Args:
            text: 抽出対象のテキスト
            min_confidence: スキルとして認識する最小の信頼度 (0.0〜1.0)
            
        Returns:
            抽出されたスキルのリスト
        """
        logging.info(f"スキル抽出を開始: テキスト長={len(text)}, 最小信頼度={min_confidence}")
        
        if not text or not isinstance(text, str):
            logging.warning("無効な入力テキストです")
            return []
            
        skills_found = []
        text_lower = text.lower()
        
        # デバッグ用にテキストの先頭100文字をログに出力
        logging.debug(f"入力テキストの先頭: {text[:100]}...")
        
        # 必須スキルと尚可スキルを検出
        required_skills = set()
        preferred_skills = set()
        
        # 必須スキルセクションを検出
        required_match = re.search(r'【必須スキル】([^【]+)', text, re.DOTALL)
        if required_match:
            required_text = required_match.group(1).lower()
            required_skills.update(self._extract_skills_from_section(required_text))
        
        # 尚可スキルセクションを検出
        preferred_match = re.search(r'【尚可スキル】([^【]+)', text, re.DOTALL)
        if preferred_match:
            preferred_text = preferred_match.group(1).lower()
            preferred_skills.update(self._extract_skills_from_section(preferred_text))
        
        # スキルセクションを検索
        skill_sections = self._find_skill_sections(text)
        
        # セクションごとに処理
        for section in skill_sections:
            if not isinstance(section, dict) or 'text' not in section:
                continue
                
            section_text = section.get('text', '')
            section_lower = section_text.lower()
            
            # スキルDBからスキルを検索
            for skill, data in self.skill_db.items():
                # スキル名とエイリアスを検索パターンとして使用
                patterns = [skill.lower()] + [a.lower() for a in data.get('aliases', [])]
                
                for pattern in patterns:
                    # スキル名が含まれる位置を検索
                    for match in re.finditer(r'\b' + re.escape(pattern) + r'\b', section_lower):
                        start, end = match.span()
                        context = self._get_context(section_text, start, end)
                        
                        # 必須スキルかどうかをチェック
                        is_required = pattern in required_skills
                        is_preferred = pattern in preferred_skills
                        
                        # スキルの信頼度を計算
                        confidence = self._calculate_skill_confidence(skill, context)
                        
                        # 必須スキルの場合は信頼度を上げる
                        if is_required:
                            original_confidence = confidence
                            confidence = min(1.0, confidence * 1.5)  # 1.5倍にブースト
                            logging.debug(f"必須スキル検出: {skill} (信頼度: {original_confidence:.2f} -> {confidence:.2f})")
                        elif is_preferred:
                            original_confidence = confidence
                            confidence = min(1.0, confidence * 1.2)  # 1.2倍にブースト
                            logging.debug(f"尚可スキル検出: {skill} (信頼度: {original_confidence:.2f} -> {confidence:.2f})")
                            
                        if confidence < min_confidence:
                            logging.debug(f"スキル '{skill}' は信頼度 {confidence:.2f} が閾値 {min_confidence:.2f} 未満のためスキップ")
                            continue
                            
                        logging.debug(f"スキル検出: {skill} (信頼度: {confidence:.2f}, 重要度: {self._calculate_importance(skill, context):.2f})")
                            
                        # スキルの重要度を計算
                        importance = self._calculate_importance(skill, context)
                        
                        # 経験年数を抽出
                        experience = self._extract_experience(context, skill)
                        
                        # 既に同じスキルが抽出されていないか確認
                        existing_skill = next((s for s in skills_found if s['skill'].lower() == skill.lower()), None)
                        
                        if existing_skill:
                            # 既存のスキルより信頼度が高い場合は更新
                            if confidence > existing_skill.get('confidence', 0):
                                existing_skill.update({
                                    'context': context,
                                    'importance': importance,
                                    'confidence': confidence,
                                    'experience_years': experience or existing_skill.get('experience_years'),
                                    'is_required': is_required or existing_skill.get('is_required', False),
                                    'is_preferred': is_preferred or existing_skill.get('is_preferred', False)
                                })
                        else:
                            skills_found.append({
                                'skill': skill,
                                'type': data.get('type', 'other'),
                                'context': context,
                                'importance': importance,
                                'confidence': confidence,
                                'experience_years': experience,
                                'categories': data.get('categories', []),
                                'related_skills': data.get('related', []),
                                'source': 'skill_db',
                                'is_required': is_required,
                                'is_preferred': is_preferred
                            })
        
        # 信頼度でソート
        skills_found.sort(key=lambda x: x['confidence'], reverse=True)
        
        logging.info(f"スキル抽出完了: {len(skills_found)} 件のスキルを検出")
        if skills_found:
            logging.info(f"検出されたスキルトップ5: {[s['skill'] for s in skills_found[:5]]}")
        else:
            logging.warning("スキルが1つも検出されませんでした")
            # デバッグ用にスキルDBの内容を出力
            logging.debug(f"スキルDBの先頭5件: {list(self.skill_db.keys())[:5]}")
            logging.debug(f"入力テキストの一部: {text_lower[:200]}")
        
        return skills_found
        
    def _extract_skills_from_section(self, section_text: str) -> set:
        """
        スキルセクションからスキルを抽出する
        
        Args:
            section_text: スキルセクションのテキスト
            
        Returns:
            抽出されたスキルのセット
        """
        skills = set()
        
        # カンマや改行で区切られたスキルを抽出
        for item in re.split(r'[,\n、・]', section_text):
            item = item.strip()
            if not item:
                continue
                
            # スキルDBと照合
            for skill, data in self.skill_db.items():
                patterns = [skill.lower()] + [a.lower() for a in data.get('aliases', [])]
                if any(re.search(r'\b' + re.escape(p) + r'\b', item.lower()) for p in patterns):
                    skills.add(skill.lower())
                    
        return skills
    
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
            
    def _extract_experience(self, context: str, skill: str) -> Optional[float]:
        """コンテキストからスキルの経験年数を抽出する
        
        Args:
            context: スキルが含まれるテキスト
            skill: 抽出対象のスキル名
            
        Returns:
            経験年数（年単位）。見つからない場合はNone
        """
        if not context or not skill:
            return None
            
        # 経験年数のパターン（例: "3年"、"2.5 years"、"経験3年"）
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:年|years?|y)(?:間|程度|以上|以下)?',
            r'(\d+(?:\.\d+)?)\s*(?:years?|y)(?:\s*of experience|\s*exp)?',
            r'経験\s*(\d+(?:\.\d+)?)\s*(?:年|years?|y)',
            r'(\d+)\s*[+＋]?\s*(?:年|years?|y)'
        ]
        
        # スキル名の位置を取得
        skill_pos = context.lower().find(skill.lower())
        if skill_pos == -1:
            return None
            
        # スキル名の周辺テキストを取得（前後100文字）
        start_pos = max(0, skill_pos - 100)
        end_pos = min(len(context), skill_pos + len(skill) + 100)
        nearby_text = context[start_pos:end_pos]
        
        # 各パターンでマッチングを試みる
        for pattern in patterns:
            matches = list(re.finditer(pattern, nearby_text, re.IGNORECASE))
            if matches:
                # 最も近いマッチを選択
                closest_match = min(
                    matches,
                    key=lambda m: abs(m.start() - (skill_pos - start_pos))
                )
                try:
                    years = float(closest_match.group(1))
                    # スキル名との距離が近い場合のみ採用
                    if abs(closest_match.start() - (skill_pos - start_pos)) < 50:
                        return years
                except (ValueError, IndexError):
                    continue
                    
        return None
    
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
        
        # 経験年数のパターン
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:年|years?|y)(?:間|程度|以上|以下)?',
            r'(\d+(?:\.\d+)?)\s*(?:years?|y)(?:\s*of experience|\s*exp)?',
            r'経験\s*(\d+(?:\.\d+)?)\s*(?:年|years?|y)'
        ]
        
        # 経験年数に基づくスコア調整
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
    
    def categorize_skills(self, skills: Union[List[Dict], List[str], Dict[str, List]]) -> Dict[str, List[Dict]]:
        """スキルをカテゴリ別に分類
        
        Args:
            skills: スキルのリストまたは辞書。各要素は辞書、文字列、または文字列のリスト
            
        Returns:
            カテゴリ別に分類されたスキルの辞書
        """
        categories = {category: [] for category in SKILL_CATEGORIES.values()}
        categories['その他'] = []
        
        # スキルがNoneまたは空の場合は空のカテゴリを返す
        if not skills:
            return categories
            
        # 既にカテゴリ分けされた辞書が渡された場合はそのまま返す
        if isinstance(skills, dict):
            return skills
            
        processed_skills = set()  # 重複を防ぐためのセット（小文字で比較）
        
        for skill_data in skills:
            # スキルデータが文字列の場合は辞書に変換
            if isinstance(skill_data, str):
                skill_data = {
                    'skill': skill_data,
                    'name': skill_data,
                    'type': 'other',
                    'confidence': 0.5,
                    'importance': 0.5,
                    'source': 'unknown'
                }
            # 辞書でない場合はスキップ
            elif not isinstance(skill_data, dict):
                logging.warning(f"無効なスキルデータをスキップ: {skill_data}")
                continue
                
            # スキル名を取得
            skill_name = str(skill_data.get('skill', '') or skill_data.get('name', '')).strip()
            if not skill_name:
                logging.warning(f"スキル名が空のエントリをスキップ: {skill_data}")
                continue
                
            # スキル名を正規化して重複をチェック
            normalized_name = self.normalize_skill(skill_name)
            if normalized_name in processed_skills:
                logging.debug(f"重複するスキルをスキップ: {skill_name}")
                continue
                
            # スキルのメタデータを取得
            skill_type = str(skill_data.get('type', 'other')).lower()
            
            # 信頼度と重要度の取得（型チェック付き）
            try:
                skill_confidence = float(skill_data.get('confidence', 0.5) or 0.5)
                skill_importance = float(skill_data.get('importance', 0.5) or 0.5)
            except (TypeError, ValueError) as e:
                logging.warning(f"スキルの信頼度/重要度の変換エラー: {e}")
                skill_confidence = 0.5
                skill_importance = 0.5
            
            # カテゴリを決定
            category = 'その他'  # デフォルトカテゴリ
            
            # スキルDBに基づいてカテゴリを決定
            skill_info = self.skill_db.get(skill_name.title(), {}) or \
                       self.skill_db.get(skill_name.upper(), {}) or \
                       self.skill_db.get(skill_name.lower(), {})
            
            if skill_info:
                skill_type = skill_info.get('type', skill_type)
                skill_category = skill_info.get('category')
                if skill_category and skill_category in categories:
                    category = skill_category
            
            # スキルエントリを作成
            skill_entry = {
                'skill': skill_name,
                'name': skill_name,  # 互換性のため両方のキーを設定
                'type': skill_type,
                'confidence': skill_confidence,
                'importance': skill_importance,
                'source': str(skill_data.get('source', 'unknown'))
            }
            
            # その他の情報があれば追加
            for key, value in skill_data.items():
                if key not in ['skill', 'name', 'type', 'confidence', 'importance', 'source'] and value is not None:
                    skill_entry[key] = value
            
            # カテゴリにスキルを追加
            categories[category].append(skill_entry)
            processed_skills.add(normalized_name)
            
            logging.debug(f"スキルをカテゴリに追加: {skill_name} -> {category}")
        
        # 重要度と信頼度でソート
        for category in categories:
            try:
                categories[category].sort(
                    key=lambda x: (
                        -float(x.get('importance', 0.5) or 0.5),
                        -float(x.get('confidence', 0.5) or 0.5)
                    )
                )
            except (TypeError, ValueError):
                # ソートに失敗した場合はそのまま
                pass
            
        # 空のカテゴリを削除
        return {k: v for k, v in categories.items() if v}
        
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
    
    def extract_skills(self, text: str, min_confidence: float = 0.6, use_rezume: bool = True, use_external: bool = None) -> Dict[str, List[Dict]]:
        """
        テキストからスキルを抽出し、カテゴリ別に分類して返す
        
        Args:
            text: 抽出対象のテキスト
            min_confidence: スキルとして認識する最小の信頼度 (0.0〜1.0)
            use_rezume: Rezume Parser を使用するかどうか
            use_external: 外部スキルサービスを使用するかどうか（Noneの場合は設定に従う）
            
        Returns:
            カテゴリ別に分類されたスキルの辞書
        """
        if not text:
            return {}
            
        # 前処理
        text = self.preprocess_text(text)
        
        # 候補スキルを抽出（信頼度付き）
        candidate_skills = []
        
        # 基本のスキル抽出を試みる
        try:
            base_skills = self.extract_candidate_skills(text, min_confidence)
            if isinstance(base_skills, list):
                candidate_skills.extend(base_skills)
        except Exception as e:
            logging.error(f"基本スキル抽出中にエラーが発生しました: {str(e)}")
        
        # Rezume Parser を使用する場合
        if use_rezume and self.rezume_parser:
            try:
                if hasattr(self.rezume_parser, 'extract_skills'):
                    logging.info("Rezume Parser を使用してスキルを抽出中...")
                    rezume_skills = self.rezume_parser.extract_skills(text)
                    if isinstance(rezume_skills, list):
                        logging.info(f"Rezume Parser から {len(rezume_skills)} 件のスキルを取得")
                        for skill_data in rezume_skills:
                            if not isinstance(skill_data, dict):
                                continue
                                
                            # Rezume Parser の形式に合わせてスキル名を取得
                            skill = skill_data.get('name')  # Rezume Parser では 'name' にスキル名が入っている
                            if not skill:
                                continue
                                
                            # コンテキストを取得
                            context = ''
                            if 'start' in skill_data and 'end' in skill_data:
                                start = max(0, skill_data['start'] - 50)
                                end = min(len(text), skill_data['end'] + 50)
                                context = text[start:end]
                            
                            # 既存のスキルを検索
                            existing_skill = next((s for s in candidate_skills 
                                               if isinstance(s, dict) 
                                               and s.get('skill', '').lower() == skill.lower()), None)
                            
                            # スキルの信頼度を計算（Rezume Parser の場合はデフォルトで0.8）
                            skill_confidence = 0.8
                            
                            if existing_skill:
                                # 既存のスキルの信頼度を更新（高い方を採用）
                                existing_confidence = float(existing_skill.get('confidence', 0) or 0)
                                if skill_confidence > existing_confidence:
                                    existing_skill['confidence'] = skill_confidence
                                    existing_skill['source'] = 'rezume_parser'
                                    if context:
                                        existing_skill['context'] = context
                            else:
                                # 新しいスキルを追加
                                candidate_skills.append({
                                    'skill': skill,
                                    'type': skill_data.get('type', 'other').lower(),
                                    'context': context,
                                    'importance': 0.5,  # デフォルト値
                                    'confidence': skill_confidence,
                                    'experience_years': None,  # 経験年数は後で抽出
                                    'categories': [],
                                    'related_skills': [],
                                    'source': 'rezume_parser',
                                    'is_required': False,
                                    'is_preferred': False
                                })
                                
                                logging.debug(f"Rezume Parser からスキルを追加: {skill} (信頼度: {skill_confidence})")
                else:
                    logging.warning("Rezume Parser に extract_skills メソッドが存在しません")
            except Exception as e:
                logging.error(f"Rezume Parser でのスキル抽出中にエラーが発生しました: {str(e)}")
        
        # 外部サービスを使用する場合
        if use_external is None:
            use_external = self.enable_external_skills
            
        if use_external and self.external_service:
            try:
                if hasattr(self.external_service, 'extract_skills'):
                    external_skills = self.external_service.extract_skills(text)
                    if isinstance(external_skills, list):
                        for skill_data in external_skills:
                            if not isinstance(skill_data, dict):
                                continue
                                
                            skill = skill_data.get('skill')
                            if not skill:
                                continue
                                
                            # 既存のスキルを検索
                            existing_skill = next((s for s in candidate_skills if isinstance(s, dict) and s.get('skill', '').lower() == skill.lower()), None)
                            
                            if existing_skill:
                                # 既存のスキルの信頼度を更新（高い方を採用）
                                existing_confidence = float(existing_skill.get('confidence', 0) or 0)
                                new_confidence = float(skill_data.get('confidence', 0.5) or 0.5)
                                if new_confidence > existing_confidence:
                                    existing_skill['confidence'] = new_confidence
                                    existing_skill['source'] = 'external_service'
                            else:
                                # 新しいスキルを追加（信頼度が閾値以上の場合のみ）
                                skill_confidence = float(skill_data.get('confidence', 0.5) or 0.5)
                                if skill_confidence >= min_confidence:
                                    candidate_skills.append({
                                        'skill': skill,
                                        'type': skill_data.get('type', 'other'),
                                        'context': skill_data.get('context', ''),
                                        'importance': float(skill_data.get('importance', 0.5) or 0.5),
                                        'confidence': skill_confidence,
                                        'experience_years': skill_data.get('experience_years'),
                                        'categories': skill_data.get('categories', []),
                                        'related_skills': skill_data.get('related_skills', []),
                                        'source': 'external_service'
                                    })
            except Exception as e:
                logging.error(f"外部スキルサービスでのスキル抽出中にエラーが発生しました: {str(e)}")
        
        # candidate_skills が None の場合の処理を追加
        if candidate_skills is None:
            candidate_skills = []
        
        # スキルをカテゴリ別に分類
        categorized_skills = self.categorize_skills(candidate_skills)
        
        # 各カテゴリ内で信頼度順にソート
        for category, skills in categorized_skills.items():
            try:
                if isinstance(skills, list):
                    categorized_skills[category] = sorted(
                        skills,
                        key=lambda x: (float(x.get('confidence', 0) or 0), float(x.get('importance', 0) or 0)),
                        reverse=True
                    )
            except Exception as e:
                logging.error(f"スキルのソート中にエラーが発生しました: {str(e)}")
        
        # エンジニアタイプを分析
        engineer_types = self.analyze_engineer_type(candidate_skills)
        
        # エンジニアタイプをスキルとして追加
        if engineer_types:
            # スコアが0.3以上のエンジニアタイプを追加
            for eng_type, data in engineer_types.items():
                if data.get('score', 0) >= 0.3:
                    categorized_skills.setdefault('engineer_types', []).append({
                        'skill': eng_type,
                        'name': eng_type,
                        'type': 'engineer_type',
                        'confidence': float(data.get('score', 0.5)),
                        'importance': 0.7,  # エンジニアタイプは重要度を高めに設定
                        'source': 'skill_analyzer',
                        'categories': ['エンジニアタイプ']
                    })
            
            # 主要なエンジニアタイプをログに記録
            primary_type = next(iter(engineer_types), None)
            if primary_type:
                logging.info(f"主なエンジニアタイプ: {primary_type} (スコア: {engineer_types[primary_type]['score']:.2f})")
        
        return categorized_skills
    
    def format_skills_output(self, categorized_skills: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """スキルを表示用にフォーマット
        
        Args:
            categorized_skills: カテゴリ別に分類されたスキルの辞書
            
        Returns:
            フォーマットされたスキル情報の辞書
        """
        formatted = {}
        
        # categorized_skills が None または辞書でない場合は空の辞書を返す
        if not isinstance(categorized_skills, dict):
            return {}
        
        for category, skills in categorized_skills.items():
            # スキルが文字列の場合は、それをスキル名とする辞書のリストに変換
            if isinstance(skills, str):
                skills = [{'skill': skills}]
            # スキルがリストでない場合は空のリストを使用
            elif not isinstance(skills, list):
                skills = []
                
            formatted_skills = []
            
            for skill in skills:
                # スキルが文字列の場合は辞書に変換
                if isinstance(skill, str):
                    skill = {
                        'skill': skill,
                        'type': 'other',
                        'confidence': 0.5,
                        'source': 'unknown'
                    }
                # スキルが辞書でない場合はスキップ
                elif not isinstance(skill, dict):
                    continue
                    
                # スキル名を取得
                skill_name = skill.get('skill') or skill.get('name') or str(skill)
                if not skill_name:
                    continue
                    
                # 信頼度が低いスキルはスキップ
                try:
                    confidence = float(skill.get('confidence', 0) or 0)
                    if confidence < 0.3:
                        continue
                except (TypeError, ValueError):
                    confidence = 0.5
                
                # 重要度の取得
                try:
                    importance = float(skill.get('importance', 0.5) or 0.5)
                except (TypeError, ValueError):
                    importance = 0.5
                
                # スキル情報を整形
                formatted_skill = {
                    'name': skill_name,
                    'type': str(skill.get('type', 'other')).lower(),
                    'confidence': confidence,
                    'importance': importance,
                    'experience': skill.get('experience_years'),
                    'context': str(skill.get('context', '')),
                    'categories': skill.get('categories', []),
                    'related_skills': skill.get('related_skills', []),
                    'source': str(skill.get('source', 'unknown'))
                }
                
                # 型チェックと変換
                if not isinstance(formatted_skill['categories'], list):
                    formatted_skill['categories'] = []
                if not isinstance(formatted_skill['related_skills'], list):
                    formatted_skill['related_skills'] = []
                    
                formatted_skills.append(formatted_skill)
            
            # 信頼度と重要度でソート
            try:
                formatted_skills.sort(
                    key=lambda x: (x.get('confidence', 0), x.get('importance', 0)),
                    reverse=True
                )
            except (TypeError, KeyError) as e:
                logging.warning(f"スキルのソート中にエラーが発生しました: {str(e)}")
            
            if formatted_skills:
                formatted[category] = formatted_skills
        
        return formatted

# シングルトンインスタンス
skill_extractor = SkillExtractor()
