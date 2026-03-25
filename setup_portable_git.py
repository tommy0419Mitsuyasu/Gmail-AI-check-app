import os
import urllib.request
import zipfile

# MinGit (Portable Git) のダウンロードURL
URL = "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/MinGit-2.44.0-64-bit.zip"
DEST_ZIP = "mingit.zip"
EXTRACT_TO = "minigit"

print(f"Downloading {URL}...")
try:
    urllib.request.urlretrieve(URL, DEST_ZIP)
    print("Download complete.")
except Exception as e:
    print(f"Download failed: {e}")
    exit(1)

print(f"Extracting to {EXTRACT_TO}...")
try:
    if not os.path.exists(EXTRACT_TO):
        os.makedirs(EXTRACT_TO)
    with zipfile.ZipFile(DEST_ZIP, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_TO)
    print("Extraction complete.")
except Exception as e:
    print(f"Extraction failed: {e}")
    exit(1)

git_path = os.path.abspath(os.path.join(EXTRACT_TO, "cmd", "git.exe"))
print(f"Git is now available at: {git_path}")

# テスト実行
import subprocess
try:
    result = subprocess.run([git_path, "--version"], capture_output=True, text=True)
    print(f"Verified: {result.stdout.strip()}")
except Exception as e:
    print(f"Verification failed: {e}")
