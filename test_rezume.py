import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rezume_parser import rezume_parser

text = """
職務経歴書
私はJavaとAWSの経験が3年あります。
以前はフロントエンドエンジニアとしてReactとTypeScriptを触っていました。
またGitやDockerも日常的に活用しています。
Project Managementの経験もありますがメインではありません。
Augustなどという謎の単語もとりあえず書いてみます。TheやThisなどは無視されるべきです。
"""

skills = rezume_parser.extract_skills(text)
for s in skills:
    print(f"抽出スキル: {s['name']} (Category: {s['type']})")
