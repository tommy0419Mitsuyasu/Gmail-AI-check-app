
import logging
import sys
import os
import io

# 標準出力のエンコーディングをUTF-8に強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# カレントディレクトリをパスに追加してインポートできるようにする
sys.path.append(os.getcwd())

from vector_engine import VectorEngine

# ログ設定
logging.basicConfig(
    level=logging.INFO, 
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)

def test_vector_engine():
    print("VectorEngineを初期化中... (初回はモデルのダウンロードに時間がかかります)")
    engine = VectorEngine()
    
    if not engine.model:
        print("エラー: モデルの初期化に失敗しました")
        return

    test_pairs = [
        ("Python", "Java", "プログラミング言語同士 (高)"),
        ("Python", "Django", "言語とフレームワーク (高)"),
        ("Python", "Cooking", "無関係 (低)"),
        ("Web Development", "Frontend", "関連概念 (高)"),
        ("React", "Vue.js", "競合フレームワーク (中-高)"),
        ("AWS", "Cloud Computing", "技術と概念 (高)")
    ]
    
    print("\n=== 行列類似度テスト ===")
    for text1, text2, desc in test_pairs:
        vec1 = engine.encode(text1)
        vec2 = engine.encode(text2)
        
        sim = engine.calculate_similarity(vec1, vec2)
        print(f"'{text1}' vs '{text2}' ({desc}): {sim:.4f}")
        
    print("\n=== リスト化テスト ===")
    texts = ["Python", "Java", "Ruby"]
    vectors = engine.encode(texts)
    print(f"入力: {texts}")
    print(f"ベクトル形状: {vectors.shape}")
    
    if vectors.shape[0] == 3 and vectors.shape[1] > 0:
        print("成功: ベクトル形状が正しいです")
    else:
        print("失敗: ベクトル形状が不正です")

if __name__ == "__main__":
    test_vector_engine()
