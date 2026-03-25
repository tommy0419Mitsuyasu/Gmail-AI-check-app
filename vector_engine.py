
import numpy as np
import logging
from typing import List, Union
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import threading

class VectorEngine:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VectorEngine, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        if self._initialized:
            return
            
        logging.info(f"Initializing VectorEngine with model: {model_name}")
        try:
            # モデルのロード（初回はダウンロードが発生）
            self.model = SentenceTransformer(model_name)
            self._initialized = True
            logging.info("VectorEngine initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize VectorEngine: {e}")
            self.model = None
            
    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """テキストをベクトルに変換する"""
        if not self.model:
            logging.warning("VectorEngine is not initialized properly.")
            return np.array([])
            
        if isinstance(texts, str):
            texts = [texts]
            
        try:
            return self.model.encode(texts)
        except Exception as e:
            logging.error(f"Error during encoding: {e}")
            return np.array([])
            
    def calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """2つのベクトル間のコサイン類似度を計算する"""
        if vec1.size == 0 or vec2.size == 0:
            return 0.0
            
        # 1次元配列の場合は2次元に変換
        if vec1.ndim == 1:
            vec1 = vec1.reshape(1, -1)
        if vec2.ndim == 1:
            vec2 = vec2.reshape(1, -1)
            
        try:
            return float(cosine_similarity(vec1, vec2)[0][0])
        except Exception as e:
            logging.error(f"Error calculating similarity: {e}")
            return 0.0

# グローバルインスタンス
vector_engine = VectorEngine()
