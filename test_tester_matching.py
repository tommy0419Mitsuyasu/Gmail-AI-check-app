"""
テスター・QAスキルのマッチング動作確認スクリプト
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skill_matcher_enhanced import enhance_skill_matching

# テスターのスキルシートを想定したスキル（候補者側）
tester_skills = [
    {'name': 'テスト', 'level': '上級'},
    {'name': 'テスター', 'level': '上級'},
    {'name': '品質保証', 'level': '上級'},
    {'name': '単体テスト', 'level': '中級'},
    {'name': '結合テスト', 'level': '中級'},
    {'name': 'Selenium', 'level': '中級'},
    {'name': 'バグ管理', 'level': '上級'},
]

# テスト案件の要求スキル（案件側）
test_project_reqs = [
    {'skill': 'テスト', 'type': 'must', 'weight': 2.0},
    {'skill': 'テスター', 'type': 'must', 'weight': 2.0},
    {'skill': '品質保証', 'type': 'want', 'weight': 1.0},
    {'skill': 'Selenium', 'type': 'want', 'weight': 1.0},
]

# AWS案件（テスターには合わないはずの案件）
aws_project_reqs = [
    {'skill': 'AWS', 'type': 'must', 'weight': 2.0},
    {'skill': 'インフラ', 'type': 'must', 'weight': 2.0},
    {'skill': 'Terraform', 'type': 'want', 'weight': 1.0},
]

print("=== テスト案件とのマッチング結果 ===")
result_test = enhance_skill_matching(test_project_reqs, tester_skills)
print(f"マッチ率: {result_test.get('match_ratio', 0):.1f}%")
print(f"マッチしたスキル: {result_test.get('matched_skills', [])}")

print("\n=== AWS案件とのマッチング結果（低くあるべき） ===")
result_aws = enhance_skill_matching(aws_project_reqs, tester_skills)
print(f"マッチ率: {result_aws.get('match_ratio', 0):.1f}%")

print("\n=== 判定 ===")
test_score = result_test.get('match_ratio', 0)
aws_score = result_aws.get('match_ratio', 0)
if test_score > aws_score:
    print(f"✅ OK: テスト案件 ({test_score:.1f}%) > AWS案件 ({aws_score:.1f}%)")
else:
    print(f"❌ NG: テスト案件 ({test_score:.1f}%) <= AWS案件 ({aws_score:.1f}%)")
