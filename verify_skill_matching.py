
import logging
import sys
import os
import io

# 標準出力のエンコーディングをUTF-8に強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# パス設定
sys.path.append(os.getcwd())

from skill_matcher_enhanced import enhance_skill_matching
from vector_engine import vector_engine

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(message)s')

def verify_matching():
    print("VectorEngine初期化待ち...")
    # 明示的に初期化（通常はインポート時に行われる）
    if not vector_engine.model:
        print("モデルをロード中...")
        vector_engine.__init__()
    print("初期化完了\n")

    test_cases = [
        {
            "name": "意味的関連性テスト (AI vs ML)",
            "requirements": [{"skill": "Artificial Intelligence", "level": "中級", "weight": 1.0}],
            "candidate": [{"name": "Machine Learning", "level": "中級"}]
        },
        {
            "name": "関連技術テスト (Python vs Django)",
            "requirements": [{"skill": "Python", "level": "中級", "weight": 1.0}],
            "candidate": [{"name": "Django", "level": "中級"}]
        },
        {
            "name": "全く異なる技術 (Python vs Cooking)",
            "requirements": [{"skill": "Python", "level": "中級", "weight": 1.0}],
            "candidate": [{"name": "Cooking", "level": "中級"}]
        },
        {
            "name": "表記ゆれ複合 (React.js vs ReactJS)",
            "requirements": [{"skill": "React.js", "level": "中級", "weight": 1.0}],
            "candidate": [{"name": "ReactJS", "level": "中級"}]
        }
    ]

    print("=== 事前類似度チェック ===")
    for case in test_cases:
        req = case['requirements'][0]['skill']
        cand = case['candidate'][0]['name']
        v1 = vector_engine.encode(req)
        v2 = vector_engine.encode(cand)
        sim = vector_engine.calculate_similarity(v1, v2)
        print(f"{req} vs {cand}: {sim:.4f}")
    print("\n")

    for case in test_cases:
        print(f"=== {case['name']} ===")
        print(f"要求: {case['requirements'][0]['skill']}")
        print(f"候補: {case['candidate'][0]['name']}")
        
        result = enhance_skill_matching(case['requirements'], case['candidate'])
        
        if result['matches']:
            match = result['matches'][0]
            print(f"結果: マッチしました！")
            print(f"  マッチしたスキル: {match['matched_skill']}")
            print(f"  スコア: {match['score']:.4f}")
            print(f"  タイプ: {match['match_type']}")
            if 'similarity' in match:
                print(f"  類似度: {match['similarity']:.4f}")
        else:
            print("結果: マッチしませんでした")
        print("-" * 30 + "\n")

if __name__ == "__main__":
    verify_matching()
