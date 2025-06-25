"""
高度なスキル抽出モジュール
- コンテキストを考慮したスキル抽出
- 経験年数の自動検出
- スキルの重要度スコアリング
"""
import re
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
import math

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
    def __init__(self):
        self.skill_db = SKILL_DB
        self.alias_map = ALIAS_MAP
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
        
        # 1. 既知のスキルを直接マッチング
        for skill, data in self.skill_db.items():
            # スキル名とエイリアスで検索
            patterns = [skill.lower()] + [a.lower() for a in data.get('aliases', [])]
            
            for pattern in patterns:
                for match in re.finditer(r'\b' + re.escape(pattern) + r'\b', text_lower):
                    start, end = match.span()
                    context = self._get_context(text, start, end)
                    
                    # スキルの重要度を計算
                    importance = self._calculate_importance(skill, context)
                    
                    # 経験年数を抽出
                    experience = self._extract_experience(context, skill)
                    
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
    
    def _calculate_importance(self, skill: str, context: str) -> float:
        """スキルの重要度を計算"""
        score = 0.0
        context_lower = context.lower()
        
        # 出現回数
        count = context_lower.count(skill.lower())
        score += min(count * 0.2, 1.0)  # 最大1.0
        
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
            categories[category].sort(key=lambda x: x['importance'], reverse=True)
            
        # 空のカテゴリを削除
        return {k: v for k, v in categories.items() if v}
    
    def extract_skills(self, text: str) -> Dict[str, List[Dict]]:
        """
        テキストからスキルを抽出するメイン関数
        
        Args:
            text: 解析対象のテキスト
            
        Returns:
            カテゴリ別に分類されたスキルの辞書
        """
        print("スキル抽出を開始します...")
        if not text:
            print("エラー: テキストが空です")
            return {}
            
        try:
            # テキストの前処理
            print("テキストの前処理を開始します...")
            text = self.preprocess_text(text)
            print(f"前処理後のテキスト長: {len(text)}文字")
            
            # スキル候補を抽出
            print("スキル候補を抽出しています...")
            candidate_skills = self.extract_candidate_skills(text)
            print(f"抽出されたスキル候補: {len(candidate_skills)}件")
            
            if not candidate_skills:
                print("警告: スキル候補が1つも見つかりませんでした")
                return {}
            
            # スキルを正規化して重複を削除
            print("スキルの正規化を実行中...")
            unique_skills = {}
            for skill_info in candidate_skills:
                normalized = self.normalize_skill(skill_info['skill'])
                if normalized:
                    if normalized not in unique_skills:
                        unique_skills[normalized] = skill_info
                        print(f"追加されたスキル: {normalized}")
                else:
                    print(f"スキルの正規化に失敗: {skill_info['skill']}")
            
            if not unique_skills:
                print("エラー: 有効なスキルが見つかりませんでした")
                return {}
            
            # スキルをカテゴリ別に分類
            print("スキルをカテゴリ別に分類中...")
            skills_list = list(unique_skills.values())
            categorized_skills = self.categorize_skills(skills_list)
            
            if not categorized_skills:
                print("警告: カテゴリ別に分類されたスキルがありません")
            else:
                for category, skills in categorized_skills.items():
                    print(f"カテゴリ '{category}': {len(skills)}スキル")
            
            return categorized_skills
            
        except Exception as e:
            print(f"スキル抽出中にエラーが発生しました: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}
            
        except Exception as e:
            print(f"スキル抽出中にエラーが発生しました: {str(e)}")
            return {cat: [] for cat in SKILL_CATEGORIES.values()}
    
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
