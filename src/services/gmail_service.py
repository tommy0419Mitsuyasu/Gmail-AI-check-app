import os
import base64
from typing import Dict, List, Any
import logging
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from flask import session

logger = logging.getLogger(__name__)

class GmailService:
    # プロジェクトルートディレクトリの絶対パスを取得
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 認証情報を保存するファイルのパス
    CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
    TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/userinfo.email']

    @staticmethod
    def get_credentials():
        creds = None
        if os.path.exists(GmailService.TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(GmailService.TOKEN_FILE, GmailService.SCOPES)
        return creds

    @staticmethod
    def is_authenticated():
        creds = GmailService.get_credentials()
        if creds and creds.valid:
            if 'user_email' not in session:
                try:
                    user_info_service = build('oauth2', 'v2', credentials=creds)
                    user_info = user_info_service.userinfo().get().execute()
                    session['user_email'] = user_info.get('email')
                except Exception as e:
                    logger.error(f"ユーザー情報の取得に失敗しました: {e}")
            return True
        return False
        
    @staticmethod
    def get_service():
        creds = GmailService.get_credentials()
        if not creds or not creds.valid:
            return None
        return build('gmail', 'v1', credentials=creds)
