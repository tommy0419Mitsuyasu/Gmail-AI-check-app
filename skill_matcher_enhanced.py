"""スキルマッチング機能を強化するモジュール"""
import re
from typing import List, Dict, Any, Set, Tuple, Optional
from difflib import SequenceMatcher
from collections import defaultdict

# ドメインとスキルの関連性を定義
DOMAIN_SKILLS = {
    'java_backend': ['java', 'spring', 'spring boot', 'hibernate', 'jpa', 'junit', 'maven', 'gradle'],
    'python_backend': ['python', 'django', 'flask', 'fastapi', 'sqlalchemy'],
    'frontend': ['javascript', 'typescript', 'react', 'vue', 'angular', 'html', 'css', 'sass'],
    'devops': ['docker', 'kubernetes', 'jenkins', 'github actions', 'gitlab ci'],
    'cloud': ['aws', 'azure', 'gcp', 'terraform', 'cloudformation'],
    'data_science': ['python', 'pandas', 'numpy', 'tensorflow', 'pytorch', 'scikit-learn'],
    'mobile': ['swift', 'kotlin', 'flutter', 'react native', 'ios', 'android']
}

# ドメイン間の関連性を定義（0.0-1.0の値で関連性の強さを表現）
DOMAIN_RELATIONSHIPS = {
    ('java_backend', 'devops'): 0.4,
    ('java_backend', 'cloud'): 0.5,
    ('python_backend', 'data_science'): 0.7,
    ('python_backend', 'devops'): 0.5,
    ('frontend', 'mobile'): 0.6
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
    'testing': ['jest', 'mocha', 'cypress', 'selenium', 'pytest', 'junit', 'testng', 'rspec'],
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
        best_similarity = 0.7  # 類似度の閾値
        best_match = None
        best_original_name = None
        best_domain_score = 0.0
        
        # スキルのドメインを取得
        req_skill_domains = [
            domain for domain, skills in DOMAIN_SKILLS.items()
            if any(skill_similarity(req_skill_normalized, s) > 0.8 for s in skills)
        ]
        
        for cand_skill, cand_data in normalized_candidate_skills.items():
            # スキルの類似度を計算
            similarity = calculate_skill_similarity(req_skill_normalized, cand_skill)
            
            # 類似度が閾値未満の場合はスキップ
            if similarity < best_similarity:
                continue
                
            # ドメイン一致スコアを計算
            domain_score = 0.0
            if req_skill_domains and domain_match_score > 0:
                # 候補スキルのドメインを取得
                cand_domains = [
                    domain for domain, skills in DOMAIN_SKILLS.items()
                    if any(skill_similarity(cand_skill, s) > 0.8 for s in skills)
                ]
                
                # 共通のドメインがあればスコアを計算
                common_domains = set(req_skill_domains) & set(cand_domains)
                if common_domains:
                    domain_score = max(
                        min(candidate_domains.get(d, 0), project_domains.get(d, 0))
                        for d in common_domains
                        if d in candidate_domains and d in project_domains
                    )
            
            # スコアを計算（類似度: 60%, ドメイン: 20%, レベル: 20% の重み）
            level_score = calculate_level_score(
                cand_data.get('level', ''), 
                req.get('level', ''), 
                is_related=True
            )
            
            # 総合スコア
            total_score_candidate = (similarity * 0.6) + (domain_score * 0.2) + (level_score * 0.2)
            
            # 最高スコアを更新
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
                'level_score': calculate_level_score(
                    best_match.get('level', ''), 
                    req.get('level', ''), 
                    is_related=True
                )
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
                
                # 関連スキルのドメインを取得
                related_domains = [
                    domain for domain, skills in DOMAIN_SKILLS.items()
                    if any(skill_similarity(related_skill, s) > 0.8 for s in skills)
                ]
                
                # ドメイン一致スコアを計算
                domain_score = 0.0
                if related_domains and domain_match_score > 0:
                    domain_score = max(
                        min(candidate_domains.get(d, 0), project_domains.get(d, 0))
                        for d in related_domains
                        if d in candidate_domains and d in project_domains
                    )
                
                # レベルの一致度を考慮
                level_score = calculate_level_score(
                    candidate_data.get('level', ''), 
                    req.get('level', ''), 
                    is_related=True
                )
                
                # 関連スキルのスコア（類似度は固定で0.5、ドメイン: 30%, レベル: 20% の重み）
                related_score = (0.5 * 0.5) + (domain_score * 0.3) + (level_score * 0.2)
                
                # 最高スコアの関連スキルを記録
                if related_score > best_related_score:
                    best_related_score = related_score
                    best_related_match = {
                        'data': candidate_data,
                        'skill_name': related_skill,
                        'domain_score': domain_score,
                        'level_score': level_score
                    }
        
        # 関連スキルが見つかった場合（閾値: 0.3）
        if best_related_match and best_related_score >= 0.3:
            weight = req.get('weight', 1.0) * best_related_score * 0.7  # 関連スキルは重みを下げる
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
    missed_skills = [
        req['skill'] for req in project_requirements
        if req.get('skill') and normalize_skill(req['skill']) not in matched_skills
    ]
    
    # 最終的なマッチ率を計算（スキルマッチ: 70%, ドメインマッチ: 30% の重み）
    skill_match_ratio = (total_score / max_possible_score) if max_possible_score > 0 else 0
    final_score = (skill_match_ratio * 0.7) + (domain_match_score * 0.3)
    match_ratio = final_score * 100
    
    # 候補者の専門性トップ3を取得
    top_domains = sorted(
        candidate_domains.items(),
        key=lambda x: x[1],
        reverse=True
    )[:3]
    
    # プロジェクトの要求専門性トップ3を取得
    top_project_domains = sorted(
        project_domains.items(),
        key=lambda x: x[1],
        reverse=True
    )[:3] if project_domains else []
    
    return {
        'matches': matches,
        'missed_skills': missed_skills,
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
