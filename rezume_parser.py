import re
from typing import Dict, List, Any, Optional

# NLTKを使用しないモードで固定
NLTK_AVAILABLE = False

# ========== ノイズとして除外すべきワード ==========
# 個人情報・場所など（スキルではない）
PERSONAL_INFO_PATTERNS = [
    r'^\d{1,3}歳?$',         # 年齢
    r'^[男女]性$',           # 性別
    r'^\d{4}/\d{2}$',       # 日付
    r'^\d+ヵ月$',           # 期間
    r'^\d+年\d+ヶ月$',      # 期間
    r'^[ぁ-ん]{2,5}駅$',   # 駅名
    r'^[ぁ-ん]{2,10}線$',   # 路線名
    r'^\d+月$',             # 月
    r'^[A-Z]\.[A-Z]$',      # イニシャル
]

# セクション区切りパターン
SECTION_PATTERNS = {
    'tech_summary': [
        r'【経験分野】', r'【主要な業務経歴】', r'【スキル】',
    ],
    'project_detail': [
        r'【システム概要】', r'【業務内容】', r'【担当業務】',
        r'【開発手法】', r'【実績】', r'【開発環境】',
    ],
    'personal': [
        r'【アピールポイント】', r'長所', r'自己PR',
    ],
}

# 技術スタック行を示すパターン（これらの行は高精度でスキルを含む）
TECH_TABLE_LINE_HINTS = [
    r'(Windows|Linux|CentOS|macOS|iOS|Android)[/／]',   # OS
    r'(Oracle|MySQL|PostgreSQL|DB2|SQL Server)',         # DB名
    r'(Java|Python|PHP|C#|Ruby|Kotlin|Swift|Go)\s*(（|[\(/])?',  # 言語
    r'(Spring|Django|Rails|Laravel|Flutter|React|Vue)',  # FW
    r'(Eclipse|IntelliJ|Xcode|Visual Studio)',           # IDE
    r'(GitLab|GitHub|SVN|Subversion|Jenkins)',           # VCS/CI
    r'(JUnit|Pytest|Selenium|Appium|Cypress)',           # テストツール
]


