
import logging
import sys
from skill_extractor import skill_extractor

# 設定
logging.basicConfig(level=logging.INFO)
sys.stdout.reconfigure(encoding='utf-8')

def test_project_extraction():
    sample_texts = [
        """
        【案件】Java Webシステム開発案件
        【単価】60万〜70万円
        【場所】東京都内（リモート可）
        【精算】140H-180H
        【商流】エンド直
        【内容】
        Spring Bootを用いたWebアプリケーション開発です。
        """,
        """
        [募集] Pythonデータ分析
        単価：80万円 (スキル見合い)
        場所：渋谷区
        商流：元請
        リモート：フルリモート
        """,
        """
        C#.NET開発 
        50-60万
        大阪
        二社先
        """
    ]

    print("=== Skill Extraction Test ===\n")

    for i, text in enumerate(sample_texts):
        print(f"--- Case {i+1} ---")
        info = skill_extractor.extract_project_info(text)
        
        print(f"Title: {info['title']}")
        print(f"Price: {info['min_price']} - {info['max_price']} ({info['price_text']})")
        print(f"Hours: {info['min_hours']} - {info['max_hours']}")
        print(f"Flow: {info['commercial_flow']}")
        print(f"Location: {info['location']}")
        print(f"Remote: {info['remote_type']}")
        print("\n")

if __name__ == "__main__":
    test_project_extraction()
