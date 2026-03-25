import logging
from flask import Blueprint, render_template, redirect, request, session
from src.services.gmail_service import GmailService

# Blueprintの作成
view_bp = Blueprint('views', __name__)
logger = logging.getLogger(__name__)

# ----- 画面レンダリング エンドポイント -----

@view_bp.route('/')
def index():
    """メインページ（ホーム画面）"""
    try:
        is_auth = GmailService.is_authenticated()
    except Exception:
        is_auth = False
    return render_template('index.html', is_authenticated=is_auth)

@view_bp.route('/search')
def search_page():
    """案件検索画面"""
    return render_template('search.html')

@view_bp.route('/upload')
def upload_page():
    """アップロード（スキルシート登録）画面"""
    return render_template('upload.html')

@view_bp.route('/projects')
def projects_page():
    """プロジェクト一覧画面"""
    return render_template('projects.html')

@view_bp.route('/engineers')
def engineers_page():
    """エンジニア一覧画面"""
    return render_template('engineers.html')

# エラーハンドラー
@view_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('search.html', error="ページが見つかりません"), 404

@view_bp.app_errorhandler(500)
def internal_server_error(e):
    return render_template('search.html', error="サーバー内部でエラーが発生しました"), 500
