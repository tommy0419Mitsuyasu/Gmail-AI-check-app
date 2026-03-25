import os
from dotenv import load_dotenv
from google import genai
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)

# 環境変数ロード
load_dotenv()

def list_models():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("[ERROR] GEMINI_API_KEY が .env から読み込めません。")
        return

    print(f"Using API Key: {api_key[:5]}...")
    
    try:
        client = genai.Client(api_key=api_key)
        
        print("\n--- Available Models ---")
        # モデル一覧を取得 (pagerオブジェクトが返る)
        models_pager = client.models.list()
        
        # モデル名を表示
        found_flash = False
        for model in models_pager:
            print(f"- {model.name}")
            if "gemini-1.5-flash" in model.name:
                found_flash = True
                
        print("\n------------------------")
        
        if found_flash:
            print("Gemini 1.5 Flash is found in the list.")
        else:
            print("WARNING: Gemini 1.5 Flash NOT found. You might need to use a different model name.")

    except Exception as e:
        print(f"[ERROR] Failed to list models: {e}")

if __name__ == "__main__":
    list_models()
