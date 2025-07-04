from skill_matcher import SkillMatcher

# AIを使用したスキルマッチャーを初期化
print("スキルマッチャーを初期化中...")
matcher = SkillMatcher(use_ai=True)

# テスト用のテキスト
test_text = """
私はPythonとJavaScriptでの開発経験が3年あります。
最近はDjangoとReactを使ったWebアプリケーションを開発しています。
また、AWSでのクラウド環境構築の経験もあります。
"""

print("\nテキストからスキルを抽出中...")
# スキルを抽出
skills = matcher.extract_skills_from_text(test_text)

# 結果を表示
print("\n抽出されたスキル:")
for skill, match in skills.items():
    print(f"- {skill}: 信頼度={match.confidence:.2f}, マッチ箇所={match.matched_terms[0][:50]}..." if len(match.matched_terms[0]) > 50 else f"- {skill}: 信頼度={match.confidence:.2f}, マッチ箇所={match.matched_terms[0]}")

# エンジニアとプロジェクトのマッチング例
print("\nエンジニアとプロジェクトのマッチングを実行中...")
engineer_skills = [
    {"name": "Python", "level": "中級", "experience_years": 3},
    {"name": "JavaScript", "level": "中級", "experience_years": 3},
    {"name": "Django", "level": "初級", "experience_years": 1},
    {"name": "React", "level": "初級", "experience_years": 1},
    {"name": "AWS", "level": "初級", "experience_years": 1}
]

project_requirements = [
    {"skill": "Python", "level": "中級", "weight": 1.0},
    {"skill": "Django", "level": "中級", "weight": 0.8},
    {"skill": "データベース", "level": "初級", "weight": 0.5}
]

result = matcher.match_engineer_to_project(engineer_skills, project_requirements)
print("\n=== プロジェクトマッチング結果 ===")
print(f"マッチ率: {result['match_ratio']*100:.1f}%")
print("\nマッチしたスキル:")
for skill in result['matched_skills']:
    print(f"- {skill}")
print("\n不足しているスキル:")
for skill in result['missed_skills']:
    print(f"- {skill}" if skill else "- 不明なスキル")

print("\nテストが完了しました。")
