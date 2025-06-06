# GmailToSkillSheetMatcherForSES

AIを活用して、SES事業におけるエンジニアのスキルシートとGmail経由で届く案件情報を自動でマッチングするシステムです。

## 機能

- スキルシートの自動解析と構造化
- Gmailからの案件情報の自動抽出
- AIを活用した最適なマッチングの提案
- 直感的なダッシュボードでの結果確認
- 新規マッチングの通知機能

## セットアップ

1. リポジトリをクローンします：
   ```bash
   git clone https://github.com/tommy0419Mitsuyasu/Gmail-AI-check-app.git
   cd Gmail-AI-check-app
   ```

2. 仮想環境を作成して有効化します：
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # Windows
   # または
   # source venv/bin/activate  # macOS/Linux
   ```

3. 依存パッケージをインストールします：
   ```bash
   pip install -r requirements.txt
   ```

4. 環境変数を設定します：
   ```bash
   cp .env.example .env
   ```
   `.env` ファイルを編集して、必要な認証情報を設定してください。

## 使用方法

1. アプリケーションを起動します：
   ```bash
   cd src
   uvicorn main:app --reload
   ```

2. ブラウザで `http://localhost:8000/api/docs` にアクセスすると、APIドキュメントを確認できます。

## プロジェクト構成

```
Gmail-AI-check-app/
├── config/               # 設定ファイル
│   └── settings.py       # アプリケーション設定
├── src/                  # ソースコード
│   ├── modules/          # 機能モジュール
│   │   ├── skill_sheet_parser/    # スキルシート解析モジュール
│   │   ├── gmail_project_scanner/ # Gmailスキャンモジュール
│   │   ├── intelligent_matcher/   # マッチングエンジン
│   │   └── dashboard_notifier/    # ダッシュボード・通知
│   ├── models.py         # データモデル
│   └── main.py           # メインアプリケーション
├── tests/                # テストコード
├── .env.example          # 環境変数テンプレート
├── requirements.txt      # 依存パッケージ
└── README.md            # このファイル
```

## ライセンス

このプロジェクトはプライベートライセンスです。

## 開発者

- tommy0419Mitsuyasu

## 連絡先

ご質問やご要望がございましたら、リポジトリのIssueにご登録ください。
