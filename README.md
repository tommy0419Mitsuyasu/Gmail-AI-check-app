# GmailToSkillSheetMatcherForSES

AIと自然言語処理を活用して、SES事業におけるエンジニアのスキルシート（PDF/Word）と、Gmail経由で届く大量の案件メールを自動で高精度にマッチングするシステムです。

## 主な機能

- **スキルシートの自動解析**: アップロードされた職務経歴書（PDF/Word等）から、エンジニアの経験スキルや年数を自動抽出します。
- **Gmailからの案件自動抽出**: バックグラウンド処理（`batch_processor.py`）により、指定条件の案件メールを自動で取得・データベース化します。
- **ハイブリッド・マッチングエンジン**: 単純なキーワードの一致ではなく、「必須スキル」「尚可スキル」「開発環境」などのセクション解析と、スキルの「希少度（IDF）」や「充足率・強み活用度」を考慮した高度なスコアリングを行います（`matching_engine.py`）。
- **理由の可視化**: なぜその案件がマッチしたのか（一致したスキル、代替可能なスキル、不足しているスキル等）を画面上にわかりやすく表示します。

## アーキテクチャと使用技術

- **バックエンド**: Python, Flask
- **データベース**: SQLite3 (フルテキスト検索 FTS5 対応)
- **ベクトル検索**: `SentenceTransformer` によるハイブリッド検索
- **フロントエンド**: HTML, Vanilla JS, Tailwind CSS
- **外部API**: Gmail API (OAuth2.0)

## セットアップ手順

1. リポジトリをクローンします：
   ```bash
   git clone https://github.com/tommy0419Mitsuyasu/Gmail-AI-check-app.git
   cd Gmail-AI-check-app
   ```

2. 仮想環境を作成して有効化します：
   ```bash
   python -m venv venv
   # Windowsの場合
   .\venv\Scripts\activate
   # macOS/Linuxの場合
   # source venv/bin/activate
   ```

3. 依存パッケージをインストールします：
   ```bash
   pip install -r requirements.txt
   ```

4. 環境変数を設定します：
   `.env.example` をコピーして `.env` ファイルを作成し、必要なAPIキー（Google Gemini APIなど）やFlaskのシークレットキーを設定してください。
   ```bash
   cp .env.example .env
   ```

5. Gmail APIの認証情報を準備します：
   Google Cloud Consoleで作成した `credentials.json` をプロジェクトルートに配置してください。

## 起動方法

アプリケーションを起動すると、Webサーバーとバックグラウンドの定期バッチ処理（メール取得）が同時に立ち上がります。

```bash
python app.py
```

ブラウザで `http://localhost:5000` にアクセスし、システムを利用してください。初回起動時は画面右上からGmailの連携（OAuth認証）を行う必要があります。

## プロジェクト構成

```text
Gmail-AI-check-app/
├── app.py                  # メインアプリケーション（Flaskサーバー起動）
├── batch_processor.py      # Gmailからの定期案件取得バッチ
├── db_manager.py           # データベース（SQLite）操作ラッパー
├── matching_engine.py      # 新型ハイブリッド・マッチングエンジン
├── skill_extractor.py      # スキル抽出処理（Gemini API等を利用）
├── vector_engine.py        # ベクトル化エンジン（SentenceTransformer）
├── src/                    # APIルート定義
│   └── routes/             # 各種エンドポイント（api_routes.py 等）
├── static/                 # フロントエンド静的ファイル
│   ├── css/
│   └── js/                 # main.js (UI処理)
├── templates/              # HTMLテンプレート
├── requirements.txt        # 依存パッケージ一覧
└── README.md               # このファイル
```

## ライセンス

このプロジェクトはプライベートライセンスです。

## 開発者

- tommy0419Mitsuyasu

