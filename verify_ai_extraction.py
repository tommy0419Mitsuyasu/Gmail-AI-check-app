import os
from dotenv import load_dotenv
import logging
from skill_extractor import SkillExtractor

# ログ設定
logging.basicConfig(level=logging.INFO)

# 環境変数ロード
load_dotenv()

def test_extraction():
    # APIキーが読み込めているか確認
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("[ERROR] GEMINI_API_KEY が .env から読み込めません。")
        return

    print(f"API Key loaded: {api_key[:5]}...")
    
    extractor = SkillExtractor(enable_external_skills=False)
    
    # テスト用メール本文（SES案件風）
    test_text = """
    【案件名】Java開発支援
    【場所】リモート（週1出社あり）
    【単価】60〜80万
    【精算】140-180h
    【内容】
    大手通信キャリア向けシステムの開発支援をお願いします。
    Spring Bootを用いたAPI開発がメインです。
    
    【必須スキル】
    - Java (SpringBoot) 3年以上
    - AWSの知見
    
    【尚可スキル】
    - React/TypeScript
    - Docker
    """
    
    print("--- AI抽出テスト開始 ---")
    try:
        result = extractor.extract_all(test_text)
        
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result.get('min_price') == 600000:
            print("\n[OK] 単価が正しく円単位で抽出されています。")
        else:
            print(f"\n[NG] 単価抽出が期待通りではありません: {result.get('min_price')}")
            
    except Exception as e:
        print(f"\n[ERROR] 実行中にエラーが発生しました: {e}")

if __name__ == "__main__":
    test_extraction()
