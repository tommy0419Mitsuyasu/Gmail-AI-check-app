"""
Gitのコミット＆プッシュをPythonから実行するスクリプト
"""
import subprocess
import sys

REPO = r"c:\Users\m.toyoda\.windsurf\Gmail-AI-check-app-main"
REMOTE = "https://github.com/tommy0419Mitsuyasu/Gmail-AI-check-app.git"
BRANCH = "main"
MSG = "feat: skill extraction and matching logic overhaul"

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True)
    out = result.stdout.decode('cp932', errors='replace').strip()
    err = result.stderr.decode('cp932', errors='replace').strip()
    if out:
        print("OUT:", out)
    if err:
        print("ERR:", err)
    return result.returncode

print("=== git add ===")
rc = run(f'git -C "{REPO}" add .')
print("RC:", rc)

print("\n=== git status ===")
run(f'git -C "{REPO}" status --short')

print("\n=== git commit ===")
rc = run(f'git -C "{REPO}" commit -m "{MSG}"')
print("RC:", rc)

# まずremote URLを確認
print("\n=== remote URL確認 ===")
run(f'git -C "{REPO}" remote -v')

# リモートURLをHTTPSに設定（すでにそうなら no-op）
run(f'git -C "{REPO}" remote set-url origin {REMOTE}')

print("\n=== git push ===")
rc = run(f'git -C "{REPO}" push origin {BRANCH}')
print("RC:", rc)

if rc == 0:
    print("\n✅ プッシュ成功！")
else:
    print("\n❌ プッシュ失敗。認証が必要な場合はGitHub PAT（Personal Access Token）が必要です。")
