import re
from typing import Dict, List, Any, Optional

# NLTKを使用しないモードで固定
NLTK_AVAILABLE = False

# ========== ノイズとして除外すべきワード ==========
# 役割種別（スキルではない）
ROLE_WORDS = {
    'pg', 'pm', 'tl', 'sl', 'se', 'pmo', 'pm/pmo', 'tl/sl',
    'プログラマー', 'プログラマ', 'テックリード', 'プロジェクトマネージャー',
    'サブリーダー', 'チームリーダー', 'スクラムマスター',
}

# 列ヘッダー（スキルシートの表ヘッダー）
COLUMN_HEADER_WORDS = {
    'os/db', 'os', 'db', 'fw', 'ツール', '言語', 'フレームワーク',
    '開発環境', '各種サービス', '言語 fw/ツール', 'os/db/サーバー',
    '業種', 'システム名称', '業務内容', '期間', '年　月数',
    '役割', 'メンバー数', '作業工程', '経験年数', '合計年数',
}

# 業務工程名（抽出しなくてよい）
PROCESS_WORDS = {
    '基本設計', '詳細設計', '製造', '単体試験', '結合試験', '総合試験',
    '運用', '保守', 'マネジメント', '調査', '分析', '要件定義',
}

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
        # 連続した1文字の漢字単語を結合（縦書きによる分割対策）
        # 例: "単\n体\n試\n験" -> 除去対象ではないが、行単位で処理するため影響小
        # 行ごとに処理しやすくするため改行を正規化
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        return text

    def _is_noise_token(self, token: str) -> bool:
        """トークンがノイズかどうかを判定"""
        t = token.strip().lower()
        if not t or len(t) <= 1:
            return True
        # 役割ワード
        if t in ROLE_WORDS:
            return True
        # 列ヘッダー
        if t in COLUMN_HEADER_WORDS:
            return True
        # 個人情報パターン
        for pat in PERSONAL_INFO_PATTERNS:
            if re.match(pat, token.strip()):
                return True
        return False

    def _is_tech_table_line(self, line: str) -> bool:
        """この行が技術スタック表の行かどうか推定する"""
        for hint in TECH_TABLE_LINE_HINTS:
            if re.search(hint, line, re.IGNORECASE):
                return True
        # スラッシュ区切りで複数の技術名が並んでいる行
        slash_parts = re.split(r'[/／]', line)
        if len(slash_parts) >= 2:
            # 全体の50%以上が辞書に載っている場合は技術行と判断
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
        Returns:
            {
              'tech_table': [技術スタックが書かれた行のリスト],
              'project_desc': [業務内容・システム概要の文章行],
              'other': [それ以外の行]
            }
        """
        lines = text.split('\n')
        segments = {'tech_table': [], 'project_desc': [], 'other': []}

        in_project_section = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # プロジェクト説明セクション開始判定
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

            # 技術スタック行の判定
            if self._is_tech_table_line(stripped):
                segments['tech_table'].append(stripped)
                continue

            # プロジェクト説明セクション内の行
            if in_project_section:
                segments['project_desc'].append(stripped)
                continue

            # その他
            segments['other'].append(stripped)

        return segments

    # ========== スキル抽出 ==========

    def _extract_skills_from_text(
        self, text: str, weight: float = 1.0
    ) -> List[Dict]:
        """テキストからスキル辞書にある技術を抽出する（重み付き）"""
        skills = []
        text_lower = text.lower()

        for skill_lower, skill_info in self.skill_aliases.items():
            escaped = re.escape(skill_lower)
            # 単語境界チェック（日本語・英語混在に対応）
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
        """テキストからスキルを抽出するプライベートメソッド（セクション対応版）"""
        if not text or not isinstance(text, str):
            return []

        text = self._preprocess_text(text)
        segments = self._segment_text(text)

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

        # 重要度の高い順にソート
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
