import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_manager import db_manager
from skill_matcher_enhanced import enhance_skill_matching

# Javaスキルの候補者をモック
candidate_skills = [{'name': 'Java', 'level': '上級'}]

projects = db_manager.search_projects(limit=50)

scored_projects = []
for proj in projects:
    proj_dict = dict(proj)
    formatted_reqs = []
    for r in proj_dict.get('skills', []):
        if isinstance(r, dict):
            formatted_reqs.append({
                'skill': r.get('name', ''),
                'type': r.get('type', 'want'),
                'weight': 1.0
            })
    
    match_result = enhance_skill_matching(formatted_reqs, candidate_skills)
    score = match_result.get('match_ratio', 0.0)
    
    if score >= 0:
        proj_dict['match_percentage'] = score
        scored_projects.append(proj_dict)

scored_projects.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)

for i, p in enumerate(scored_projects[:5]):
    print(f"[{i+1}] スコア: {p['match_percentage']} - タイトル: {p['title']}")
    print(f"    要求スキル: {[s.get('name') for s in p.get('skills', [])]}")
