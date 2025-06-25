import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
from datetime import datetime, timedelta
import re

# Gmail APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Gmail APIサービスを取得する"""
    creds = None
    token_path = 'token.pickle'
    
    # 保存済みの認証情報を読み込む
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    # 有効な認証情報がない場合は、ユーザーにログインを求める
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # 認証情報を保存
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    
    service = build('gmail', 'v1', credentials=creds)
    return service

def search_emails(service, query, max_results=10):
    """メールを検索する"""
    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        if not messages:
            return []
            
        return messages
    except Exception as e:
        print(f'An error occurred: {e}')
        return []

def get_email_content(service, msg_id):
    """メールの内容を取得する"""
    try:
        message = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='full'
        ).execute()
        
        # メールのヘッダーから件名と送信者を取得
        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '（件名なし）')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '（送信者不明）')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # メール本文を取得
        if 'parts' in message['payload']:
            parts = message['payload']['parts']
            data = parts[0]['body']['data']
        else:
            data = message['payload']['body']['data']
            
        # Base64デコード
        data = data.replace("-", "+").replace("_", "/")
        decoded_data = base64.b64decode(data).decode('utf-8')
        
        # HTMLタグを削除
        clean_text = re.sub(r'<[^>]+>', '', decoded_data)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return {
            'id': msg_id,
            'subject': subject,
            'from': sender,
            'date': date,
            'snippet': message.get('snippet', ''),
            'content': clean_text[:500] + ('...' if len(clean_text) > 500 else '')  # 最初の500文字のみ
        }
        
    except Exception as e:
        print(f'Error getting email content: {e}')
        return None

def find_matching_emails(skills):
    """スキルに基づいてマッチするメールを検索する"""
    try:
        service = get_gmail_service()
        
        # 過去30日間のメールを検索
        after_date = (datetime.now() - timedelta(days=30)).strftime('%Y/%m/%d')
        query = f'after:{after_date} (求人 OR 案件 OR 募集)'
        
        # スキルを検索クエリに追加
        skill_queries = [f'"{skill}"' for skill in skills]
        if skill_queries:
            query += ' (' + ' OR '.join(skill_queries) + ')'
        
        # メールを検索
        messages = search_emails(service, query)
        
        # メールの詳細を取得
        results = []
        for msg in messages[:10]:  # 最大10件まで処理
            email = get_email_content(service, msg['id'])
            if email:
                # スキルが含まれているか確認
                email_skills = [skill for skill in skills if skill.lower() in email['content'].lower() or skill.lower() in email['subject'].lower()]
                if email_skills:
                    email['matching_skills'] = email_skills
                    results.append(email)
        
        return results
        
    except Exception as e:
        print(f'Error in find_matching_emails: {e}')
        return []
