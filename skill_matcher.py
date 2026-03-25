import re
import logging
import os
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum, auto

# 外部ライブラリのインポート（オプション）
try:
    from sentence_transformers import SentenceTransformer
    HAS_AI_DEPS = True
except ImportError:
    HAS_AI_DEPS = False
try:
    from rapidfuzz import fuzz, process as rf_process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    
# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('skill_matcher.log')
    ]
)
logger = logging.getLogger(__name__)

class SkillContext(Enum):
    """スキルが現れるコンテキストの種類"""
    TITLE = auto()        # タイトルや見出し
    LIST_ITEM = auto()    # リスト形式
    SENTENCE = auto()     # 通常の文
    CODE_BLOCK = auto()   # コードブロック内
    OTHER = auto()        # その他

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SkillMatch:
    """スキルマッチ情報を保持するクラス"""
    skill: str
    matched_terms: List[str] = field(default_factory=list)
    confidence: float = 0.0
    category: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'skill': self.skill,
            'matched_terms': self.matched_terms,
            'confidence': self.confidence,
            'category': self.category,
            'context': self.context
        }

class SkillMatcher:
    """スキルを抽出・マッチングするクラス"""
    
    def __init__(self, use_ai: bool = False, confidence_threshold: float = 0.5):
        """
        SkillMatcherを初期化します。
        
        Args:
            use_ai: AIを使用するかどうか
            confidence_threshold: 信頼度の閾値（0.0〜1.0）
        """
        self.use_ai = use_ai and HAS_AI_DEPS
        self.confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        self.ai_model = None
        self.skill_categories = {}
        self.skill_aliases = {}
        self.enable_synonyms = os.getenv('ENABLE_SYNONYM_EXPANSION', 'false').lower() == 'true'
        self.enable_fuzzy = os.getenv('ENABLE_FUZZY_MATCH', 'false').lower() == 'true' and HAS_RAPIDFUZZ
        try:
            self.fuzzy_threshold = int(os.getenv('FUZZY_THRESHOLD', '86'))
        except Exception:
            self.fuzzy_threshold = 86
        # 重み（環境変数で調整可能）
        try:
            self.level_weight = float(os.getenv('MATCH_LEVEL_WEIGHT', '0.7'))
            self.exp_weight = float(os.getenv('MATCH_EXP_WEIGHT', '0.3'))
            total = self.level_weight + self.exp_weight
            if total <= 0:
                self.level_weight, self.exp_weight = 0.7, 0.3
            else:
                self.level_weight /= total
                self.exp_weight /= total
        except Exception:
            self.level_weight, self.exp_weight = 0.7, 0.3
        
        # コンテキストの重み
        self.context_weights = {
            SkillContext.TITLE: 1.5,
            SkillContext.LIST_ITEM: 1.3,
            SkillContext.SENTENCE: 1.0,
            SkillContext.CODE_BLOCK: 1.2,
            SkillContext.OTHER: 0.8
        }
        
        # カテゴリの重み
        self.category_weights = {
            'programming_languages': 1.2,
            'frameworks': 1.3,
            'cloud': 1.4,
            'databases': 1.1,
            'methodologies': 1.0
        }
        
        # 初期化処理
        self._initialize_skill_categories()
        
        # AIモデルの初期化（必要な場合）
        if self.use_ai:
            self._initialize_ai_model()
        
    def _initialize_ai_model(self):
        """AIモデルを初期化する"""
        try:
            logger.info("AIモデルを読み込んでいます...")
            # より軽量なモデルを使用
            self.ai_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("AIモデルの読み込みが完了しました")
        except Exception as e:
            logger.error(f"AIモデルの読み込みに失敗しました: {e}")
            self.use_ai = False
    
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

        if self.enable_synonyms:
            additional_aliases: Dict[str, List[str]] = {
                'python': ['パイソン'],
                'java': ['ジャバ'],
                'aws': ['アマゾンウェブサービス', 'awsクラウド', 'アマゾン ウェブ サービス'],
                'gcp': ['グーグルクラウド', 'グーグル クラウド', 'google クラウド'],
                'azure': ['アジュール', 'マイクロソフトアジュール'],
                'docker': ['ドッカー'],
                'kubernetes': ['クバネティス', 'クーバネティス', 'クベ'],
                'react': ['リアクト'],
                'vue': ['ヴュー', 'ビュージェーエス', 'ビュージェイエス'],
                'angular': ['アンギュラー'],
                'mysql': ['マイエスキューエル'],
                'postgresql': ['ポストグレス', 'ポスグレ', 'ポストグレ'],
                'mongodb': ['モンゴ', 'モンゴデービー'],
                'redis': ['レディス'],
                'oracle': ['オラクル'],
                'sqlite': ['エスキューライト'],
                'elasticsearch': ['エラスティックサーチ'],
                'terraform': ['テラフォーム'],
                'jenkins': ['ジェンキンス'],
                'gitlab ci': ['ギットラブ シーアイ', 'ギットラボ ci'],
                'github actions': ['ギットハブ アクションズ', 'ギットハブアクションズ'],
                'agile': ['アジャイル'],
                'scrum': ['スクラム'],
                'devops': ['デブオプス'],
            }
            for norm, aliases in additional_aliases.items():
                existing = self.skill_aliases.get(norm, [])
                merged = list(dict.fromkeys(existing + aliases))
                self.skill_aliases[norm] = merged
                for a in aliases:
                    self.skill_normalization_map[a] = norm

    def normalize_skill(self, skill: str) -> str:
        """スキル名を正規化する"""
        s = (skill or '').strip().lower()
        if not s:
            return ''
        mapped = self.skill_normalization_map.get(s)
        if mapped:
            return mapped
        if self.enable_fuzzy and HAS_RAPIDFUZZ and self.skill_normalization_map:
            try:
                choice, score, _ = rf_process.extractOne(
                    s, list(self.skill_normalization_map.keys()), scorer=fuzz.QRatio
                )
                if choice and score >= self.fuzzy_threshold:
                    return self.skill_normalization_map.get(choice, s)
            except Exception:
                pass
        return s

    def extract_skills_from_text(self, text: str, threshold: float = 0.5) -> Dict[str, SkillMatch]:
        """テキストからスキルを抽出する
        
        Args:
            text: スキルを抽出するテキスト
            threshold: スキルマッチングのしきい値（0.0〜1.0）
            
        Returns:
            抽出されたスキルとそのマッチ情報を含む辞書
        """
        text_lower = text.lower()
        found_skills = {}
        
        # 1. まずは正規表現で明示的なマッチングを試みる
        found_skills = self._extract_skills_with_regex(text_lower)
        
        # AIが有効な場合は、文脈を考慮したマッチングを追加
        if self.use_ai and self.ai_model:
            ai_matches = self._extract_skills_with_ai(text_lower, threshold)
            
            # AIが検出したスキルを追加または更新
            for skill, match in ai_matches.items():
                if skill in found_skills:
                    # 既存のマッチとAIのマッチを統合
                    existing = found_skills[skill]
                    existing.confidence = max(existing.confidence, match.confidence)
                    existing.matched_terms = list(set(existing.matched_terms + match.matched_terms))
                else:
                    found_skills[skill] = match
        
        return found_skills
    
    def _extract_skills_with_regex(self, text_lower: str) -> Dict[str, SkillMatch]:
        """正規表現を使用してスキルを抽出する"""
        found_skills = {}
        
        for category, skills in self.skill_categories.items():
            for skill, aliases in skills.items():
                patterns = [r'\b' + re.escape(alias) + r'\b' for alias in aliases + [skill]]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                    for match in matches:
                        matched_term = match.group(0).lower()
                        if skill not in found_skills or len(matched_term) > len(found_skills[skill].matched_terms[0]):
                            confidence = 1.0 if match.group(0).lower() == skill.lower() else 0.8
                            found_skills[skill] = SkillMatch(
                                skill=skill,
                                matched_terms=[matched_term],
                                confidence=confidence
                            )
                        elif skill in found_skills:
                            if matched_term not in found_skills[skill].matched_terms:
                                found_skills[skill].matched_terms.append(matched_term)
        
        return found_skills
    
    def _extract_skills_with_ai(self, text: str, threshold: float) -> Dict[str, SkillMatch]:
        """AIを使用して文脈からスキルを抽出する"""
        if not self.skill_list:
            self._prepare_skill_embeddings()
        
        # テキストを文に分割
        sentences = [s.strip() for s in re.split(r'[。.\n]', text) if s.strip()]
        
        # 各文の埋め込みを取得
        sentence_embeddings = self.ai_model.encode(sentences, convert_to_tensor=True)
        
        # スキルの埋め込みを取得
        skill_embeddings = self.ai_model.encode(self.skill_list, convert_to_tensor=True)
        
        # コサイン類似度を計算
        from sentence_transformers import util
        
        found_skills = {}
        
        for i, sentence in enumerate(sentences):
            # 文とスキルの類似度を計算
            cos_scores = util.pytorch_cos_sim(sentence_embeddings[i], skill_embeddings)[0]
            
            # 類似度が閾値以上のスキルを抽出
            for idx, score in enumerate(cos_scores):
                if score >= threshold:
                    skill = self.skill_list[idx]
                    if skill not in found_skills or score > found_skills[skill].confidence:
                        found_skills[skill] = SkillMatch(
                            skill=skill,
                            matched_terms=[sentence],
                            confidence=float(score)
                        )
        
        return found_skills
    
    def _prepare_skill_embeddings(self):
        """スキルの埋め込みを準備する"""
        self.skill_list = []
        
        # スキルとそのエイリアスを収集
        for category, skills in self.skill_categories.items():
            for skill, aliases in skills.items():
                self.skill_list.append(skill)
                self.skill_list.extend(aliases)
        
        # 重複を削除
        self.skill_list = list(dict.fromkeys(self.skill_list))

    def _normalize_skill_level(self, level: str) -> str:
        level = (level or '').strip().lower()
        if any(k in level for k in ['senior', '上級', 'expert']):
            return 'senior'
        if any(k in level for k in ['intermediate', '中級', 'mid']):
            return 'intermediate'
        if any(k in level for k in ['junior', '初級', 'beginner']):
            return 'junior'
        return level or ''

    def _calculate_years_since_used(self, last_used: str) -> float:
        try:
            from datetime import datetime
            s = (last_used or '').strip()
            if not s:
                return 0.0
            for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y-%m', '%Y/%m', '%Y'):
                try:
                    dt = datetime.strptime(s, fmt)
                    return max(0.0, (datetime.utcnow() - dt).days / 365.25)
                except Exception:
                    continue
            return 0.0
        except Exception:
            return 0.0

    def _find_additional_skills(self, engineer_skill_set: Dict[str, Any], requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        req_names = {self.normalize_skill(r.get('skill', '').lower()) for r in requirements if r.get('skill')}
        extras = []
        for name, data in engineer_skill_set.items():
            if name not in req_names:
                extras.append({
                    'skill': data.get('original_name', name),
                    'level': data.get('level', ''),
                    'experience_years': data.get('experience', 0)
                })
        return extras

    def calculate_skill_weight(self, skill: str, context: str) -> float:
        """スキルの重みを計算する"""
        # 基本重み
        weight = 1.0
        
        # コンテキストに応じた重み付け
        context_lower = context.lower()
        
        # 必須スキルとして言及されているか
        if re.search(rf'(必須|必要|要|must have|required).*{re.escape(skill)}', context_lower, re.IGNORECASE):
            weight *= 1.5
            
        # 優遇スキルとして言及されているか
        if re.search(rf'(優遇|歓迎|あればなお可|plus|preferred).*{re.escape(skill)}', context_lower, re.IGNORECASE):
            weight *= 1.2
            
        # 経験年数が指定されている場合
        exp_match = re.search(rf'{re.escape(skill)}.*?(\d+)[ 　]*(?:年|years?|y)', context_lower, re.IGNORECASE)
        if exp_match:
            years = int(exp_match.group(1))
            weight *= min(1.0 + (years * 0.1), 2.0)  # 1年ごとに0.1倍、最大2.0倍まで
            
        return weight

    def extract_requirements(self, text: str) -> Dict[str, List[Dict]]:
        """メール本文から必須スキルと尚可スキルを抽出する"""
        if not text:
            return {'required_skills': [], 'preferred_skills': []}
        
        # 必須スキルセクションを抽出
        required_section = self._extract_section(text, ['必須スキル', '必須要件', '必須事項', '必須技術'])
        required_skills = self._extract_skills_from_section(required_section) if required_section else []
        
        # 尚可スキルセクションを抽出
        preferred_section = self._extract_section(text, ['尚可スキル', '歓迎スキル', 'あれば尚可', '尚可要件'])
        preferred_skills = self._extract_skills_from_section(preferred_section) if preferred_section else []
        
        return {
            'required_skills': required_skills,
            'preferred_skills': preferred_skills
        }

    def _extract_section(self, text: str, section_names: List[str]) -> Optional[str]:
        """テキストから指定されたセクション名のいずれかにマッチするセクションを抽出する"""
        for name in section_names:
            pattern = re.compile(
                r'{}\s*[:：]?\s*\n(.*?)(?=\n\S+[:：]|$)'.format(re.escape(name)),
                re.DOTALL | re.IGNORECASE
            )
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_skills_from_section(self, section_text: str) -> List[Dict]:
        """スキルセクションからスキルと経験年数を抽出する"""
        skills = []
        if not section_text:
            return skills
        
        # 箇条書きやカンマ区切りのスキルを抽出
        lines = [line.strip() for line in section_text.split('\n') if line.strip()]
        
        for line in lines:
            # 行からスキル名と経験年数を抽出
            skill_match = re.search(r'([^（(]+)(?:（(\d+)[ヶ年]）|(\(\d+)[\s]*(?:years?|年|ヶ月))?', line)
            if skill_match:
                skill_name = skill_match.group(1).strip()
                exp_years = skill_match.group(2) or skill_match.group(3)
                
                # スキル名を正規化
                normalized_skill = self.normalize_skill(skill_name)
                if normalized_skill:
                    skills.append({
                        'skill': normalized_skill,
                        'experience': float(exp_years) if exp_years and exp_years.isdigit() else None
                    })
        
        return skills

    def match_skills_with_requirements(self, candidate_skills: List[Dict], job_requirements: Dict) -> Dict:
        """
        候補者のスキルと求人要件をマッチングする
        """
        # 候補者のスキルを正規化してセットに変換
        candidate_skill_set = {self.normalize_skill(skill['name'].lower()): skill 
                             for skill in candidate_skills if 'name' in skill}
        
        results = {
            'match_score': 0.0,
            'required_matches': [],
            'preferred_matches': [],
            'missing_required': [],
            'missing_preferred': []
        }
        
        # 必須スキルのマッチング
        required_matches = self._match_skill_list(
            job_requirements.get('required_skills', []),
            candidate_skill_set
        )
        results['required_matches'] = required_matches['matches']
        results['missing_required'] = required_matches['missing']
        
        # 尚可スキルのマッチング
        preferred_matches = self._match_skill_list(
            job_requirements.get('preferred_skills', []),
            candidate_skill_set
        )
        results['preferred_matches'] = preferred_matches['matches']
        results['missing_preferred'] = preferred_matches['missing']
        
        # マッチングスコアを計算（必須スキルを重視）
        total_required = len(job_requirements.get('required_skills', []))
        matched_required = len([m for m in results['required_matches'] if m['match']])
        required_score = matched_required / total_required if total_required > 0 else 1.0
        
        total_preferred = len(job_requirements.get('preferred_skills', []))
        matched_preferred = len([m for m in results['preferred_matches'] if m['match']])
        preferred_score = matched_preferred / total_preferred if total_preferred > 0 else 1.0
        
        # 必須スキルを70%、尚可スキルを30%で重み付け
        results['match_score'] = (required_score * 0.7) + (preferred_score * 0.3)
        
        return results

    def _match_skill_list(self, required_skills: List[Dict], candidate_skill_set: Dict) -> Dict:
        """必要なスキルリストと候補者のスキルをマッチングする"""
        matches = []
        missing = []
        
        for req_skill in required_skills:
            req_skill_name = req_skill.get('skill', '').lower()
            req_exp = req_skill.get('experience')
            
            # スキル名を正規化
            normalized_req_skill = self.normalize_skill(req_skill_name)
            if not normalized_req_skill:
                continue
                
            # 候補者のスキルとマッチング
            match_info = {
                'skill': normalized_req_skill,
                'required_exp': req_exp,
                'match': False,
                'candidate_exp': None,
                'experience_met': False
            }
            
            # 完全一致または部分一致でマッチング
            for cand_skill_name, cand_skill in candidate_skill_set.items():
                if (normalized_req_skill in cand_skill_name or 
                    cand_skill_name in normalized_req_skill):
                    match_info['match'] = True
                    match_info['candidate_exp'] = cand_skill.get('experience')
                    
                    # 経験年数の確認
                    if req_exp is not None and 'experience' in cand_skill:
                        match_info['experience_met'] = cand_skill['experience'] >= req_exp
                    
                    break
                    
            if match_info['match']:
                matches.append(match_info)
            else:
                missing.append({
                    'skill': normalized_req_skill,
                    'required_exp': req_exp
                })
        
        return {
            'matches': matches,
            'missing': missing
        }

    def match_engineer_to_project(
        self, 
        engineer_skills: List[Dict[str, Any]], 
        project_requirements: List[Dict[str, Any]], 
        project_context: str = ""
    ) -> Dict[str, Any]:
        """
        エンジニアのスキルとプロジェクト要件をマッチングする
        
        Args:
            engineer_skills: エンジニアのスキルリスト [
                {'name': str, 'level': str, 'experience_years': float, 'last_used': str(optional)}
            ]
            project_requirements: プロジェクトの要件リスト [
                {
                    'skill': str, 
                    'level': str, 
                    'weight': float,
                    'required': bool,
                    'min_experience': float(optional),
                    'preferred': List[str](optional)
                }
            ]
            project_context: プロジェクトのコンテキスト情報（例: 業界、ドメインなど）
            
        Returns:
            {
                'match_score': float,  # 0.0〜1.0のマッチスコア
                'coverage': float,    # カバー率（0.0〜1.0）
                'matches': [          # マッチしたスキルの詳細
                    {
                        'required_skill': str,
                        'matched_skill': str,
                        'match_type': str,  # 'exact', 'alias', 'related', 'partial'
                        'score': float,     # 0.0〜1.0
                        'level_match': str,  # 'exact', 'higher', 'lower', 'none'
                        'experience_years': float,
                        'required_experience': float,
                        'is_required': bool,
                        'weight': float
                    }
                ],
                'missing_skills': [    # 不足している必須スキル
                    {
                        'skill': str,
                        'level': str,
                        'weight': float
                    }
                ],
                'additional_skills': [  # 追加のマッチングスキル
                    {
                        'skill': str,
                        'level': str,
                        'score': float
                    }
                ]
            }
        """
        # エンジニアのスキルを正規化して辞書に格納
        engineer_skill_set = {}
        for skill in engineer_skills:
            if not skill or not skill.get('name'):
                continue
                
            skill_name = skill.get('name', '').strip()
            if not skill_name:
                continue
                
            normalized = self.normalize_skill(skill_name)
            if not normalized:
                continue
                
            # 最終使用時期を取得（あれば）
            last_used = skill.get('last_used', '')
            years_since_used = self._calculate_years_since_used(last_used) if last_used else 0
            
            engineer_skill_set[normalized] = {
                'original_name': skill_name,
                'level': self._normalize_skill_level(skill.get('level', '')),
                'experience': max(0, float(skill.get('experience_years', 0) or 0) - (years_since_used * 0.2)),
                'last_used': last_used,
                'years_since_used': years_since_used
            }
        
        # マッチング結果を格納する変数
        result = {
            'match_score': 0.0,
            'coverage': 0.0,
            'matches': [],
            'missing_skills': [],
            'additional_skills': []
        }
        
        # 必須スキルとオプションスキルを分離
        required_skills = [r for r in project_requirements if r.get('required', True)]
        optional_skills = [r for r in project_requirements if r.get('required', None) is False]
        
        # 必須スキルのマッチング
        required_matches, missing_required = self._match_skill_requirements(
            required_skills, engineer_skill_set, is_required=True
        )
        
        # オプションスキルのマッチング
        optional_matches, _ = self._match_skill_requirements(
            optional_skills, engineer_skill_set, is_required=False
        )
        
        # 追加スキル（要件にないがエンジニアが持っているスキル）
        additional_skills = self._find_additional_skills(
            engineer_skill_set, 
            required_skills + optional_skills
        )
        
        # スコア計算
        
        # カバー率（必須スキルのみで計算）
        required_weight = sum(r.get('weight', 1.0) for r in required_skills)
        matched_required_weight = sum(m.get('weight', 1.0) for m in required_matches)
        
        coverage = (matched_required_weight / required_weight) if required_weight > 0 else 1.0
        
        # マッチスコア（カバー率とスキルレベルのマッチ度を考慮）
        level_scores = [m.get('level_score', 0) * m.get('weight', 1.0) 
                       for m in required_matches + optional_matches]
        avg_level_score = sum(level_scores) / len(level_scores) if level_scores else 0
        
        match_score = (coverage * 0.7) + (avg_level_score * 0.3)
        
        combined_matches = required_matches + optional_matches
        seen_keys = set()
        deduped_matches = []
        for m in combined_matches:
            key = (m.get('required_skill', ''), m.get('matched_skill', ''))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped_matches.append(m)
        sorted_matches = sorted(
            deduped_matches,
            key=lambda x: (x.get('score', 0.0) * x.get('weight', 1.0)),
            reverse=True
        )

        # 結果を構築
        result.update({
            'match_score': min(1.0, max(0.0, match_score)),
            'coverage': min(1.0, max(0.0, coverage)),
            'matches': sorted_matches,
            'missing_skills': missing_required,
            'additional_skills': additional_skills
        })
        # 互換キー（既存のテスト/呼び出し向け）
        result['match_ratio'] = result['match_score']
        result['matched_skills'] = [m.get('required_skill', m.get('matched_skill', '')) for m in result['matches']]
        result['missed_skills'] = [m.get('skill') for m in missing_required]

        return result
        
    def _match_skill_requirements(
        self, 
        requirements: List[Dict[str, Any]], 
        engineer_skills: Dict[str, Any],
        is_required: bool = True
    ) -> Tuple[List[Dict], List[Dict]]:
        """スキル要件とエンジニアのスキルをマッチングする
        Returns:
            Tuple[List[Dict], List[Dict]]: (matches, missing)
        """
        matches: List[Dict[str, Any]] = []
        missing: List[Dict[str, Any]] = []

        for req in requirements:
            req_skill_raw = (req.get('skill') or '').strip()
            if not req_skill_raw:
                continue
            normalized_req = self.normalize_skill(req_skill_raw.lower())
            if not normalized_req:
                continue
            req_level = self._normalize_skill_level(req.get('level', ''))
            req_weight = float(req.get('weight', 1.0))
            req_min_exp = float(req.get('min_experience', 0) or 0)

            best_match = None
            best_score = 0.0

            for eng_skill, eng_data in engineer_skills.items():
                if eng_skill == normalized_req or eng_skill in self.skill_aliases.get(normalized_req, []):
                    level_score = 1.0
                    eng_level = eng_data.get('level', '')
                    if req_level:
                        if req_level == 'junior' and 'senior' in eng_level:
                            level_score = 1.2
                        elif req_level == 'senior' and 'junior' in eng_level:
                            level_score = 0.7

                    exp_years = float(eng_data.get('experience', 0) or 0)
                    exp_score = 1.0 if req_min_exp == 0 else min(exp_years / max(req_min_exp, 0.0001), 1.0)
                    score = (self.level_weight * level_score) + (self.exp_weight * exp_score)

                    if score > best_score:
                        best_score = score
                        # 一致種別（厳密/エイリアス）
                        alias_list = self.skill_aliases.get(normalized_req, [])
                        match_type = 'exact' if eng_skill == normalized_req else ('alias' if eng_skill in alias_list else 'partial')
                        # レベル関係
                        if not req_level or not eng_level:
                            level_relation = 'none'
                        elif req_level == 'junior' and 'senior' in eng_level:
                            level_relation = 'higher'
                        elif req_level == 'senior' and 'junior' in eng_level:
                            level_relation = 'lower'
                        elif req_level in eng_level:
                            level_relation = 'match'
                        else:
                            level_relation = 'none'
                        # 理由文生成
                        reason = (
                            f"required='{req_skill_raw}' level='{req_level or 'unspecified'}', "
                            f"matched='{eng_data.get('original_name', eng_skill)}' level='{eng_level or 'n/a'}' via {match_type}; "
                            f"exp={exp_years:g}y vs min={req_min_exp:g}y -> exp_score={exp_score:.2f}; "
                            f"level_relation={level_relation}, level_score={level_score:.2f}; weight={req_weight:g}"
                        )
                        best_match = {
                            'required_skill': req_skill_raw,
                            'matched_skill': eng_data.get('original_name', eng_skill),
                            'level': eng_level,
                            'experience': exp_years,
                            'score': score,
                            'level_score': level_score,
                            'weight': req_weight,
                            'is_required': is_required,
                            'required_experience': req_min_exp,
                            'match_type': match_type,
                            'level_relation': level_relation,
                            'reason': reason,
                            'components': {
                                'exp_score': exp_score,
                                'level_score': level_score,
                                'weight': req_weight
                            }
                        }

            if best_match:
                matches.append(best_match)
            else:
                missing.append({
                    'skill': normalized_req,
                    'level': req_level,
                    'weight': req_weight,
                    'is_required': is_required
                })

        return matches, missing
