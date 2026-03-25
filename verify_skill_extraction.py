
import logging
import sys
import os
import io
from textwrap import dedent

# 標準出力のエンコーディングをUTF-8に強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# カレントディレクトリをパスに追加してインポートできるようにする
sys.path.append(os.getcwd())

from skill_extractor import SkillExtractor

# ログ設定
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)

def verify_extraction():
    # ロガー設定を確実にする
    root_logger = logging.getLogger()
    for h in root_logger.handlers:
        root_logger.removeHandler(h)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    print("SkillExtractorを初期化します...")
    print(f"Module path: {sys.modules['skill_extractor'].__file__}")
    extractor = SkillExtractor()
    print(f"SKILL_DB size: {len(extractor.skill_db)}")
    print(f"Sample skill: {list(extractor.skill_db.keys())[0]}")
    
    import inspect
    print("\n--- Source of _find_skill_sections ---")
    try:
        print(inspect.getsource(extractor._find_skill_sections))
    except Exception as e:
        print(f"Could not get source: {e}")
    print("--------------------------------------\n")

    
    test_cases = [
        {
            "name": "ヘッダーパターン1 (要求スキル/尚可)",
            "text": dedent("""
            【要求スキル】
            ・Python
            ・Django
            
            【尚可】
            ・AWS
            ・Docker
            """)
        },
        {
            "name": "ヘッダーパターン2 (Must/Wants)",
            "text": dedent("""
            <Must>
            Java, Spring Boot
            
            <Wants>
            Vue.js
            """)
        },
        {
            "name": "1行完結型",
            "text": dedent("""
            業務内容: Webアプリ開発
            必須要件: React, TypeScript
            歓迎条件: Next.js
            """)
        },
        {
            "name": "文脈パターン",
            "text": dedent("""
            開発環境
            言語：Go (必須)
            DB：PostgreSQL
            インフラ：GCP (尚可)
            """)
        }
    ]
    
    for case in test_cases:
        print(f"\n{'='*20}\n検証ケース: {case['name']}\n{'='*20}")
        print(f"テキスト:\n{case['text']}")
        print("-" * 20)
        
        skills = extractor.extract_candidate_skills(case['text'], min_confidence=0.1)
        
        print("抽出結果:")
        for s in skills:
            req_mark = "[必須]" if s['is_required'] else ""
            pref_mark = "[尚可]" if s['is_preferred'] else ""
            print(f"- {s['skill']}: {req_mark}{pref_mark} (信頼度: {s['confidence']:.2f}, 重要度: {s['importance']:.2f})")

if __name__ == "__main__":
    verify_extraction()
