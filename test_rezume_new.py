"""
改善されたrezume_parser.pyの動作確認スクリプト
実際のスキルシートサンプルでテスト
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rezume_parser import RezumeParser

# ユーザーから提供されたスキルシートサンプル
SAMPLE_SHEET = """
【経験分野】
【アピールポイント】
業種
システム名称
業務内容
総
合
試
験
2023/06
2025/02
21ヵ月
PG
PM
TL
SL
SE
PG 2年7ヶ月
No
業種
OS/DB
言語/FW
ツール
Windows／Oracle
JAVA （Spring/Spring boot）
Eclipse/GitLab/Subversion (SVN)/Junit/Slack/Power Shell
テスター
資格名
田園都市線
合計年数 2年7ヶ月
M.T
Spring
SVN
Power Shell
Git Lab
Eclipse
保険業、通信業
【システム概要】
・半年リリースの社内向けシステムの改修
【開発手法】
・ウォーターフォール
【業務内容】
≪詳細設計≫
・新しい仕様追加に対し既存設計書の改修を実施
≪製造工程≫
・新機能の実装を担当
≪単体/結合試験≫
・テスト設計書を作成し、単体試験を実施
・試験後の不具合に対して不具合改修を実施

Spring boot
SVN
Git Lab
Junit
Eclipse

【システム概要】
・大手通信会社向けGWシステム改修、新規機能実装案件
【担当業務】
≪製造≫
・JAVAを使用した機能実装を実施
≪単体/結合試験≫
・APIの業務者が作成した仕様書をもとに結合試験を実施

Windows
Oracle
JAVA
HTML/CSS

【システム概要】
既存システムの単体試験移行業務を行いました。
【担当業務】
≪単体試験≫
・junit4からjunit5への単体試験のコードの修正を行いました。

Windows
Linux
Java
Eclipse
Gitlab
"""

parser = RezumeParser()
result = parser.parse_resume(SAMPLE_SHEET)

print("=" * 60)
print("抽出されたスキル一覧")
print("=" * 60)

for skill in result['skills']:
    importance = skill.get('importance', 1.0)
    star = "⭐⭐" if importance >= 3.0 else ("⭐" if importance >= 1.5 else "  ")
    print(f"{star} {skill['name']:25s} | 重み: {importance:.1f} | カテゴリ: {skill['type']}")

print(f"\n合計: {len(result['skills'])} スキル")
print(f"経験年数: {result['experience_years']} 年")

# 期待されるスキルの確認
expected = ['java', 'spring', 'spring boot', 'junit', 'eclipse', 'gitlab', 'oracle', 'windows', 'linux', 'html', 'css']
print("\n" + "=" * 60)
print("期待スキルの抽出確認")
print("=" * 60)
extracted_lower = [s['name'].lower() for s in result['skills']]
for exp in expected:
    found = any(exp in e for e in extracted_lower)
    mark = "✅" if found else "❌"
    print(f"{mark} {exp}")

# ノイズが含まれていないか確認
noise_check = ['pg', 'se', 'tl', '田園都市線', '21ヵ月', 'os/db']
print("\n" + "=" * 60)
print("ノイズ排除の確認（抽出されていたらNG）")
print("=" * 60)
for noise in noise_check:
    found = any(noise.lower() in e for e in extracted_lower)
    mark = "❌ NG（ノイズが混入）" if found else "✅ OK（排除済み）"
    print(f"{mark}: {noise}")
