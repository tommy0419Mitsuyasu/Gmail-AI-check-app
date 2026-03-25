import os
import sqlite3
import logging
from flask import Blueprint, request, jsonify, current_app, render_template, session
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
from src.services.gmail_service import GmailService
from src.services.document_parser_service import DocumentParserService
from db_manager import db_manager
from skill_extractor import SkillExtractor

# Blueprintの作成
api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# インスタンスの初期化
skill_extractor = SkillExtractor()

# DB接続ラッパー関数
def get_db():
    conn = db_manager._get_connection()
    conn.row_factory = sqlite3.Row
    return conn

# ----- API エンドポイント -----

@api_bp.route('/api/search', methods=['GET'])
def search_projects():
    """案件を検索するAPI"""
    try:
        # GETリクエストのクエリパラメータから取得
        keywords = request.args.get('q', '')
        min_price = request.args.get('min_salary', type=int)
        max_price = request.args.get('max_salary', type=int)
        # skillsはカンマ区切りで渡される可能性があるため対処
        raw_skills = request.args.getlist('skills')
        skills = []
        for s in raw_skills:
            if ',' in s:
                skills.extend([x.strip() for x in s.split(',') if x.strip()])
            else:
                skills.append(s.strip())
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)

        # db_managerを使用して検索
        projects = db_manager.search_projects(
            keywords=keywords,
            min_price=min_price,
            max_price=max_price,
            skills=skills,
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'success': True,
            'projects': projects,
            'count': len(projects)
        })

    except Exception as e:
        logger.error(f"検索中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/api/upload', methods=['POST'])
def upload_file():
    """職務経歴書をアップロードして解析するAPI"""
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    if not file.filename.lower().endswith(('.pdf', '.docx', '.doc')):
        return jsonify({'error': '許可されていないファイル形式です（.pdf, .docx, .docのみ可）'}), 400

    try:
        # 一時ディレクトリに保存
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        # テキスト抽出
        text = ""
        if filename.lower().endswith('.pdf'):
            text = DocumentParserService.extract_text_from_pdf(filepath)
        elif filename.lower().endswith(('.docx', '.doc')):
            text = DocumentParserService.extract_text_from_docx(filepath)

        # 一時ファイルを削除
        try:
            os.remove(filepath)
        except Exception as e:
            logger.warning(f"一時ファイルの削除に失敗しました: {e}")

        if not text:
            return jsonify({'error': 'テキストを抽出できませんでした'}), 400

        # LLMでのスキル解析
        skills_dict = skill_extractor.extract_skills(text)
        
        # 自由記述からスキル解析する既存の互換機能
        return jsonify({
            'success': True,
            'message': '解析が完了しました',
            'skills': skills_dict
        })

    except Exception as e:
        logger.error(f"ファイル処理中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({'error': f'エラーが発生しました: {str(e)}'}), 500

@api_bp.route('/api/gmail_auth_status', methods=['GET'])
def check_gmail_auth():
    """Gmail認証状態を確認するAPI"""
    is_auth = GmailService.is_authenticated()
    return jsonify({
        'authenticated': is_auth,
        'email': session.get('user_email', '') if is_auth else ''
    })

@api_bp.route('/api/match_projects', methods=['POST'])
def match_projects():
    """入力されたスキルに基づいて案件をマッチングするAPI"""
    try:
        data = request.json
        skills = data.get('skills', [])
        
        if not skills:
            return jsonify({'success': False, 'message': 'スキルが指定されていません'}), 400

        # JavaScriptからは文字列またはオブジェクト({'name':'...'})の配列が送られてくる
        candidate_skills = []
        for s in skills:
            if isinstance(s, dict):
                candidate_skills.append(s)
            elif isinstance(s, str):
                candidate_skills.append({'name': s, 'level': '中級'})

        # db_managerを使用して最大2000件程度の案件を取得
        projects = db_manager.search_projects(limit=2000)
        
        from skill_matcher_enhanced import enhance_skill_matching
        
        scored_projects = []
        for proj in projects:
            proj_dict = dict(proj) # sqlite3.Rowから変換
            
            # APIの入力形式（{'skill': '名', 'type': 'must'}）へ案件の要求スキルを変換
            formatted_reqs = []
            for r in proj_dict.get('skills', []):
                if isinstance(r, dict):
                    formatted_reqs.append({
                        'skill': r.get('name', ''),
                        'type': r.get('type', 'want'),
                        'weight': 1.0
                    })
            
            # 作成した高精度マッチングエンジンでスコアを計算
            match_result = enhance_skill_matching(formatted_reqs, candidate_skills)
            score = match_result.get('match_ratio', 0.0)
            
            # スコアが少しでもあればリストに追加（または最低要件をクリアしたもの）
            if score > 0:
                proj_dict['match_percentage'] = score
                proj_dict['match_details'] = match_result
                scored_projects.append(proj_dict)

        # マッチ度の高い順に降順ソート
        scored_projects.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
        
        return jsonify({
            'status': 'success',
            'matches': scored_projects[:100] # トップ100件を返す
        })
    except Exception as e:
        logger.error(f"案件マッチング中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/api/emails/<email_id>', methods=['GET'])
def get_email(email_id):
    """Gmailの特定メールの詳細とマッチする案件を取得するAPI"""
    # スタブ実装
    return jsonify({
        'status': 'success',
        'email': {
            'subject': '未実装のメール内容',
            'from': '未実装',
            'date': '2025-01-01',
            'body': f'ID {email_id} のメール詳細取得は現在開発中の機能です。'
        },
        'extracted_skills': [],
        'matched_projects': []
    })

@api_bp.route('/api/save_skills', methods=['POST'])
def save_skills():
    """解析されたスキルをセッションに保存するAPI"""
    try:
        import json
        data = request.json
        skills = data.get('skills', [])
        engineer_id = data.get('engineer_id', 1)
        
        # スキルをフラスクセッションに保存（engineer_idごとに管理）
        session_key = f'engineer_skills_{engineer_id}'
        session[session_key] = skills
        
        logger.info(f"スキルの保存を受け付けました (engineer_id={engineer_id}): {len(skills)}件")
        
        return jsonify({
            'status': 'success',
            'message': 'スキルが保存されました',
            'engineer_id': engineer_id,
            'skill_count': len(skills)
        })
    except Exception as e:
        logger.error(f"スキル保存中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@api_bp.route('/api/engineers/<int:engineer_id>/skills', methods=['GET'])
def get_engineer_skills(engineer_id):
    """指定エンジニアのスキル情報を返すAPI"""
    try:
        # セッションからスキルを取得
        session_key = f'engineer_skills_{engineer_id}'
        skills = session.get(session_key, [])
        
        if not skills:
            return jsonify({
                'status': 'not_found',
                'message': 'スキル情報が見つかりません。トップページからスキルシートを読み込んでください。',
                'skills': []
            }), 404
        
        return jsonify({
            'status': 'success',
            'engineer_id': engineer_id,
            'skills': skills
        })
    except Exception as e:
        logger.error(f"スキル取得中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500
