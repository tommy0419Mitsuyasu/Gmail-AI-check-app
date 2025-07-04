import re
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import logging

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SkillMatch:
    skill: str
    matched_terms: List[str]
    confidence: float

class SimpleSkillMatcher:
    def __init__(self):
        self._initialize_skill_categories()
    
    def _initialize_skill_categories(self):
        """スキルカテゴリを初期化する"""
        self.skill_categories = {
            'programming_languages': {
                'python': ['python', 'py', 'python3', 'python2'],
                'javascript': ['javascript', 'js', 'ecmascript', 'es6', 'es2015'],
                'typescript': ['typescript', 'ts'],
                'java': ['java', 'j2ee', 'j2se', 'j2me'],
                'csharp': ['c#', 'csharp', '.net'],
                'cpp': ['c++', 'cpp', 'c plus plus'],
                'php': ['php'],
                'ruby': ['ruby', 'rb'],
                'go': ['go', 'golang'],
                'swift': ['swift'],
                'kotlin': ['kotlin', 'kt'],
                'scala': ['scala'],
                'rust': ['rust'],
                'dart': ['dart'],
                'r': ['r', 'rlang'],
                'matlab': ['matlab'],
            },
            'frameworks': {
                'django': ['django'],
                'flask': ['flask'],
                'fastapi': ['fastapi'],
                'spring': ['spring', 'spring boot', 'spring framework'],
                'ruby on rails': ['rails', 'ruby on rails', 'ror'],
                'laravel': ['laravel'],
                'express': ['express', 'express.js'],
                'react': ['react', 'react.js', 'reactjs'],
                'vue': ['vue', 'vue.js', 'vuejs'],
                'angular': ['angular', 'angular.js', 'angularjs'],
                'nextjs': ['next', 'next.js', 'nextjs'],
                'nuxtjs': ['nuxt', 'nuxt.js', 'nuxtjs'],
                'svelte': ['svelte'],
                'tensorflow': ['tensorflow', 'tf'],
                'pytorch': ['pytorch', 'torch'],
                'keras': ['keras'],
            },
            'cloud': {
                'aws': ['aws', 'amazon web services'],
                'azure': ['azure', 'microsoft azure'],
                'gcp': ['gcp', 'google cloud', 'google cloud platform'],
                'docker': ['docker'],
                'kubernetes': ['kubernetes', 'k8s'],
                'terraform': ['terraform'],
                'ansible': ['ansible'],
                'jenkins': ['jenkins'],
                'github actions': ['github actions', 'gh actions'],
                'gitlab ci': ['gitlab ci', 'gitlab-ci'],
            },
            'databases': {
                'mysql': ['mysql'],
                'postgresql': ['postgresql', 'postgres', 'pg'],
                'mongodb': ['mongodb', 'mongo'],
                'redis': ['redis'],
                'oracle': ['oracle', 'oracle db', 'oracledb'],
                'sql server': ['sql server', 'mssql', 'microsoft sql server'],
                'sqlite': ['sqlite', 'sqlite3'],
                'dynamodb': ['dynamodb', 'dynamo db'],
                'cassandra': ['cassandra'],
                'elasticsearch': ['elasticsearch', 'elastic search', 'es'],
            },
            'methodologies': {
                'agile': ['agile', 'scrum', 'kanban'],
                'devops': ['devops'],
                'ci/cd': ['ci/cd', 'ci cd', 'continuous integration', 'continuous deployment'],
                'tdd': ['tdd', 'test driven development'],
                'bdd': ['bdd', 'behavior driven development'],
                'microservices': ['microservices', 'micro service', 'micro-service'],
                'rest': ['rest', 'restful'],
                'graphql': ['graphql', 'gql'],
                'grpc': ['grpc', 'gRPC'],
            }
        }
        
        # スキルの正規化マップを作成
        self.skill_normalization_map = {}
        self.skill_aliases = {}
        
        for category, skills in self.skill_categories.items():
            for skill, aliases in skills.items():
                self.skill_aliases[skill] = aliases
                for alias in aliases + [skill]:
                    self.skill_normalization_map[alias] = skill

    def normalize_skill(self, skill: str) -> str:
        """スキル名を正規化する"""
        return self.skill_normalization_map.get(skill.lower(), skill.lower())

    def extract_skills_from_text(self, text: str) -> Dict[str, SkillMatch]:
        """テキストからスキルを抽出する"""
        text_lower = text.lower()
        found_skills = {}
        
        # スキルを検索
        for category, skills in self.skill_categories.items():
            for skill, aliases in skills.items():
                # 正規表現パターンを作成（単語境界を考慮）
                search_terms = aliases + [skill]
                
                for term in search_terms:
                    # 単語境界を考慮したパターン
                    pattern = r'(?<![\w-])' + re.escape(term) + r'(?![\w-])'
                    matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                    
                    for match in matches:
                        matched_term = match.group(0).lower()
                        # 既に見つかっている場合は、より長いマッチを優先
                        if skill not in found_skills or len(matched_term) > len(found_skills[skill].matched_terms[0]):
                            # 信頼度を計算（完全一致は1.0、部分一致は0.8）
                            confidence = 1.0 if matched_term.lower() == skill.lower() else 0.8
                            found_skills[skill] = SkillMatch(
                                skill=skill,
                                matched_terms=[matched_term],
                                confidence=confidence
                            )
                        elif skill in found_skills:
                            # 既存のマッチに用語を追加
                            if matched_term not in found_skills[skill].matched_terms:
                                found_skills[skill].matched_terms.append(matched_term)
        
        return found_skills

# テスト用のコード
if __name__ == "__main__":
    print("シンプルなスキルマッチャーのテストを開始します...")
    matcher = SimpleSkillMatcher()
    
    # テスト用のテキスト
    test_text = """
    私はPythonとJavaScriptでの開発経験が3年あります。
    最近はDjangoとReactを使ったWebアプリケーションを開発しています。
    また、AWSでのクラウド環境構築の経験もあります。
    
    スキル: Python 3.8+, JavaScript (ES6+), Django REST framework, React.js, AWS (S3, EC2)
    """
    
    print("\nテストテキスト:")
    print(test_text)
    
    print("\nテキストからスキルを抽出中...")
    skills = matcher.extract_skills_from_text(test_text)
    
    print("\n抽出されたスキル:")
    if skills:
        for skill, match in skills.items():
            print(f"- {skill}: 信頼度={match.confidence:.2f}, マッチ箇所={match.matched_terms}")
    else:
        print("スキルが見つかりませんでした。")
        
        # デバッグ用にカテゴリとスキルを表示
        print("\n登録されているスキルカテゴリ:")
        for category in matcher.skill_categories.keys():
            print(f"- {category}")
        
        print("\n登録されているスキルの例:")
        for i, (skill, aliases) in enumerate(matcher.skill_aliases.items()):
            if i >= 10:  # 最初の10個だけ表示
                print("...他")
                break
            print(f"- {skill} (エイリアス: {', '.join(aliases)})")
    
    print("\nテストが完了しました。")