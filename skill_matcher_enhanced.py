"""スキルマッチング機能を強化するモジュール"""
import re
from typing import List, Dict, Any, Set, Tuple

# スキルカテゴリを定義（必要に応じて追加・修正してください）
SKILL_CATEGORIES = {
    'programming': ['python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'go', 'rust', 'swift', 'kotlin'],
    'frontend': ['html', 'css', 'react', 'vue', 'angular', 'sass', 'typescript', 'bootstrap', 'jquery'],
    'backend': ['django', 'flask', 'spring', 'ruby on rails', 'node.js', 'express', 'laravel', 'fastapi'],
    'database': ['mysql', 'postgresql', 'mongodb', 'oracle', 'sql server', 'dynamodb', 'redis', 'sqlite'],
    'cloud': ['aws', 'azure', 'gcp', 'heroku', 'firebase', 'docker', 'kubernetes', 'terraform'],
    'ml_ai': ['機械学習', '深層学習', 'tensorflow', 'pytorch', 'scikit-learn', 'データ分析', '自然言語処理', '画像認識'],
    'devops': ['ci/cd', 'github actions', 'jenkins', 'ansible', 'prometheus', 'grafana', 'elk'],
    'design': ['figma', 'adobe xd', 'sketch', 'ui/ux', 'プロトタイプ'],
}

def normalize_skill(skill: str) -> str:
    """スキル名を正規化する"""
    if not skill:
        return ""
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
            'max_possible_score': 0.0
        }
    
    # 候補スキルを正規化
    normalized_candidate_skills = {}
    for skill_data in candidate_skills:
        name = skill_data.get('name', '')
        if name:  # スキル名が空でない場合のみ処理
            normalized = normalize_skill(name)
            if normalized:  # 正規化後のスキル名が空でない場合のみ追加
                # 同じスキルが複数回出現した場合は、レベルの高い方を採用
                if normalized not in normalized_candidate_skills or \
                   (skill_data.get('level') and skill_data['level'] > normalized_candidate_skills[normalized].get('level', '')):
                    normalized_candidate_skills[normalized] = skill_data
    
    # マッチング結果を格納するリスト
    matches = []
    matched_skills = set()
    
    # 各プロジェクト要件に対してマッチングを実行
    for req in project_requirements:
        req_skill = req.get('skill', '')
        if not req_skill:  # スキル名が空の場合はスキップ
            continue
            
        req_skill_normalized = normalize_skill(req_skill)
        if not req_skill_normalized:  # 正規化後に空になる場合はスキップ
            continue
        
        # 完全一致をチェック
        if req_skill_normalized in normalized_candidate_skills:
            candidate_data = normalized_candidate_skills[req_skill_normalized]
            weight = req.get('weight', 1.0)
            level = candidate_data.get('level', '')
            
            # レベルの一致度を考慮したスコア計算
            level_score = 1.0
            req_level = req.get('level', '')
            if req_level and level:
                levels = ['初級', '中級', '上級', 'リード']
                req_level_idx = levels.index(req_level) if req_level in levels else -1
                cand_level_idx = levels.index(level) if level in levels else -1
                if req_level_idx >= 0 and cand_level_idx >= 0:
                    if cand_level_idx >= req_level_idx:
                        level_score = 1.0  # 要求レベル以上
                    else:
                        level_score = 0.5 + (cand_level_idx / (req_level_idx + 1)) * 0.5  # 0.5-1.0の範囲で調整
            
            score = 1.0 * weight * level_score
            
            matches.append({
                'required_skill': req_skill,
                'matched_skill': candidate_data['name'],
                'level': level,
                'score': score,
                'match_type': 'exact',
                'context': req.get('context', '')
            })
            matched_skills.add(req_skill_normalized)
            continue
            
        # 関連スキルをチェック
        related_skills = get_related_skills(req_skill)
        for related_skill in related_skills:
            if related_skill in normalized_candidate_skills:
                candidate_data = normalized_candidate_skills[related_skill]
                weight = req.get('weight', 1.0) * 0.7  # 関連スキルの場合はスコアを下げる
                level = candidate_data.get('level', '')
                
                # レベルの一致度を考慮したスコア計算
                level_score = 1.0
                req_level = req.get('level', '')
                if req_level and level:
                    levels = ['初級', '中級', '上級', 'リード']
                    req_level_idx = levels.index(req_level) if req_level in levels else -1
                    cand_level_idx = levels.index(level) if level in levels else -1
                    if req_level_idx >= 0 and cand_level_idx >= 0:
                        if cand_level_idx >= req_level_idx:
                            level_score = 0.9  # 要求レベル以上（完全一致よりは低く）
                        else:
                            level_score = 0.4 + (cand_level_idx / (req_level_idx + 1)) * 0.5  # 0.4-0.9の範囲で調整
                
                score = weight * level_score
                
                # 同じ要件に対して複数の関連スキルがマッチするのを防ぐため、スコアが最も高いもののみを採用
                existing_match = next((m for m in matches if m['required_skill'] == req_skill), None)
                if existing_match:
                    if score > existing_match['score']:
                        matches.remove(existing_match)
                        matched_skills.discard(normalize_skill(existing_match['matched_skill']))
                    else:
                        continue
                
                matches.append({
                    'required_skill': req_skill,
                    'matched_skill': candidate_data['name'],
                    'level': level,
                    'score': score,
                    'match_type': 'related',
                    'context': req.get('context', '')
                })
                matched_skills.add(related_skill)
                break
    
    # マッチング結果をスコアの高い順にソート
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    # マッチしなかった要件を特定
    missed_skills = [
        req['skill'] for req in project_requirements
        if req.get('skill') and normalize_skill(req['skill']) not in matched_skills
    ]
    
    # マッチ率を計算
    total_score = sum(match['score'] for match in matches)
    max_possible_score = sum(req.get('weight', 1.0) for req in project_requirements if req.get('skill'))
    match_ratio = (total_score / max_possible_score) * 100 if max_possible_score > 0 else 0
    
    return {
        'matches': matches,
        'missed_skills': missed_skills,
        'match_ratio': round(match_ratio, 1),
        'total_score': round(total_score, 2),
        'max_possible_score': round(max_possible_score, 2)
    }
