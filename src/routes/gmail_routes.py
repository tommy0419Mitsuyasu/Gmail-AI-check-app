import os
import logging
from flask import Blueprint, request, redirect, url_for, session, jsonify, current_app
from google_auth_oauthlib.flow import Flow
from src.services.gmail_service import GmailService

# Blueprintの作成
gmail_bp = Blueprint('gmail', __name__)
logger = logging.getLogger(__name__)

# HTTPS環境でないローカル開発用（本番環境では削除するか環境変数で制御）
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

@gmail_bp.route('/gmail/auth')
def authorize():
    """Gmail認証の開始（Googleへのリダイレクト）"""
    try:
        # すでに認証済みの場合はホームへ
        if GmailService.is_authenticated():
            return redirect(url_for('views.index'))

        # credentials.json が存在するか確認
        if not os.path.exists(GmailService.CREDENTIALS_FILE):
            logger.error(f"認証情報ファイル {GmailService.CREDENTIALS_FILE} が見つかりません。")
            return "Gmail APIの認証情報ファイルが見つかりません。管理者に連絡してください。", 500

        flow = Flow.from_client_secrets_file(
            GmailService.CREDENTIALS_FILE,
            scopes=GmailService.SCOPES
        )
        flow.redirect_uri = url_for('gmail.auth_callback', _external=True)

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        session['state'] = state
        return redirect(authorization_url)

    except Exception as e:
        logger.error(f"Gmail認証のためのリダイレクト生成に失敗しました: {e}", exc_info=True)
        return "サーバー内部エラーが発生しました", 500

@gmail_bp.route('/gmail/auth/callback')
def auth_callback():
    """Googleからのコールバック処理"""
    try:
        state = session.get('state')

        flow = Flow.from_client_secrets_file(
            GmailService.CREDENTIALS_FILE,
            scopes=GmailService.SCOPES,
            state=state
        )
        flow.redirect_uri = url_for('gmail.auth_callback', _external=True)

        authorization_response = request.url
        # fetch_tokenでアクセストークンを取得
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials

        # token.jsonに保存
        with open(GmailService.TOKEN_FILE, 'w') as f:
            f.write(credentials.to_json())

        # 認証成功後はホームにリダイレクト
        return redirect(url_for('views.index'))

    except Exception as e:
        logger.error(f"Gmailからのコールバック処理に失敗しました: {e}", exc_info=True)
        return "認証に失敗しました。もう一度お試しください。", 400

@gmail_bp.route('/gmail/disconnect', methods=['POST'])
def disconnect():
    """Gmailとの連携を解除するAPI"""
    try:
        # トークンファイルを削除
        if os.path.exists(GmailService.TOKEN_FILE):
            os.remove(GmailService.TOKEN_FILE)
            
        # セッション情報をクリア
        session.pop('user_email', None)
        session.pop('state', None)

        return jsonify({"success": True, "message": "Gmailとの連携を解除しました。"})
    except Exception as e:
        logger.error(f"Gmailの連携解除処理に失敗しました: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
