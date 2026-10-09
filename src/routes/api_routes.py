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
        
        # 単価が万円単位（1000未満）で送られてきた場合は円単位に変換
        if min_price is not None and min_price < 1000:
            min_price *= 10000
        if max_price is not None and max_price < 1000:
            max_price *= 10000
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
        
        flat_skills = []
        if isinstance(skills_dict, dict):
            for category, sk_list in skills_dict.items():
                for sk in sk_list:
                    if isinstance(sk, dict):
                        sk_copy = sk.copy()
                        sk_copy['category'] = category
                        flat_skills.append(sk_copy)
                    elif isinstance(sk, str):
                        flat_skills.append({'skill': sk, 'category': category})
        else:
            flat_skills = skills_dict if isinstance(skills_dict, list) else []
            
        # 自動的にセッションに保存（engineer_id=1として）
        session_key = 'engineer_skills_1'
        session[session_key] = flat_skills
        
        # 自由記述からスキル解析する既存の互換機能
        return jsonify({
            'status': 'success',
            'success': True,
            'message': '解析が完了しました',
            'skills': flat_skills,
            'extracted_text': text
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
        
        # 単価フィルタリング用の値を取得（存在すれば整数に変換）
        min_price_val = data.get('min_price')
        max_price_val = data.get('max_price')
        target_price = None
        max_price = None
        
        if min_price_val:
            try:
                target_price = int(min_price_val)
                # 単価が万円単位（1000未満）で送られてきた場合は円単位に変換
                if target_price < 1000:
                    target_price *= 10000
            except ValueError:
                pass
                
        if max_price_val:
            try:
                max_price = int(max_price_val)
                # 単価が万円単位（1000未満）で送られてきた場合は円単位に変換
                if max_price < 1000:
                    max_price *= 10000
            except ValueError:
                pass
        
        if not skills:
            return jsonify({'success': False, 'message': 'スキルが指定されていません'}), 400

        from matching_engine import get_engine
        engine = get_engine()
        
        # 新しいマッチングエンジンでスコアリング（過去60日分、スコア20%以上、単価指定があればフィルタリング）
        result = engine.match(raw_skills=skills, days=60, limit=100, min_score=20.0, target_price=target_price, max_price=max_price)
        
        # APIレスポンス用にマッピング
        formatted_matches = []
        for match in result['matches']:
            # フロントエンド（main.js）が期待するプロパティ名にマッピング
            formatted_match = {
                'id': match['id'],
                'message_id': match['message_id'],
                'title': match['title'],
                'subject': match['subject'],
                'sender': match['sender'],
                'created_at': match['received_at'],
                'salary': match['price_text'],
                'location': match['location'],
                'match_percentage': match['match_percentage'],
                'required_skills': match['required_skills'],
                'must_skills': match['must_skills'],
                'matched_skills': match['matched_skills'],
                # detailed match info
                'match_details': match['match_details'],
                'reasons': match['reasons'],
                'description': '【AI解析によるマッチング理由】\n' + '\n'.join('・' + r for r in match['reasons']),
                'gmail_url': match['gmail_url']
            }
            formatted_matches.append(formatted_match)

        return jsonify({
            'status': 'success',
            'matches': formatted_matches
        })
    except Exception as e:
        logger.error(f"案件マッチング中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/api/emails/<email_id>', methods=['GET'])
def get_email(email_id):
    """Gmailの特定メールの詳細を取得するAPI"""
    try:
        conn = get_db()
        row = conn.execute('SELECT subject, sender, received_at, body FROM emails WHERE message_id = ?', (email_id,)).fetchone()
        conn.close()
        
        if row:
            return jsonify({
                'status': 'success',
                'email': {
                    'subject': row['subject'],
                    'from': row['sender'],
                    'date': row['received_at'],
                    'body': row['body']
                }
            })
        else:
            return jsonify({'status': 'error', 'message': 'メールが見つかりません'}), 404
            
    except Exception as e:
        logger.error(f"メール詳細取得中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

@api_bp.route('/api/feedback', methods=['POST'])
def save_feedback():
    """マッチングのフィードバックを保存するAPI"""
    try:
        import json
        data = request.json
        project_id = data.get('project_id')
        is_good = data.get('is_good')
        candidate_skills = data.get('candidate_skills', [])
        comment = data.get('comment', '')
        
        if not project_id or is_good is None:
            return jsonify({'success': False, 'message': '必須パラメータが不足しています'}), 400
            
        success = db_manager.save_feedback(
            project_id=project_id,
            candidate_skills=json.dumps(candidate_skills, ensure_ascii=False),
            is_good=is_good,
            comment=comment
        )
        
        if success:
            return jsonify({'success': True, 'message': 'フィードバックを保存しました'})
        else:
            return jsonify({'success': False, 'message': '保存に失敗しました'}), 500
            
    except Exception as e:
        logger.error(f"フィードバック保存中にエラーが発生しました: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500
