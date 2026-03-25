"""
skill_matcher_enhanced.py の832行以降の残骸コードを削除するスクリプト
"""
with open(r'c:\Users\m.toyoda\.windsurf\Gmail-AI-check-app-main\skill_matcher_enhanced.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 832行目（0-indexed: 831）まで保持する
clean_lines = lines[:832]

# 末尾が改行で終わるようにする
if clean_lines and not clean_lines[-1].endswith('\n'):
    clean_lines[-1] += '\n'

with open(r'c:\Users\m.toyoda\.windsurf\Gmail-AI-check-app-main\skill_matcher_enhanced.py', 'w', encoding='utf-8') as f:
    f.writelines(clean_lines)

print(f"ファイルを {len(clean_lines)} 行に切り詰めました")
