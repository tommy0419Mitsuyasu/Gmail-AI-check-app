"""スキルマッチング機能を強化するモジュール"""
import re
from typing import List, Dict
from difflib import SequenceMatcher
from collections import defaultdict
from vector_engine import vector_engine

# ドメインとスキルの関連性を定義
DOMAIN_SKILLS = {
    'java_backend': ['java', 'spring', 'spring boot', 'hibernate', 'jpa', 'junit', 'maven', 'gradle'],
    'python_backend': ['python', 'django', 'flask', 'fastapi', 'sqlalchemy'],
    'frontend': ['javascript', 'typescript', 'react', 'vue', 'angular', 'html', 'css', 'sass'],
    'devops': ['docker', 'kubernetes', 'jenkins', 'github actions', 'gitlab ci'],
    'cloud': ['aws', 'azure', 'gcp', 'terraform', 'cloudformation'],
    'data_science': ['python', 'pandas', 'numpy', 'tensorflow', 'pytorch', 'scikit-learn'],
    'mobile': ['swift', 'kotlin', 'flutter', 'react native', 'ios', 'android'],
    # テスト・QAドメイン（新設）
    'testing': [
        # --- 日本語テスト基本用語 ---
        'テスト', 'テスター', 'qa', 'qe', 'qc', '品質保証', '品質管理',
        'ソフトウェアテスト', 'システムテスト', '結合テスト',
        '単体テスト', '検証', 'テスト設計', 'テスト実行',
        'ut', 'it', 'st', 'uat', '半導体テスト',
        '回帰テスト', 'リグレッションテスト', 'スモークテスト',
        'バグ管理', '不具合管理', 'テスト仕様書',
        # --- テストツール ---
        'selenium', 'playwright', 'appium', 'cypress', 'testng', 'junit',
        'pytest', 'jest', 'mocha', 'rspec', 'capybara',
        'jmeter', 'loadrunner', 'postman', 'rest assured',
        'katalon', 'qtest', 'testlink', 'redmine', 'jira',
        # --- テスト技法 ---
        '黒箱テスト', '白箱テスト', 'グレーボックステスト',
        '負荷テスト', 'パフォーマンステスト', 'セキュリティテスト',
        'アクセシビリティテスト', 'ユーザビリティテスト',
        '自動テスト', '手動テスト', 'アジャイル', 'スクラム',
    ]
}

# ドメイン間の関連性を定義（0.0-1.0の値で関連性の強さを表現）
DOMAIN_RELATIONSHIPS = {
    ('java_backend', 'devops'): 0.4,
    ('java_backend', 'cloud'): 0.5,
    ('python_backend', 'data_science'): 0.7,
    ('python_backend', 'devops'): 0.5,
    ('frontend', 'mobile'): 0.6,
    # テストドメインの関連性追加
    ('testing', 'java_backend'): 0.4,
    ('testing', 'python_backend'): 0.4,
    ('testing', 'frontend'): 0.3,
    ('testing', 'devops'): 0.3,
    ('testing', 'mobile'): 0.3,
}

def levenshtein_ratio(s1: str, s2: str) -> float:
    """文字列の類似度を計算する（0.0 〜 1.0）
    
    Args:
        s1: 比較する文字列1
        s2: 比較する文字列2
        
    Returns:
        文字列の類似度（0.0 〜 1.0）
    """
    return SequenceMatcher(None, s1, s2).ratio()

