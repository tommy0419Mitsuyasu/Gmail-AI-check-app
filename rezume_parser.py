import re
import logging
from typing import Dict, List, Optional, Any
import string

# NLTKを使用しないモードで固定
NLTK_AVAILABLE = False

class RezumeParser:
    def __init__(self):
        """Rezume Parserの初期化"""
        # 技術用語のカテゴリを拡張
        self.tech_terms = {
            'programming': [
                'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Ruby', 
                'PHP', 'Swift', 'Kotlin', 'Go', 'Rust', 'Scala', 'Dart', 'R', 'Perl', 'Shell'
            ],
            'web': [
                'HTML', 'CSS', 'Sass', 'Less', 'React', 'Vue', 'Angular', 'Svelte',
                'Django', 'Flask', 'FastAPI', 'Node.js', 'Express', 'Next.js', 'Nuxt.js',
                'jQuery', 'Bootstrap', 'Tailwind CSS'
            ],
            'database': [
                'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Oracle', 'SQLite',
                'DynamoDB', 'Firebase', 'Elasticsearch', 'Neo4j', 'Cassandra'
            ],
            'devops': [
                'Docker', 'Kubernetes', 'AWS', 'Azure', 'GCP', 'CI/CD', 'Git',
                'GitHub Actions', 'GitLab CI', 'Jenkins', 'Ansible', 'Terraform',
                'Prometheus', 'Grafana', 'Kibana', 'Datadog', 'Splunk'
            ],
            'ml': [
                'Machine Learning', 'Deep Learning', 'AI', 'Neural Networks',
                'TensorFlow', 'PyTorch', 'scikit-learn', 'Keras', 'OpenCV',
                'NLP', 'Computer Vision', 'Reinforcement Learning', 'Pandas', 'NumPy'
            ],
            'mobile': ['Android', 'iOS', 'Flutter', 'React Native', 'Xamarin'],
            'cloud': ['AWS', 'Azure', 'GCP', 'Heroku', 'Vercel', 'Netlify', 'Firebase']
        }
        
        # エイリアスマップを作成（大文字小文字を区別しない）
        self.skill_aliases = {}
        for category, skills in self.tech_terms.items():
            for skill in skills:
                self.skill_aliases[skill.lower()] = {'name': skill, 'type': category.upper()}
        
    def parse_resume(self, text: str) -> Dict:
        """
        レジュメを解析してスキルを抽出
        
        Args:
            text: 解析するテキスト
            
        Returns:
            抽出されたスキルとその情報を含む辞書
        """
        # スキルを抽出
        skills = self._extract_skills(text)
        
        # 経験年数を抽出
        experience = self._extract_experience(text)
        
        return {
            'skills': skills,
            'experience_years': experience,
            'raw_text': text[:500] + '...'  # デバッグ用に最初の500文字を保存
        }
    
    def extract_skills(self, text: str) -> List[Dict]:
        """スキルを抽出（パブリックメソッド）
        
        Args:
            text: スキルを抽出するテキスト
            
        Returns:
            抽出されたスキルのリスト。各スキルは以下のキーを持つ辞書:
            - name: スキル名
            - type: スキルのタイプ（例: PROGRAMMING, WEB, DATABASE など）
            - start: テキスト内での開始位置
            - end: テキスト内での終了位置
        """
        return self._extract_skills(text)
        
    def _extract_skills(self, text: str) -> List[Dict[str, Any]]:
        """テキストからスキルを抽出するプライベートメソッド"""
        skills = []
        
        if not text or not isinstance(text, str):
            return skills
            
        # テキストを小文字に変換
        text_lower = text.lower()
        
        # NLTKを使用しないシンプルなトークン化
        # 1. 英数字とハイフン、プラス記号、日本語を保持して、その他をスペースに変換
        cleaned_text = re.sub(r'[^\w\s\-+\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]', ' ', text)
        # 2. 連続するスペースを1つに変換
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        # 3. トークンに分割
        tokens = [t for t in cleaned_text.split() if len(t) > 1]  # 1文字のトークンは除外
        
        # 1. 既知の技術用語を抽出（大文字小文字を区別せず）
        for skill_lower, skill_info in self.skill_aliases.items():
            # 単語境界を考慮した検索
            if re.search(r'\b' + re.escape(skill_lower) + r'\b', text_lower):
                # スキルが既に追加されていないか確認
                if not any(s['name'].lower() == skill_info['name'].lower() for s in skills):
                    skills.append({
                        'name': skill_info['name'],
                        'type': skill_info['type'],
                        'start': 0,
                        'end': 0,
                        'importance': 0.8,  # デフォルトの重要度
                        'confidence': 0.9,   # 既知のスキルは信頼度を高く
                        'context': 'known_skill',
                        'source': 'skill_aliases',
                        'category': skill_info.get('category', 'other')
                    })
        
        # 2. 大文字で始まる単語を抽出（固有名詞の代わり）
        for token in tokens:
            if token[0].isupper() and len(token) > 1:
                # スキルが既に追加されていないか確認
                if not any(s['name'].lower() == token.lower() for s in skills):
                    # テキスト内での位置を検索
                    for match in re.finditer(re.escape(token), text):
                        skills.append({
                            'name': token,
                            'type': 'OTHER',
                            'start': match.start(),
                            'end': match.end()
                        })
                        break
        
        # 3. 単語の組み合わせをチェック（2-3語のフレーズ）
        for i in range(len(tokens) - 1):
            # 2語のフレーズ
            phrase = ' '.join(tokens[i:i+2])
            if len(phrase) > 3 and not any(s['name'].lower() == phrase.lower() for s in skills):
                for match in re.finditer(re.escape(phrase), text, re.IGNORECASE):
                    skills.append({
                        'name': phrase,
                        'type': 'other',
                        'start': match.start(),
                        'end': match.end(),
                        'importance': 0.5,  # デフォルトの重要度
                        'confidence': 0.6,   # 抽出されたスキルはやや低めの信頼度
                        'context': 'extracted',
                        'source': 'text_analysis',
                        'category': 'other'
                    })
                    break
            
            # 3語のフレーズ（オプション）
            if i < len(tokens) - 2:
                phrase = ' '.join(tokens[i:i+3])
                if len(phrase) > 5 and not any(s['name'].lower() == phrase.lower() for s in skills):
                    for match in re.finditer(re.escape(phrase), text, re.IGNORECASE):
                        skills.append({
                            'name': phrase,
                            'type': 'PHRASE',
                            'start': match.start(),
                            'end': match.end()
                        })
                        break
        
        # 3. 重複を削除して返す
        unique_skills = []
        seen = set()
        
        for skill in sorted(skills, key=lambda x: x['start']):
            skill_key = (skill['name'].lower(), skill['start'], skill['end'])
            if skill_key not in seen:
                seen.add(skill_key)
                unique_skills.append(skill)
        
        return unique_skills
    
    def _extract_experience(self, text: str) -> float:
        """経験年数を抽出
        
        Args:
            text: 経験年数を抽出するテキスト
            
        Returns:
            抽出された経験年数（見つからない場合は0.0）
        """
        if not text or not isinstance(text, str):
            return 0.0
            
        # 経験年数のパターン（日本語と英語の両方に対応）
        experience_patterns = [
            # 日本語パターン
            r'(?:経験|実務経験|職務経験|開発経験)[^\d]{0,20}?(\d+)[^\d]{0,3}(?:年|years?|y)(?:間|以上|程度|程度|ほど|程)?',
            r'(\d+)[^\d]{0,3}(?:年|years?|y)(?:間|以上|程度|ほど|程)?[^\d]{0,20}?(?:経験|実務経験|職務経験)',
            r'(?:\b|^)(?:約|およそ|約|約)?\s*(\d+(?:\.\d+)?)\s*(?:年|years?|y)(?:間|以上|程度|ほど|程)?(?:の経験)?(?:\b|$)',
            
            # 英語パターン
            r'(?:experience|work(?:ing)?\s+experience)[^\d]{0,20}?(\d+(?:\.\d+)?)[^\d]{0,3}(?:years?|yrs?)(?:\s+of\s+experience)?',
            r'(\d+(?:\.\d+)?)[^\d]{0,3}(?:years?|yrs?)(?:\s+of\s+experience)?',
            r'(?:\b|^)(?:about|around|approximately|~|〜)?\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)(?:\s+of\s+experience)?(?:\b|$)'
        ]
        
        # 月単位の経験も考慮（12ヶ月 = 1年）
        month_patterns = [
            r'(\d+)\s*ヶ月',
            r'(\d+)\s*months?',
            r'(\d+)\s*mos?'
        ]
        
        # 年数ベースの経験を検索
        max_years = 0.0
        
        for pattern in experience_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    years = float(match.group(1))
                    max_years = max(max_years, years)
                except (ValueError, IndexError):
                    continue
        
        # 月単位の経験を検索（年数に変換）
        for pattern in month_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    months = float(match.group(1))
                    years = months / 12.0
                    max_years = max(max_years, years)
                except (ValueError, IndexError):
                    continue
        
        # 範囲指定（例：3-5年）を検出
        range_patterns = [
            r'(\d+(?:\.\d+)?)\s*[-~〜]\s*(\d+(?:\.\d+)?)\s*(?:年|years?|y)',
            r'(?:between\s+)?(\d+(?:\.\d+)?)\s*(?:and|to|〜|~)\s*(\d+(?:\.\d+)?)\s*(?:years?|y)'
        ]
        
        for pattern in range_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    start = float(match.group(1))
                    end = float(match.group(2))
                    avg_years = (start + end) / 2.0
                    max_years = max(max_years, avg_years)
                except (ValueError, IndexError):
                    continue
        
        # 小数点以下1桁で丸める
        return round(max_years, 1) if max_years > 0 else 0.0

# シングルトンインスタンス
rezume_parser = RezumeParser()
