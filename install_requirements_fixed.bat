@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ===================================
echo  GmailToSkillSheetMatcherForSES セットアップ
echo ===================================
echo このセットアップでは以下の作業を行います：
echo 1. Pythonのバージョンチェック
echo 2. 仮想環境の作成
echo 3. 必要なパッケージのインストール
echo ===================================
echo.

:: 1. Pythonのバージョンチェック
echo Pythonのバージョンを確認しています...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [エラー] Pythonがインストールされていないか、PATHに追加されていません。
    echo Python 3.7以上をインストールしてから再度実行してください。
    echo 公式サイト: https://www.python.org/downloads/
    pause
    exit /b 1deactivate
    rmdir /s /q venv
    python -m venv venv
    .\venv\Scripts\activatepip install --upgrade pip
    pip install --only-binary :all: pydantic
    pip install fastapi uvicorn
)

:: 2. 仮想環境の作成
echo.
echo 仮想環境をセットアップしています...
if not exist "venv\" (
    echo 新しい仮想環境を作成しています...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [エラー] 仮想環境の作成に失敗しました。
        echo 管理者権限で実行しているか確認してください。
        pause
        exit /b 1
    )
    echo 仮想環境が正常に作成されました。
) else (
    echo 既存の仮想環境が見つかりました。
)

:: 仮想環境をアクティベート
call venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo [エラー] 仮想環境のアクティベートに失敗しました。
    echo 手動で以下のコマンドを実行してみてください：
    echo   .\venv\Scripts\activate
    pause
    exit /b 1
)

:: 3. パッケージのインストール
echo.
echo 必要なパッケージをインストールしています...
echo 初回は時間がかかる場合があります...
echo.

:: pipのアップグレード
echo pipをアップグレードしています...
python -m pip install --upgrade pip
if %ERRORLEVEL% NEQ 0 (
    echo [警告] pipのアップグレードに失敗しましたが、続行します...
)

:: 依存パッケージのインストール
echo 依存パッケージをインストールしています...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [エラー] 依存パッケージのインストールに失敗しました。
    echo インターネット接続を確認してください。
    pause
    exit /b 1
)

:: Windows用の追加パッケージ
echo.
echo Windows用の追加パッケージをインストールしています...
pip install python-magic-bin==0.4.14

:: 完了メッセージ
echo.
echo ===================================
echo セットアップが完了しました！
echo ===================================
echo.
echo アプリケーションを起動するには、以下のコマンドを実行してください：
echo   .\run_app.bat
echo.
echo 問題が発生した場合は、以下の情報をメモして開発者に連絡してください：
echo - エラーメッセージ
echo - 実行したコマンド
echo - 環境情報（OS、Pythonバージョンなど）
echo.
pause