# スキルカテゴリを定義（拡充版）
SKILL_CATEGORIES = {
    # 既存のカテゴリを保持
    'programming': ['python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'go', 'rust', 'swift', 'kotlin'],
    'frontend': ['html', 'css', 'react', 'vue', 'angular', 'sass', 'typescript', 'bootstrap', 'jquery'],
    'backend': ['django', 'flask', 'spring', 'ruby on rails', 'node.js', 'express', 'laravel', 'fastapi'],
    'database': ['mysql', 'postgresql', 'mongodb', 'oracle', 'sql server', 'dynamodb', 'redis', 'sqlite'],
    'cloud': ['aws', 'azure', 'gcp', 'heroku', 'firebase', 'docker', 'kubernetes', 'terraform'],
    'ml_ai': ['機械学習', '深層学習', 'tensorflow', 'pytorch', 'scikit-learn', 'データ分析', '自然言語処理', '画像認識'],
    'devops': ['ci/cd', 'github actions', 'jenkins', 'ansible', 'prometheus', 'grafana', 'elk'],
    'design': ['figma', 'adobe xd', 'sketch', 'ui/ux', 'プロトタイプ'],
    
    # 新しいカテゴリを追加
    'mobile': ['flutter', 'react native', 'swift', 'kotlin', 'android', 'ios', 'xamarin', 'ionic'],
    # テスト・QA日本語用語を大量追加（最重要）
    'testing': [
        # 基本テスト用語（日本語）
        'テスト', 'テスター', 'qa', 'qe', 'qc',
        '品質保証', '品質管理', '品質', '品質検証',
        'ソフトウェアテスト', 'システムテスト', '結合テスト',
        '単体テスト', '検証', 'テスト設計', 'テスト実行',
        'テスト仕様', 'テスト仕様書', 'テスト計画', 'テスト計画書',
        'テスト管理', 'テスト工程', 'テスト要件',
        'テストツール', 'テスト現場', 'テスト適用',
        # テストレベル略語
        'ut', 'it', 'st', 'uat', 'sit', '結合', '単体',
        # テスト手法
        '回帰テスト', 'リグレッションテスト', 'スモークテスト',
        '結合テスト', 'システム連携テスト',
        '黒箱テスト', '白箱テスト', 'グレーボックステスト',
        '負荷テスト', 'パフォーマンステスト',
        'セキュリティテスト', 'アクセシビリティテスト',
        'ユーザビリティテスト', 'ユーザビリティ',
        '自動テスト', '自動化', '手動テスト', '試験',
        'ウォーターフォール', 'アジャイル', 'スクラム',
        'エクスプローラトリテスト', 'アドホックテスト',
        # バグ・不具合管理
        'バグ', 'バグ管理', '不具合管理', '不具合報告',
        'デフェクト', 'インシデント', 'エラー',
        '課題管理', '工数管理',
        # テストツール・フレームワーク
        'selenium', 'playwright', 'appium', 'cypress', 'testng', 'junit',
        'pytest', 'jest', 'mocha', 'rspec', 'capybara',
        'jmeter', 'loadrunner', 'postman', 'rest assured', 'soapui',
        'katalon', 'qtest', 'testlink', 'redmine', 'jira',
        'testrail', 'xray', 'zephyr',
        # 連携ツール
        'エクセル', 'スプレッドシート', 'データ履歴', 'テスト履歴',
    ],
    'security': ['認証', '認可', 'oauth', 'jwt', 'saml', '暗号化', 'セキュリティ'],
    'data_engineering': ['apache spark', 'hadoop', 'kafka', 'airflow', 'dbt', 'snowflake', 'bigquery'],
    'product_management': ['agile', 'scrum', 'kanban', 'jira', 'confluence', 'product owner', 'product manager']
}

# スキルのシノニム辞書（異なる表記を正規化）
SKILL_SYNONYMS = {
    # プログラミング言語
    'js': 'javascript',
    'ts': 'typescript',
    'py': 'python',
    'rb': 'ruby',
    'go lang': 'go',
    'golang': 'go',
    'cplusplus': 'c++',
    'csharp': 'c#',
    'f#': 'fsharp',
    'aspnet': 'asp.net',
    'dotnet': '.net',
    
    # フレームワーク・ライブラリ
    'reactjs': 'react',
    'react.js': 'react',
    'vuejs': 'vue',
    'vue.js': 'vue',
    'angularjs': 'angular',
    'angular.js': 'angular',
    'nextjs': 'next.js',
    'nuxtjs': 'nuxt.js',
    'expressjs': 'express',
    'node': 'node.js',
    'nodejs': 'node.js',
    'djangorestframework': 'django rest framework',
    'djangodrf': 'django rest framework',
    'drf': 'django rest framework',
    'springboot': 'spring boot',
    'springframework': 'spring',
    'rails': 'ruby on rails',
    'ror': 'ruby on rails',
    
    # データベース
    'postgres': 'postgresql',
    'mongo': 'mongodb',
    'ms sql': 'sql server',
    'mssql': 'sql server',
    'google bigquery': 'bigquery',
    'elastic search': 'elasticsearch',
    'es': 'elasticsearch',
    'dynamo': 'dynamodb',
    'redis cache': 'redis',
    
    # クラウド・インフラ
    'amazon web services': 'aws',
    'amazon s3': 's3',
    'aws s3': 's3',
    'google cloud': 'gcp',
    'google cloud platform': 'gcp',
    'k8s': 'kubernetes',
    'gke': 'kubernetes',
    'eks': 'kubernetes',
    'aks': 'kubernetes',
    
    # テスト・QA表記ゆれ吸収（新設）
    'テスタ': 'テスト',
    'テスター': 'テスト',
    'テスト実行': 'テスト',
    'テスト工程': 'テスト',
    'テスト工程師': 'テスト',
    'ソフトウェアテスト': 'テスト',
    'ソフトウェア検証': 'テスト',
    'システム検証': 'テスト',
    '検証エンジニア': 'テスト',
    '検証担当': 'テスト',
    '品質保証担当': '品質保証',
    '品質管理担当': '品質管理',
    'quality assurance': 'qa',
    'quality control': 'qc',
    'quality engineer': 'qe',
    'テスト設計': 'テスト設計',
    'テストケース': 'テスト設計',
    'テストケース作成': 'テスト設計',
    'テスト仕様': 'テスト設計',
    'テスト仕様書': 'テスト設計',
    '単体テスト': 'ut',
    '単体': 'ut',
    '結合テスト': 'it',
    '結合': 'it',
    '結合テスト（it）': 'it',
    'システムテスト': 'st',
    'システム': 'st',
    '受入テスト': 'uat',
    '受入': 'uat',
    '回帰テスト': '回帰テスト',
    'リグレッション': '回帰テスト',
    'リグレッションテスト': '回帰テスト',
    '自動テスト': '自動テスト',
    '自動テスト実装': '自動テスト',
    '自動化テスト': '自動テスト',
    '自動検証': '自動テスト',
    '負荷テスト': '負荷テスト',
    '負荷検証': '負荷テスト',
    '性能テスト': '負荷テスト',
    'バグ報告': 'バグ管理',
    'バグ追跡': 'バグ管理',
    'バグ履歴': 'バグ管理',
    '不具合': '不具合管理',
    '不具合報告': '不具合管理',
    '不具合内容': '不具合管理',
    # ツール略語
    'selenium webdriver': 'selenium',
    'selenium ide': 'selenium',
    'playwright test': 'playwright',
    'cypress io': 'cypress',
    'appium test': 'appium',
    # その他
    'ci/cd pipeline': 'ci/cd',
    'github action': 'github actions',
    'gitlab ci/cd': 'gitlab ci',
    'jupyter notebook': 'jupyter',
    'vscode': 'visual studio code',
    'vs code': 'visual studio code'
}

def calculate_skill_similarity(skill1: str, skill2: str, threshold: float = 0.8) -> float:
    """2つのスキルの類似度を計算する（0.0 〜 1.0）
    
    Args:
        skill1: 比較するスキル1
        skill2: 比較するスキル2
        threshold: 類似度の閾値（これ以上の類似度があれば類似とみなす）
        
    Returns:
        類似度（0.0 〜 1.0）
    """
    # 正規化
    norm1 = normalize_skill(skill1)
    norm2 = normalize_skill(skill2)
    
    # 完全一致の場合は1.0を返す
    if norm1 == norm2:
        return 1.0
    
    # 文字列の類似度を計算
    similarity = levenshtein_ratio(norm1, norm2)
    
    # 閾値以下の類似度は0.0とみなす
    return similarity if similarity >= threshold else 0.0

# 互換性のためのエイリアス
skill_similarity = calculate_skill_similarity

def normalize_skill(skill: str) -> str:
    """スキル名を正規化する"""
    if not skill:
        return ""
        
    # 小文字化して前後の空白を削除
    skill = skill.lower().strip()
    
    # シノニム辞書で置換
    skill = SKILL_SYNONYMS.get(skill, skill)
    
    # 不要な文字を削除
    skill = re.sub(r'[()\[\]{}<>/+]', ' ', skill)
    
    # スペースやハイフンの正規化
    skill = re.sub(r'[\s-]+', ' ', skill).strip()
    
    # バージョン番号の正規化 (例: python3 -> python)
    skill = re.sub(r'\s*\d+(\.\d+)*$', '', skill).strip()
    
    return skill
    # 小文字化して前後の空白を削除
    skill = skill.lower().strip()
    # 不要な文字を削除
    skill = re.sub(r'[()\[\]{}<>/+]', ' ', skill)
    # スペースやハイフンの正規化
    skill = re.sub(r'[\s-]+', ' ', skill).strip()
    # バージョン番号の正規化 (例: python3 -> python)
    skill = re.sub(r'\s*\d+(\.\d+)*$', '', skill)
    return skill

def get_related_skills(skill: str) -> List[str]:
    """関連するスキルを取得"""
    related = set()
    skill_lower = normalize_skill(skill)
    
    # 完全一致または部分一致で関連スキルを探す
    for category, skills in SKILL_CATEGORIES.items():
        # カテゴリ内のスキルと完全一致または部分一致するかチェック
        for s in skills:
            if skill_lower == s or skill_lower in s or s in skill_lower:
                # マッチしたスキルを除いたカテゴリ内の他のスキルを関連スキルとして追加
                related.update(rel_skill for rel_skill in skills 
                             if rel_skill != s and rel_skill != skill_lower)
    
    return list(related)

def calculate_skill_weight(skill: str, context: str) -> float:
    """スキルの重みを計算"""
    if not skill or not context:
        return 0.0
        
    weight = 1.0
    skill_lower = skill.lower()
    context_lower = context.lower()
    
    # コンテキスト内での出現回数
    count = context_lower.count(skill_lower)
    weight += min(count * 0.2, 1.0)  # 最大1.0まで
    
    # 重要なキーワードの近くにある場合
    important_terms = ['必須', '必要', '要', '経験', '実務', '歓迎', '尚可', '優遇', '必須スキル']
    for term in important_terms:
        if term in context_lower:
            # キーワードとの距離に基づいて重みを調整
            term_pos = context_lower.find(term)
            skill_pos = context_lower.find(skill_lower)
            if term_pos != -1 and skill_pos != -1:
                distance = abs(term_pos - skill_pos)
                if distance < 100:  # 100文字以内にある場合
                    weight += 0.5 * (1 - distance/100)  # 近いほど重みが大きい
    
    return min(weight, 3.0)  # 最大3.0まで

def calculate_level_score(candidate_level: str, required_level: str, is_related: bool = False) -> float:
    """スキルのレベルに基づくスコアを計算する
    
    Args:
        candidate_level: 候補者のスキルレベル
        required_level: 要求されるスキルレベル
        is_related: 関連スキルの場合はTrue
        
    Returns:
        レベルに基づくスコア（0.0 〜 1.0）
    """
    if not required_level or not candidate_level:
        return 0.7 if is_related else 1.0  # レベル指定がない場合はデフォルト値を返す
    
    levels = ['初級', '中級', '上級', 'リード']
    
    try:
        req_idx = levels.index(required_level)
        cand_idx = levels.index(candidate_level)
    except ValueError:
        return 0.5 if is_related else 0.8  # 無効なレベルの場合は中間値を返す
    
    if is_related:
        # 関連スキルの場合のスコア計算（ベーススコアが低い）
        if cand_idx >= req_idx:
            return 0.9  # 要求レベル以上
        else:
            return 0.5 + (cand_idx / (req_idx + 1)) * 0.4  # 0.5-0.9の範囲で調整
    else:
        # 完全一致または類似スキルの場合のスコア計算
        if cand_idx >= req_idx:
            return 1.0  # 要求レベル以上
        else:
            return 0.5 + (cand_idx / (req_idx + 1)) * 0.5  # 0.5-1.0の範囲で調整

def identify_primary_domains(skills: List[Dict]) -> Dict[str, float]:
    """スキルリストから専門分野を特定"""
    domain_scores = defaultdict(float)
    
    for skill in skills:
        skill_name = skill.get('name', '').lower()
        skill_level = skill.get('level', '中級')
        
        # スキルレベルを数値に変換
        level_scores = {'初級': 0.5, '中級': 1.0, '上級': 1.5, 'リード': 2.0}
        level_score = level_scores.get(skill_level, 1.0)
        
        # スキルが属するドメインを特定
        for domain, domain_skills in DOMAIN_SKILLS.items():
            for domain_skill in domain_skills:
                if calculate_skill_similarity(skill_name, domain_skill) > 0.8:
                    domain_scores[domain] += level_score
                    break
    
    # スコアを正規化
    total = sum(domain_scores.values())
    if total > 0:
        return {k: v/total for k, v in domain_scores.items()}
    return {}

def calculate_domain_match(candidate_domains: Dict[str, float], 
                         project_domains: Dict[str, float]) -> float:
    """候補者と案件のドメイン一致度を計算"""
    if not candidate_domains or not project_domains:
        return 0.0
    
    total_score = 0.0
    
    for c_domain, c_score in candidate_domains.items():
        for p_domain, p_score in project_domains.items():
            if c_domain == p_domain:
                # 完全一致
                total_score += c_score * p_score
            else:
                # ドメイン間の関連性を考慮
                relationship = DOMAIN_RELATIONSHIPS.get(
                    tuple(sorted([c_domain, p_domain])), 0.0)
                total_score += c_score * p_score * relationship * 0.7
    
    return min(total_score, 1.0)

def calculate_domain_expertise(skills: List[Dict]) -> Dict[str, float]:
    """スキルリストからドメイン専門性を計算
    
    Args:
        skills: スキルリスト [{'name': 'Java', 'level': '上級', ...}, ...]
        
    Returns:
        ドメイン別の専門性スコア (0.0-1.0)
    """
    domain_scores = defaultdict(float)
    
    for skill in skills:
        skill_name = skill.get('name', '').lower()
        skill_level = skill.get('level', '中級').lower()
        
        # スキルレベルを数値に変換
        level_score = {
            '初心者': 0.3, '初級': 0.5, '中級': 0.7, 
            '上級': 0.9, 'エキスパート': 1.0, 'expert': 1.0
        }.get(skill_level, 0.5)
        
        # ドメインにスコアを加算
        for domain, domain_skills in DOMAIN_SKILLS.items():
            if any(skill_similarity(skill_name, s) > 0.8 for s in domain_skills):
                domain_scores[domain] += level_score
    
    # 正規化
    total = sum(domain_scores.values())
    if total > 0:
        return {k: v/total for k, v in domain_scores.items()}
    return {}

def enhance_skill_matching(project_requirements: List[Dict], candidate_skills: List[Dict]) -> Dict:
    """スキルマッチングを強化する
    
    Args:
        project_requirements: プロジェクト要件のリスト
        candidate_skills: 候補者のスキルリスト（{'name': スキル名, 'level': レベル, ...}の形式）
        
    Returns:
        マッチング結果を含む辞書
    """
    if not project_requirements or not candidate_skills:
        return {
            'matches': [],
            'missed_skills': [req['skill'] for req in project_requirements] if project_requirements else [],
            'match_ratio': 0.0,
            'total_score': 0.0,
            'max_possible_score': 0.0,
            'domain_expertise': {}
        }
    
    # 候補者とプロジェクトの専門性を計算
    candidate_domains = calculate_domain_expertise(candidate_skills)
    project_domains = calculate_domain_expertise(project_requirements)
    
    # ドメインの一致度を計算
    domain_match_score = 0.0
    if candidate_domains and project_domains:
        # 共通のドメインがあればスコアを計算
        common_domains = set(candidate_domains.keys()) & set(project_domains.keys())
        if common_domains:
            # 共通ドメインのスコアの平均
            domain_match_score = sum(
                min(candidate_domains[d], project_domains[d]) 
                for d in common_domains
            ) / len(common_domains) if common_domains else 0.0
    
    # 候補スキルを正規化して辞書に格納
    normalized_candidate_skills = {}
    original_skill_names = {}
    
    for skill_data in candidate_skills:
        name = skill_data.get('name', '')
        if not name:
            continue
            
        normalized = normalize_skill(name)
        if not normalized:
            continue
            
        # 同じスキルが複数回出現した場合は、レベルの高い方を採用
        if normalized not in normalized_candidate_skills or \
           (skill_data.get('level') and skill_data['level'] > normalized_candidate_skills[normalized].get('level', '')):
            normalized_candidate_skills[normalized] = skill_data
            original_skill_names[normalized] = name
    
    # マッチング結果を格納するリスト
    matches = []
    matched_skills = set()
    total_score = 0.0
    max_possible_score = 0.0

    # 候補スキルのベクトルをキャッシュ（一括エンコード）
    candidate_vectors = {}
    if normalized_candidate_skills:
        skills_to_encode = list(normalized_candidate_skills.keys())
        try:
            vectors = vector_engine.encode(skills_to_encode)
            # ベクトルが1つの場合でもリストとして扱えるように修正
            if len(skills_to_encode) == 1 and vectors.ndim == 1:
                vectors = vectors.reshape(1, -1)
                
            for i, skill in enumerate(skills_to_encode):
                if i < len(vectors):
                    candidate_vectors[skill] = vectors[i]
        except Exception as e:
            print(f"Vector encoding error: {e}")
            # エラー時は空の辞書のまま進む（通常の文字マッチングのみになる）
    
    # 各プロジェクト要件に対してマッチングを実行
    for req in project_requirements:
        req_skill = req.get('skill', '')
        if not req_skill:  # スキル名が空の場合はスキップ
            continue
            
        req_skill_normalized = normalize_skill(req_skill)
        if not req_skill_normalized:  # 正規化後に空になる場合はスキップ
            continue
            
        req_weight = req.get('weight', 1.0)
        max_possible_score += req_weight
        
        # 1. 完全一致をチェック
        if req_skill_normalized in normalized_candidate_skills:
            candidate_data = normalized_candidate_skills[req_skill_normalized]
            
            # スキルのドメインを取得
            skill_domains = [
                domain for domain, skills in DOMAIN_SKILLS.items()
                if any(skill_similarity(req_skill_normalized, s) > 0.8 for s in skills)
            ]
            
            # ドメイン一致スコアを計算
            domain_score = 0.0
            if skill_domains and domain_match_score > 0:
                domain_score = max(
                    candidate_domains.get(domain, 0) * project_domains.get(domain, 0)
                    for domain in skill_domains
                    if domain in candidate_domains and domain in project_domains
                )
            
            # レベルの一致度を考慮したスコア計算
            level_score = calculate_level_score(
                candidate_data.get('level', ''), 
                req.get('level', ''), 
                is_related=False
            )
            
            # スコアを計算（スキル: 70%, レベル: 20%, ドメイン: 10% の重み）
            skill_score = (1.0 * 0.7) + (level_score * 0.2) + (domain_score * 0.1)
            weighted_score = skill_score * req_weight
            
            matches.append({
                'required_skill': req_skill,
                'matched_skill': original_skill_names.get(req_skill_normalized, req_skill_normalized),
                'level': candidate_data.get('level', ''),
                'required_level': req.get('level', ''),
                'score': weighted_score,
                'weight': req_weight,
                'match_type': 'exact',
                'domain_score': domain_score,
                'level_score': level_score
            })
            matched_skills.add(req_skill_normalized)
            total_score += weighted_score
            continue
            
        # 2. 類似度が高いスキルをチェック
        best_similarity = 0.5  # 類似度の閾値（緩和）
        best_match = None
        best_original_name = None
        best_domain_score = 0.0
        
        # 検索対象スキルのベクトルを計算
        req_vector = vector_engine.encode(req_skill_normalized)
        
        # スキルのドメインを取得
        req_skill_domains = [
            domain for domain, skills in DOMAIN_SKILLS.items()
            if any(skill_similarity(req_skill_normalized, s) > 0.8 for s in skills)
        ]
        
        for cand_skill, cand_data in normalized_candidate_skills.items():
            # 文字列ベースの類似度
            text_similarity = calculate_skill_similarity(req_skill_normalized, cand_skill)
            
            # ベクトルベースの類似度
            cand_vector = candidate_vectors.get(cand_skill)
            vector_similarity = vector_engine.calculate_similarity(req_vector, cand_vector)
            
            # 統合類似度
            similarity = max(text_similarity, vector_similarity)
            
            # ベクトルのみが高く、かつ信頼度が中程度の場合のみ少し割り引く
            if vector_similarity > text_similarity and vector_similarity < 0.6:
                 similarity = vector_similarity * 0.9
            
            # 類似度が閾値未満の場合はスキップ
            if similarity < best_similarity:
                continue
                
            # ドメイン一致スコアを計算
            domain_score = 0.0
            if req_skill_domains and domain_match_score > 0:
                cand_domains = [
                    domain for domain, domain_skills in DOMAIN_SKILLS.items()
                    if any(skill_similarity(cand_skill, s) > 0.8 for s in domain_skills)
                ]
                common_domains = set(req_skill_domains) & set(cand_domains)
                if common_domains:
                    domain_score = max(
                        min(candidate_domains.get(d, 0), project_domains.get(d, 0))
                        for d in common_domains
                        if d in candidate_domains and d in project_domains
                    ) if common_domains else 0.0
            
            level_score = calculate_level_score(
                cand_data.get('level', ''), 
                req.get('level', ''), 
                is_related=True
            )
            
            total_score_candidate = (similarity * 0.6) + (domain_score * 0.2) + (level_score * 0.2)
            
            if total_score_candidate > best_similarity:
                best_similarity = total_score_candidate
                best_match = cand_data
                best_original_name = original_skill_names.get(cand_skill, cand_skill)
                best_domain_score = domain_score
        
        if best_match:
            weight = req.get('weight', 1.0) * best_similarity
            weighted_score = best_similarity * weight
            
            matches.append({
                'required_skill': req_skill,
                'matched_skill': f"{best_original_name} (類似度: {best_similarity:.1%})",
                'level': best_match.get('level', ''),
                'required_level': req.get('level', ''),
                'score': weighted_score,
                'weight': weight,
                'match_type': 'similar',
                'similarity': best_similarity,
                'domain_score': best_domain_score,
            })
            matched_skills.add(req_skill_normalized)
            total_score += weighted_score
            continue
            
        # 3. 関連スキルをチェック（専門性を考慮）
        related_skills = get_related_skills(req_skill_normalized)
        best_related_score = 0.0
        best_related_match = None
        
        for related_skill in related_skills:
            if related_skill in normalized_candidate_skills:
                candidate_data = normalized_candidate_skills[related_skill]
                
                related_domains = [
                    domain for domain, domain_skills in DOMAIN_SKILLS.items()
                    if any(skill_similarity(related_skill, s) > 0.8 for s in domain_skills)
                ]
                
                domain_score = 0.0
                if related_domains and domain_match_score > 0:
                    valid = [
                        min(candidate_domains.get(d, 0), project_domains.get(d, 0))
                        for d in related_domains
                        if d in candidate_domains and d in project_domains
                    ]
                    domain_score = max(valid) if valid else 0.0
                
                level_score = calculate_level_score(
                    candidate_data.get('level', ''), 
                    req.get('level', ''), 
                    is_related=True
                )
                
                related_score = (0.5 * 0.5) + (domain_score * 0.3) + (level_score * 0.2)
                
                if related_score > best_related_score:
                    best_related_score = related_score
                    best_related_match = {
                        'data': candidate_data,
                        'skill_name': related_skill,
                        'domain_score': domain_score,
                        'level_score': level_score
                    }
        
        if best_related_match and best_related_score >= 0.3:
            weight = req.get('weight', 1.0) * best_related_score * 0.7
            weighted_score = best_related_score * weight
            
            matches.append({
                'required_skill': req_skill,
                'matched_skill': f"{original_skill_names.get(best_related_match['skill_name'], best_related_match['skill_name'])} (関連スキル)",
                'level': best_related_match['data'].get('level', ''),
                'required_level': req.get('level', ''),
                'score': weighted_score,
                'weight': weight,
                'match_type': 'related',
                'domain_score': best_related_match['domain_score'],
                'level_score': best_related_match['level_score']
            })
            matched_skills.add(req_skill_normalized)
            total_score += weighted_score

    # マッチング結果をスコアの高い順にソート
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    # マッチしなかった要件を特定
    missed_skills = []
    missing_must_count = 0
    
    for req in project_requirements:
        req_name = req.get('skill', req.get('name', ''))
        if not req_name:
            continue
            
        req_type = str(req.get('type', '')).lower()
        is_must = req_type in ['must', 'required'] or str(req.get('is_required', '')).lower() == 'true'
        
        if normalize_skill(req_name) not in matched_skills:
            missed_skills.append(req_name)
            if is_must:
                missing_must_count += 1
    
    # ① カテゴリベースのフォールバックマッチング
    def _get_skill_category(skill_name: str) -> str:
        """スキルが属するカテゴリ名を返す"""
        s = normalize_skill(skill_name)
        for cat, cat_skills in SKILL_CATEGORIES.items():
            for cs in cat_skills:
                if s == cs or s in cs or cs in s:
                    return cat
        return ''
    
    category_bonus_used = set()
    for req in project_requirements:
        req_skill = req.get('skill', '')
        if not req_skill:
            continue
        req_norm = normalize_skill(req_skill)
        if req_norm in matched_skills or req_norm in category_bonus_used:
            continue
        req_cat = _get_skill_category(req_skill)
        if not req_cat:
            continue
        for cand_skill in normalized_candidate_skills:
            cand_cat = _get_skill_category(cand_skill)
            if cand_cat == req_cat:
                partial_score = req.get('weight', 1.0) * 0.5
                total_score += partial_score
                matched_skills.add(req_norm)
                category_bonus_used.add(req_norm)
                matches.append({
                    'required_skill': req_skill,
                    'matched_skill': f"{original_skill_names.get(cand_skill, cand_skill)} (カテゴリ: {req_cat})",
                    'score': partial_score,
                    'weight': req.get('weight', 1.0),
                    'match_type': 'category',
                })
                break
    
    # ② 最終マッチ率の計算（スキルマッチのみで算出：旧来のドメイン依存を廃止）
    skill_match_ratio = (total_score / max_possible_score) if max_possible_score > 0 else 0
    final_score = skill_match_ratio
    
    # ③ 同一カテゴリの案件に多くマッチした場合は少しボーナス
    if candidate_domains and project_domains:
        common_domains = set(candidate_domains) & set(project_domains)
        if common_domains:
            domain_bonus = min(len(common_domains) * 0.05, 0.15)
            final_score = min(final_score + domain_bonus, 1.0)
    
    # ④ 【ペナルティ1】必須(must)スキルが欠けている場合の軽微な減点（緩和済み）
    if missing_must_count > 0:
        final_score *= (0.6 ** missing_must_count)
    
    # ⑤ 【ペナルティ2】候補者と案件のメインドメインが不一致の場合の軽微な減点
    top_candidate_domain = max(candidate_domains.items(), key=lambda x: x[1])[0] if candidate_domains else None
    top_project_domain = max(project_domains.items(), key=lambda x: x[1])[0] if project_domains else None
    
    if top_candidate_domain and top_project_domain and top_candidate_domain != top_project_domain:
        relationship = DOMAIN_RELATIONSHIPS.get(tuple(sorted([top_candidate_domain, top_project_domain])), 0.0)
        penalty_factor = 0.85 + (0.15 * relationship)
        if skill_match_ratio > 0.5:
            penalty_factor = 1.0 - (1.0 - penalty_factor) * (1.0 - skill_match_ratio)
        final_score *= penalty_factor

    match_ratio = min(final_score * 100, 100.0)
    
    top_domains = sorted(candidate_domains.items(), key=lambda x: x[1], reverse=True)[:3]
    top_project_domains = sorted(project_domains.items(), key=lambda x: x[1], reverse=True)[:3] if project_domains else []
    
    return {
        'matches': matches,
        'missed_skills': missed_skills,
        'matched_skills': list(matched_skills),
        'match_ratio': round(match_ratio, 1),
        'total_score': round(total_score, 2),
        'max_possible_score': round(max_possible_score, 2),
        'domain_scores': {
            'candidate': dict(top_domains),
            'project': dict(top_project_domains) if project_domains else {},
            'match_score': round(domain_match_score, 2)
        },
        'skill_match_score': round(skill_match_ratio * 100, 1),
        'domain_match_score': round(domain_match_score * 100, 1),
        'final_score': round(match_ratio, 1)
    }
