"""
外部スキルサービス連携モジュール
- 外部APIを使用したスキル抽出の拡張
- 関連スキルの提案
"""
import os
import json
import logging
from typing import List, Dict, Optional, Any
import requests
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

logger = logging.getLogger(__name__)

class ExternalSkillService:
    """外部スキルサービスとの連携を管理するクラス"""
    
    def __init__(self, enabled: bool = False, api_key: str = None):
        """
        初期化
        
        Args:
            enabled: 外部APIを使用するかどうか
            api_key: 外部APIのAPIキー
        """
        self.enabled = enabled
        self.api_key = api_key or os.getenv("EXTERNAL_SKILL_API_KEY")
        self.base_url = "https://api.example.com/skills"  # 実際のAPIエンドポイントに置き換えてください
        self.timeout = 10  # タイムアウト(秒)
        
        # APIキーが設定されていない場合は無効化
        if not self.api_key or self.api_key == "your_api_key_here":
            self.enabled = False
            logger.warning("外部スキルAPIのAPIキーが設定されていないため、無効化されます")
    
    def _make_api_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        APIリクエストを実行
        
        Args:
            endpoint: APIエンドポイント
            params: クエリパラメータ
            
        Returns:
            APIレスポンスのJSONデータ
        """
        if not self.enabled or not self.api_key:
            return None
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/{endpoint}",
                headers=headers,
                params=params or {},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"外部スキルAPIのリクエストに失敗しました: {str(e)}")
            return None
    
    def get_related_skills(self, skill_name: str, limit: int = 5) -> List[Dict]:
        """
        関連スキルを取得
        
        Args:
            skill_name: スキル名
            limit: 取得する関連スキルの最大数
            
        Returns:
            関連スキルのリスト
        """
        if not self.enabled:
            return []
            
        params = {"q": skill_name, "limit": limit}
        data = self._make_api_request("related", params)
        
        if not data or "skills" not in data:
            return []
            
        return [
            {"name": skill["name"], "type": skill.get("type", "related")}
            for skill in data["skills"][:limit]
        ]
    
    def enhance_skill_extraction(self, extracted_skills: List[Dict], text: str = "") -> List[Dict]:
        """
        抽出されたスキルを拡張
        
        Args:
            extracted_skills: 抽出済みのスキルリスト
            text: 元のテキスト（オプション）
            
        Returns:
            拡張されたスキルリスト
        """
        if not self.enabled or not extracted_skills:
            return extracted_skills
            
        enhanced_skills = list(extracted_skills)
        existing_skills = {s["name"].lower() for s in extracted_skills}
        
        for skill in extracted_skills:
            try:
                related_skills = self.get_related_skills(skill["name"])
                
                for related in related_skills:
                    if related["name"].lower() not in existing_skills:
                        # 関連スキルの重要度は元のスキルより低く設定
                        enhanced_skills.append({
                            "name": related["name"],
                            "type": related["type"],
                            "importance": skill.get("importance", 0.3) * 0.7,  # 重要度を下げる
                            "source": "external_api",
                            "original_skill": skill["name"]
                        })
                        existing_skills.add(related["name"].lower())
                        
            except Exception as e:
                logger.error(f"スキル '{skill['name']}' の拡張中にエラーが発生: {str(e)}")
                continue
                
        return enhanced_skills


# シングルトンインスタンス
external_skill_service = ExternalSkillService(
    enabled=os.getenv("ENABLE_EXTERNAL_SKILL_API", "false").lower() == "true"
)
