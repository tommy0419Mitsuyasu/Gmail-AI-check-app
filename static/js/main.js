// ドラッグ＆ドロップ機能の実装
document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('progressBar');
    const resultSection = document.getElementById('resultSection');
    const skillsByCategory = document.getElementById('skillsByCategory');
    const textPreview = document.getElementById('textPreview');
    const backToUpload = document.getElementById('backToUpload');
    const findProjectsBtn = document.getElementById('findProjectsBtn');
    const gmailResultsSection = document.getElementById('gmailResultsSection');
    const gmailResultsBody = document.getElementById('gmailResultsBody');
    const backToSkillsBtn = document.getElementById('backToSkillsBtn');
    const gmailLoading = document.getElementById('gmailLoading');
    const gmailError = document.getElementById('gmailError');
    const gmailAuthBtn = document.getElementById('gmailAuthBtn');
    const gmailAuthStatus = document.getElementById('gmailAuthStatus');
    const gmailAuthContainer = document.getElementById('gmailAuthContainer');
    const gmailSearchContainer = document.getElementById('gmailSearchContainer');
    const gmailAuthError = document.getElementById('gmailAuthError');

    // ドラッグ＆ドロップのイベントを防止
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // ドラッグ中のスタイル変更
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dropZone.classList.add('border-blue-400', 'bg-blue-50');
    }

    function unhighlight() {
        dropZone.classList.remove('border-blue-400', 'bg-blue-50');
    }

    // ファイルがドロップされたとき
    dropZone.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // ファイルが選択されたとき
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });

    // ファイルを処理する関数
    function handleFiles(files) {
        if (files.length === 0) return;
        
        const file = files[0];
        
        // ファイルの種類を確認
        const fileType = file.name.split('.').pop().toLowerCase();
        if (!['pdf', 'docx', 'doc'].includes(fileType)) {
            showError('無効なファイル形式', 'PDFまたはWord形式のファイルを選択してください。', 'サポートされている形式: .pdf, .docx, .doc');
            return;
        }
        
        // ファイルサイズを確認 (16MB以下)
        if (file.size > 16 * 1024 * 1024) {
            showError('ファイルサイズが大きすぎます', '16MB以下のファイルを選択してください。', 'より小さいサイズのファイルをアップロードしてください。');
            return;
        }
        
        // ファイル情報を表示
        fileName.textContent = file.name;
        fileInfo.classList.remove('hidden');
        
        // アップロードボタンにイベントを追加
        uploadBtn.onclick = function() {
            uploadFile(file);
        };
    }
    
    // ファイルをアップロードする関数
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        // プログレスバーを表示
        uploadProgress.classList.remove('hidden');
        fileInfo.classList.add('hidden');
        
        // プログレスバーのアニメーション
        let progress = 0;
        const interval = setInterval(() => {
            progress += 5;
            if (progress > 90) {
                clearInterval(interval);
            }
            progressBar.style.width = progress + '%';
        }, 100);
        
        // サーバーにアップロード
        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            clearInterval(interval);
            progressBar.style.width = '100%';
            
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.error || 'アップロードに失敗しました');
                });
            }
            return response.json();
        })
        .then(data => {
            setTimeout(() => {
                uploadProgress.classList.add('hidden');
                showResults(data.skills, data.text);
            }, 500);
        })
        .catch(error => {
            console.error('Error:', error);
            uploadProgress.classList.add('hidden');
            showError('エラーが発生しました', error.message, 'もう一度お試しください。');
            fileInfo.classList.remove('hidden');
        });
    }
    
    // エラーメッセージを表示する関数
    function showError(title, message, resolution = '') {
        // 既存のエラーメッセージを削除
        const existingError = document.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        const errorHtml = `
            <div class="error-message">
                <p class="error-message-title">${title}</p>
                <p class="error-message-text">${message}</p>
                ${resolution ? `<p class="error-message-text">${resolution}</p>` : ''}
            </div>
        `;
        
        // エラーメッセージを表示
        document.querySelector('.max-w-4xl').insertAdjacentHTML('afterbegin', errorHtml);
    }
    
    // 結果を表示する関数
    function showResults(skills, extractedText) {
        // テキストプレビューを更新
        textPreview.textContent = extractedText || 'テキストを抽出できませんでした。';
        
        // スキルをカテゴリごとにグループ化
        const categories = {};
        
        skills.forEach(skill => {
            if (!categories[skill.category_name]) {
                categories[skill.category_name] = [];
            }
            categories[skill.category_name].push(skill);
        });
        
        // スキルカテゴリを表示
        skillsByCategory.innerHTML = '';
        
        // スキルが見つからなかった場合
        if (Object.keys(categories).length === 0) {
            const noSkills = document.createElement('div');
            noSkills.className = 'text-center py-4 text-gray-500';
            noSkills.innerHTML = `
                <i class="fas fa-info-circle text-2xl mb-2 text-gray-400"></i>
                <p>スキルを抽出できませんでした。別のファイルでお試しください。</p>
            `;
            skillsByCategory.appendChild(noSkills);
            return;
        }
        
        // カテゴリごとにスキルを表示
        Object.entries(categories).forEach(([category, skillList]) => {
            const categoryElement = document.createElement('div');
            categoryElement.className = 'skill-category';
            
            const skillsHtml = skillList.map(skill => `
                <div class="skill-badge">
                    ${skill.skill_name}
                    ${skill.count ? `<span class="ml-1 text-blue-600">×${skill.count}</span>` : ''}
                </div>
            `).join('');
            
            categoryElement.innerHTML = `
                <h3>${category}</h3>
                <div class="flex flex-wrap">
                    ${skillsHtml}
                </div>
            `;
            
            skillsByCategory.appendChild(categoryElement);
        });
        
        resultSection.classList.remove('hidden');
        
        // 結果セクションまでスクロール
        resultSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    // 戻るボタン
    backToUpload.addEventListener('click', function() {
        resultSection.classList.add('hidden');
        fileInput.value = '';
        fileName.textContent = '';
        fileInfo.classList.add('hidden');
    });
    
    // スキルを取得する関数
    async function fetchSkills() {
        const skillBadges = document.querySelectorAll('.skill-badge');
        const skills = [];
        
        skillBadges.forEach(badge => {
            skills.push(badge.textContent.trim().replace(/×\d+$/, ''));
        });
        
        return skills;
    }
    
    // 案件を探すボタン
    findProjectsBtn.addEventListener('click', async function() {
        // スキルを取得してから検索を実行
        const skills = await fetchSkills();
        if (skills.length === 0) {
            showError('スキルが見つかりません', 'スキルを抽出してから再度お試しください。');
            return;
        }
        
        // Gmail検索を実行
        searchMatchingProjects(skills);
    });
    
    // Gmailでマッチする案件を検索
    async function searchMatchingProjects(skills) {
        // ローディング表示
        gmailLoading.classList.remove('hidden');
        gmailError.classList.add('hidden');
        gmailResultsBody.innerHTML = '';
        
        // 検索クエリを作成（スキルをOR条件で結合）
        const query = skills.map(skill => `"${skill}"`).join(' OR ');
        
        try {
            // バックエンドAPIを呼び出してGmailを検索
            const response = await fetch('/api/search_gmail', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    maxResults: 10
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Gmailの検索中にエラーが発生しました');
            }
            
            const data = await response.json();
            
            // 結果を表示
            showGmailResults(data.emails || []);
            
        } catch (error) {
            console.error('Error searching Gmail:', error);
            gmailError.textContent = `エラー: ${error.message}`;
            gmailError.classList.remove('hidden');
        } finally {
            gmailLoading.classList.add('hidden');
        }
    }
    
    // Gmailの検索結果を表示
    function showGmailResults(emails) {
        // 結果セクションを表示
        resultSection.classList.add('hidden');
        gmailResultsSection.classList.remove('hidden');
        
        if (emails.length === 0) {
            gmailResultsBody.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    <i class="fas fa-inbox text-4xl mb-2 text-gray-300"></i>
                    <p>該当するメールが見つかりませんでした。</p>
                </div>
            `;
            return;
        }
        
        // メール一覧を表示
        gmailResultsBody.innerHTML = emails.map(email => `
            <div class="email-item" onclick="viewEmail('${email.id}')">
                <div class="flex justify-between items-start">
                    <div class="flex-1 min-w-0">
                        <p class="email-sender">${email.sender || '送信者不明'}</p>
                        <p class="email-subject">${email.subject || '(件名なし)'}</p>
                        <p class="email-snippet">${email.snippet || ''}</p>
                        <p class="email-date">${formatDate(email.date)}</p>
                    </div>
                    <div class="ml-4 flex-shrink-0">
                        <i class="fas fa-chevron-right text-gray-400"></i>
                    </div>
                </div>
            </div>
        `).join('');
        
        // 結果セクションまでスクロール
        gmailResultsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    // 日付をフォーマット
    function formatDate(dateString) {
        if (!dateString) return '';
        
        try {
            const date = new Date(dateString);
            return new Intl.DateTimeFormat('ja-JP', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            }).format(date);
        } catch (e) {
            return dateString;
        }
    }
    
    // 戻るボタン（Gmail結果からスキル一覧に戻る）
    backToSkillsBtn.addEventListener('click', function() {
        gmailResultsSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
    });
    
    // Gmail認証ボタン
    gmailAuthBtn.addEventListener('click', function() {
        // Gmail認証フローを開始
        window.location.href = '/gmail_auth';
    });
    
    // ページ読み込み時に認証状態を確認
    checkGmailAuthStatus();
    
    // Gmail認証状態を確認
    async function checkGmailAuthStatus() {
        try {
            const response = await fetch('/gmail_auth/status');
            const data = await response.json();
            
            if (data.authenticated) {
                // 認証済み
                gmailAuthStatus.textContent = '認証済み';
                gmailAuthStatus.className = 'text-green-600 font-medium';
                gmailAuthContainer.classList.add('hidden');
                gmailSearchContainer.classList.remove('hidden');
                gmailAuthError.classList.add('hidden');
            } else {
                // 未認証
                gmailAuthStatus.textContent = '未認証';
                gmailAuthStatus.className = 'text-red-600 font-medium';
                gmailAuthContainer.classList.remove('hidden');
                gmailSearchContainer.classList.add('hidden');
                
                if (data.error) {
                    gmailAuthError.textContent = data.error;
                    gmailAuthError.classList.remove('hidden');
                }
            }
        } catch (error) {
            console.error('認証状態の確認中にエラーが発生しました:', error);
            gmailAuthError.textContent = '認証状態の確認中にエラーが発生しました';
            gmailAuthError.classList.remove('hidden');
        }
    }
});

// グローバル関数: メールを表示（新しいタブでGmailを開く）
function viewEmail(emailId) {
    window.open(`https://mail.google.com/mail/u/0/#inbox/${emailId}`, '_blank');
}