class RezumeParser:
    def __init__(self):
        """Rezume Parserの初期化"""
        # 共通の大規模スキル辞書をインポート
        try:
            from skill_matcher_enhanced import SKILL_CATEGORIES, SKILL_SYNONYMS
        except ImportError:
            SKILL_CATEGORIES = {'programming': ['Python', 'Java', 'JavaScript']}
            SKILL_SYNONYMS = {}

        # エイリアスマップを作成（大文字小文字を区別しない）
        self.skill_aliases = {}

        # シノニム（別名）を先に登録
        for alias, canonical in SKILL_SYNONYMS.items():
            self.skill_aliases[alias.lower()] = {'name': canonical, 'type': 'OTHER'}

        # カテゴリごとに正規スキル名を登録
        for category, skills in SKILL_CATEGORIES.items():
            for skill in skills:
                self.skill_aliases[skill.lower()] = {'name': skill, 'type': category.upper()}

        # シノニム側のtypeを正規スキルに合わせて補正
        for alias_lower, info in self.skill_aliases.items():
            canonical_lower = info['name'].lower()
            if canonical_lower in self.skill_aliases and canonical_lower != alias_lower:
                info['type'] = self.skill_aliases[canonical_lower]['type']

    def parse_resume(self, text: str) -> Dict:
        """
        レジュメを解析してスキルを抽出

        Args:
            text: 解析するテキスト

        Returns:
            抽出されたスキルとその情報を含む辞書
        """
        skills = self._extract_skills(text)
        experience = self._extract_experience(text)

        return {
            'skills': skills,
            'experience_years': experience,
            'raw_text': text[:500] + '...'
        }

    def extract_skills(self, text: str) -> List[Dict]:
        """スキルを抽出（パブリックメソッド）"""
        return self._extract_skills(text)

    # ========== プリプロセス ==========

    def _preprocess_text(self, text: str) -> str:
        """スキルシートの縦書き・壊れた文字を前処理して読みやすくする"""
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        return text

    def _is_tech_table_line(self, line: str) -> bool:
        """この行が技術スタック表の行かどうか推定する"""
        for hint in TECH_TABLE_LINE_HINTS:
            if re.search(hint, line, re.IGNORECASE):
                return True
        # スラッシュ区切りで複数の技術名が並んでいる行
        slash_parts = re.split(r'[/／]', line)
        if len(slash_parts) >= 2:
            hit = sum(
                1 for p in slash_parts
                if p.strip().lower() in self.skill_aliases
            )
            if hit >= 2 or (len(slash_parts) >= 3 and hit / len(slash_parts) >= 0.4):
                return True
        return False

    def _segment_text(self, text: str) -> Dict[str, List[str]]:
        """
        スキルシートをセクションごとに分割。
        """
        lines = text.split('\n')
        segments = {'tech_table': [], 'project_desc': [], 'other': []}

        in_project_section = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            is_section_header = False
            for pat in SECTION_PATTERNS['project_detail']:
                if re.search(pat, stripped):
                    in_project_section = True
                    is_section_header = True
                    break
            for pat in SECTION_PATTERNS['personal']:
                if re.search(pat, stripped):
                    in_project_section = False
                    is_section_header = True
                    break

            if is_section_header:
                continue

            if self._is_tech_table_line(stripped):
                segments['tech_table'].append(stripped)
                continue

            if in_project_section:
                segments['project_desc'].append(stripped)
                continue

            segments['other'].append(stripped)

        return segments

    # ========== 工程抽出 (NEW) ==========
    
    def _extract_processes(self, text: str) -> List[Dict]:
        """ステートマシンとマトリクスによる厳密な工程抽出"""
        lines = text.split('\n')
        extracted_processes = set()
        
        # 1. 抽出ON/OFFのヘッダー正規表現
        start_pattern = re.compile(r'【担当業務】|≪担当業務≫|【担当】|【役割】|■担当業務|■役割')
        end_pattern = re.compile(r'【システム概要】|【開発環境】|【実績】|【チーム体制】|【開発手法】|■システム概要|■開発環境')
        
        # 汎用的な見出しを検知 (これで囲まれている場合は別セクションとみなす)
        header_pattern = re.compile(r'^【.+】|^≪.+≫|^■.+')
        
        # 2. 工程のキーワード辞書 (正規化用)
        process_keywords = {
            '要件定義': r'要件定義',
            '基本設計': r'基本設計',
            '詳細設計': r'詳細設計',
            '製造': r'製造|実装',
            '単体テスト': r'単体テスト|単体試験|UT',
            '結合テスト': r'結合テスト|結合試験|IT',
            '総合テスト': r'総合テスト|総合試験|ST',
            '運用': r'運用',
            '保守': r'保守'
        }
        
        # 3. マトリクス用ヘッダー辞書 (SES特有のフラグ表)
        matrix_headers = {
            '要件定義': r'要件?定義?|要',
            '基本設計': r'基本?設計?|基',
            '詳細設計': r'詳細?設計?|詳',
            '製造': r'製造|実装|製',
            '単体テスト': r'単体(?:テスト|試験)?|単',
            '結合テスト': r'結合(?:テスト|試験)?|結',
            '総合テスト': r'総合(?:テスト|試験)?|総',
            '運用': r'運用|運',
            '保守': r'保守|保'
        }
        
        in_task_section = False
        matrix_mapping = {} # 文字インデックス -> 工程名
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            # --- ステートマシンの状態更新 ---
            is_header = bool(header_pattern.search(stripped))
            if start_pattern.search(stripped):
                in_task_section = True
                matrix_mapping = {}
                continue
            elif end_pattern.search(stripped) or is_header:
                # 終了ヘッダー、もしくは他の汎用ヘッダーが来たらOFFにする
                in_task_section = False
                matrix_mapping = {}
                continue
                
            # --- マトリクス表の検知 ---
            # 工程の文字が複数(3つ以上)含まれる行をマトリクスヘッダーとみなす
            hit_count = 0
            temp_mapping = {}
            for proc_name, pat in matrix_headers.items():
                for m in re.finditer(pat, line):  # strippedではなく元のlineを使って正確な位置を保持
                    temp_mapping[m.start()] = proc_name
                    hit_count += 1
            
            if hit_count >= 3:
                matrix_mapping = temp_mapping
                continue # この行自体からは通常抽出しない
                
            # マトリクスデータ行の検知 (〇, ◎, ◯ があるか)
            if matrix_mapping and re.search(r'[〇◎◯]', line):
                for m in re.finditer(r'[〇◎◯]', line):
                    idx = m.start()
                    # 最も近い見出し（ヘッダー）を探す
                    closest_proc = None
                    min_dist = 999
                    for h_idx, proc_name in matrix_mapping.items():
                        dist = abs(h_idx - idx)
                        if dist < min_dist:
                            min_dist = dist
                            closest_proc = proc_name
                    
                    # 距離が一定以内（ズレを許容して5文字以内）なら抽出
                    if closest_proc and min_dist <= 5:
                        extracted_processes.add(closest_proc)
            
            # --- テキストベースの工程抽出 ---
            if in_task_section:
                for proc_name, pat in process_keywords.items():
                    if re.search(pat, stripped, re.IGNORECASE):
                        extracted_processes.add(proc_name)
                        
        # 抽出した工程をスキルフォーマットに変換
        process_skills = []
        for proc in extracted_processes:
            process_skills.append({
                'name': proc,
                'type': 'PROCESS',
                'start': 0,
                'end': 0,
                'importance': 1.5, # 工程はマッチングにおいて重要
                'confidence': 0.95,
                'context': 'task_section',
                'source': 'process_extractor',
                'category': 'process'
            })
            
        return process_skills

    # ========== スキル抽出 ==========

    def _extract_skills_from_text(
        self, text: str, weight: float = 1.0
    ) -> List[Dict]:
        """テキストからスキル辞書にある技術を抽出する（重み付き）"""
        skills = []
        text_lower = text.lower()

        for skill_lower, skill_info in self.skill_aliases.items():
            escaped = re.escape(skill_lower)
            pattern = r'(?:^|[\s/／・、。,\(\)【】]|(?<=[^a-zA-Z0-9_]))' + \
                      escaped + \
                      r'(?:$|[\s/／・、。,\(\)【】]|(?=[^a-zA-Z0-9_]))'
            if re.search(pattern, text_lower):
                skill_name = skill_info['name']
                if not any(
                    s['name'].lower() == skill_name.lower() for s in skills
                ):
                    skills.append({
                        'name': skill_name,
                        'type': skill_info['type'],
                        'start': 0,
                        'end': 0,
                        'importance': weight,
                        'confidence': 0.95 if weight >= 1.5 else 0.85,
                        'context': 'section_aware',
                        'source': 'skill_aliases',
                        'category': skill_info.get('type', 'other').lower()
                    })

        return skills

    def _extract_skills(self, text: str) -> List[Dict]:
        """テキストからスキルを抽出する（セクション対応版＋厳密な工程抽出）"""
        if not text or not isinstance(text, str):
            return []

        # 前処理
        processed_text = self._preprocess_text(text)
        
        # 1. 厳密な工程抽出（ステートマシン＆マトリクス）
        process_skills = self._extract_processes(processed_text)
        
        # 2. 技術スタックの抽出
        segments = self._segment_text(processed_text)
        all_skills: Dict[str, Dict] = {}  # name_lower -> skill_info

        def _merge(new_skills: List[Dict], weight_boost: float = 1.0):
            """スキルをマージし、重みが高い方を優先する"""
            for s in new_skills:
                key = s['name'].lower()
                s['importance'] = s.get('importance', 1.0) * weight_boost
                if key not in all_skills or all_skills[key]['importance'] < s['importance']:
                    all_skills[key] = s

        # ① 技術スタック行（最高優先度・重み2.0）
        tech_text = '\n'.join(segments['tech_table'])
        _merge(self._extract_skills_from_text(tech_text, weight=1.0), weight_boost=2.0)

        # ② プロジェクト説明セクション（高優先度・重み1.5）
        desc_text = '\n'.join(segments['project_desc'])
        _merge(self._extract_skills_from_text(desc_text, weight=1.0), weight_boost=1.5)

        # ③ その他テキスト（低優先度・重み0.8）
        other_text = '\n'.join(segments['other'])
        _merge(self._extract_skills_from_text(other_text, weight=1.0), weight_boost=0.8)

        # 3. 工程スキルと技術スタックを統合
        for p_skill in process_skills:
            all_skills[p_skill['name'].lower()] = p_skill

        # 重要度の高い順にソートして返す
        result = sorted(all_skills.values(), key=lambda x: x['importance'], reverse=True)
        return result

    def _extract_experience(self, text: str) -> float:
        """経験年数を抽出"""
        if not text or not isinstance(text, str):
            return 0.0

        experience_patterns = [
            r'(?:経験|実務経験|職務経験|開発経験)[^\d]{0,20}?(\d+)[^\d]{0,3}(?:年|years?|y)(?:間|以上|程度|ほど|程)?',
            r'(\d+)[^\d]{0,3}(?:年|years?|y)(?:間|以上|程度|ほど|程)?[^\d]{0,20}?(?:経験|実務経験|職務経験)',
            r'(?:\b|^)(?:約|およそ)?\s*(\d+(?:\.\d+)?)\s*(?:年|years?|y)(?:間|以上|程度|ほど|程)?(?:の経験)?(?:\b|$)',
            r'(?:experience|work(?:ing)?\s+experience)[^\d]{0,20}?(\d+(?:\.\d+)?)[^\d]{0,3}(?:years?|yrs?)(?:\s+of\s+experience)?',
            r'(\d+(?:\.\d+)?)[^\d]{0,3}(?:years?|yrs?)(?:\s+of\s+experience)?',
        ]

        month_patterns = [
            r'(\d+)\s*ヶ月',
            r'(\d+)\s*ヵ月',
            r'(\d+)\s*months?',
        ]

        max_years = 0.0

        for pattern in experience_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    years = float(match.group(1))
                    max_years = max(max_years, years)
                except (ValueError, IndexError):
                    continue

        for pattern in month_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    months = float(match.group(1))
                    years = months / 12.0
                    max_years = max(max_years, years)
                except (ValueError, IndexError):
                    continue

        range_patterns = [
            r'(\d+(?:\.\d+)?)\s*[-~〜]\s*(\d+(?:\.\d+)?)\s*(?:年|years?|y)',
        ]

        for pattern in range_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    start = float(match.group(1))
                    end = float(match.group(2))
                    max_years = max(max_years, (start + end) / 2.0)
                except (ValueError, IndexError):
                    continue

        return round(max_years, 1) if max_years > 0 else 0.0


# シングルトンインスタンス
rezume_parser = RezumeParser()
