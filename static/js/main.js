// グローバル変数
'use strict';

// 動的コード評価を避けるためのヘルパー関数
const safeEval = (code, context = {}) => {
  // 許可された関数のみを実行
  const allowedFunctions = {
    // 必要な関数をここに追加
  };
  
  try {
    // コンテキストをセットアップ
    const sandbox = {
      ...allowedFunctions,
      ...context
    };
    
    // 関数を作成して実行
    const fn = new Function(...Object.keys(sandbox), `return (${code})`);
    return fn(...Object.values(sandbox));
  } catch (error) {
    console.error('Error in safeEval:', error);
    return null;
  }
};

const elements = {
    // ファイルアップロード関連
    dropZone: null,
    fileInput: null,
    fileInfo: null,
    fileName: null,
    uploadBtn: null,
    uploadProgress: null,
    progressBar: null,
    
    // 結果表示関連
    resultSection: null,
    skillsByCategory: null,
    textPreview: null,
    backToUpload: null,
    
    // スキル保存関連
    saveSkillsBtn: null,
    
    // Gmail関連
    findProjectsBtn: null,
    gmailResultsSection: null,
    gmailResultsBody: null,
    backToSkillsBtn: null,
    gmailLoading: null,
    gmailError: null,
    gmailAuthBtn: null,
    gmailAuthStatus: null,
    gmailAuthContainer: null,
    gmailSearchContainer: null,
    gmailAuthError: null
};

// DOM要素を初期化
function initElements() {
    // ファイルアップロード関連
    elements.uploadForm = document.getElementById('uploadForm');
    elements.dropZone = document.getElementById('dropZone');
    elements.fileInput = document.getElementById('fileInput');
    elements.fileInfo = document.getElementById('fileInfo');
    elements.fileName = document.getElementById('fileName');
    elements.uploadBtn = document.getElementById('uploadBtn');
    elements.uploadProgress = document.getElementById('uploadProgress');
    elements.progressBar = document.getElementById('progressBar');
    
    // 結果表示関連
    elements.resultSection = document.getElementById('resultSection');
    elements.skillsByCategory = document.getElementById('skillsByCategory');
    elements.textPreview = document.getElementById('textPreview');
    elements.backToUpload = document.getElementById('backToUpload');
    elements.saveSkillsBtn = document.getElementById('saveSkills');
    
    // Gmail関連
    elements.findProjectsBtn = document.getElementById('findProjectsBtn');
    elements.gmailResultsSection = document.getElementById('gmailResultsSection');
    elements.gmailResultsBody = document.getElementById('gmailResultsBody');
    elements.backToSkillsBtn = document.getElementById('backToSkillsBtn');
    elements.gmailLoading = document.getElementById('gmailLoading');
    elements.gmailError = document.getElementById('gmailError');
    elements.gmailAuthBtn = document.getElementById('gmailAuthBtn');
    elements.gmailAuthStatus = document.getElementById('gmailAuthStatus');
    elements.gmailAuthContainer = document.getElementById('gmailAuthContainer');
    elements.gmailSearchContainer = document.getElementById('gmailSearchContainer');
    elements.gmailAuthError = document.getElementById('gmailAuthError');
}

// ページアンロード時の処理を設定
window.addEventListener('beforeunload', (event) => {
  // 必要なクリーンアップ処理をここに追加
  // 例：保存されていない変更がある場合に確認ダイアログを表示
  // if (hasUnsavedChanges) {
  //   event.preventDefault();
  //   event.returnValue = '保存されていない変更があります。このページを離れますか？';
  //   return '保存されていない変更があります。このページを離れますか？';
  // }
});

// ドラッグ＆ドロップ機能の初期化
function initDragAndDrop() {
    // 必要な要素が存在するか確認
    if (!elements.dropZone || !elements.fileInput) {
        console.warn('必要な要素が見つかりませんでした。');
        return;
    }

    // ドラッグ＆ドロップのイベントを防止
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        if (elements.dropZone) {
            elements.dropZone.addEventListener(eventName, preventDefaults, false);
        }
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // ドラッグ中のスタイル変更
    if (elements.dropZone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            elements.dropZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            elements.dropZone.addEventListener(eventName, unhighlight, false);
        });
    }

    function highlight() {
        if (elements.dropZone) {
            elements.dropZone.classList.add('border-blue-400', 'bg-blue-50');
        }
    }
    
    function unhighlight() {
        if (elements.dropZone) {
            elements.dropZone.classList.remove('border-blue-400', 'bg-blue-50');
        }
    }

    // ファイルがドロップされたとき
    if (elements.dropZone) {
        elements.dropZone.addEventListener('drop', handleDrop, false);
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // ファイルが選択されたとき
    if (elements.fileInput) {
        elements.fileInput.addEventListener('change', function() {
            if (this.files && this.files.length > 0) {
                handleFiles(this.files);
            }
        });
    }

    // ファイルを処理する関数
    function handleFiles(files) {
        if (!files || files.length === 0) return;
        
        const file = files[0];
        if (!file) return;
        
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
        if (elements.fileName) elements.fileName.textContent = file.name;
        if (elements.fileInfo) elements.fileInfo.classList.remove('hidden');
        
        // アップロードボタンにイベントを追加
        if (elements.uploadBtn) {
            elements.uploadBtn.onclick = function() {
                uploadFile(file);
            };
        }
    }
    
    // ファイル選択時のイベントリスナーを追加
    if (elements.fileInput) {
        elements.fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // ファイル名を表示
                if (elements.fileName) elements.fileName.textContent = file.name;
                if (elements.fileInfo) elements.fileInfo.classList.remove('hidden');
            }
        });
    }
    
    // フォームの送信を処理
    if (elements.uploadForm) {
        elements.uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const fileInput = document.getElementById('fileInput');
            if (!fileInput.files || fileInput.files.length === 0) {
                showError('エラー', 'ファイルが選択されていません');
                return;
            }
            
            const file = fileInput.files[0];
            uploadFile(file);
        });
    }
    
        // ファイルをアップロードする関数
    function uploadFile(file) {
        // 初期化
        const formData = new FormData();
        let interval;
        
        try {
            // バリデーション
            if (!file) {
                throw new Error('ファイルが選択されていません');
            }
            
            // ファイルサイズのチェック（10MBまで）
            const maxSize = 10 * 1024 * 1024; // 10MB
            if (file.size > maxSize) {
                throw new Error('ファイルサイズが大きすぎます。10MB以下のファイルをアップロードしてください。');
            }
            
            // フォームデータの準備
            formData.append('file', file);
            
            // UIの更新
            if (elements.uploadProgress) elements.uploadProgress.classList.remove('hidden');
            if (elements.fileInfo) elements.fileInfo.classList.add('hidden');
            
            // プログレスバーのアニメーション
            interval = setInterval(() => {
                const progressBar = elements.progressBar;
                if (progressBar) {
                    const currentWidth = parseInt(progressBar.style.width || '0', 10);
                    const newWidth = Math.min(currentWidth + 5, 90);
                    progressBar.style.width = newWidth + '%';
                    progressBar.textContent = newWidth + '%';
                    
                    if (newWidth >= 90) {
                        clearInterval(interval);
                    }
                }
            }, 100);
            
            // XMLHttpRequestの設定
            const xhr = new XMLHttpRequest();
            
            // 進捗状況を監視
            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    const progressBar = elements.progressBar;
                    if (progressBar) {
                        progressBar.style.width = percentComplete + '%';
                        progressBar.textContent = percentComplete + '%';
                    }
                }
            };
            
            // リクエストの設定
            xhr.open('POST', '/api/upload', true);
            
            // レスポンスハンドリング
            xhr.onload = function() {
                try {
                    clearInterval(interval);
                    
                    if (xhr.status >= 200 && xhr.status < 300) {
                        const data = JSON.parse(xhr.responseText);
                        
                        if (data.status === 'success') {
                            // スキル情報をセッションストレージに保存
                            if (data.skills) {
                                sessionStorage.setItem('extractedSkills', JSON.stringify(data.skills));
                                
                                // スキルを表示
                                if (typeof showResults === 'function') {
                                    showResults(data.skills, data.extracted_text || '');
                                }
                                
                                // 結果セクションを表示
                                if (elements.resultSection) {
                                    elements.resultSection.classList.remove('hidden');
                                    elements.resultSection.scrollIntoView({ behavior: 'smooth' });
                                }
                                
                                // アップロードフォームをリセット
                                if (elements.uploadForm) {
                                    elements.uploadForm.reset();
                                }
                                if (elements.fileInfo) {
                                    elements.fileInfo.classList.add('hidden');
                                }
                            }
                        } else {
                            throw new Error(data.message || 'ファイルの処理中にエラーが発生しました');
                        }
                    } else {
                        const errorData = xhr.responseText ? JSON.parse(xhr.responseText) : {};
                        throw new Error(errorData.message || `サーバーエラーが発生しました (${xhr.status})`);
                    }
                } catch (e) {
                    console.error('Error processing response:', e);
                    showError('エラー', 'サーバーからの応答の処理中にエラーが発生しました', 'もう一度お試しください。');
                }
            };
            
            // エラーハンドリング
            xhr.onerror = function() {
                clearInterval(interval);
                showError('ネットワークエラー', 'ネットワーク接続に問題があります。接続を確認してからもう一度お試しください。', '');
            };
            
            xhr.onabort = function() {
                clearInterval(interval);
                showError('アップロードキャンセル', 'アップロードがキャンセルされました', '');
            };
            
            // リクエスト送信
            xhr.send(formData);
            
        } catch (error) {
            // エラー発生時の処理
            if (interval) clearInterval(interval);
            
            // UIのリセット
            if (elements.uploadProgress) elements.uploadProgress.classList.add('hidden');
            if (elements.fileInfo) elements.fileInfo.classList.remove('hidden');
            if (elements.progressBar) {
                elements.progressBar.style.width = '0%';
                elements.progressBar.textContent = '0%';
            }
            
            // エラーメッセージを表示
            const errorMessage = error && error.message 
                ? error.message 
                : 'ファイルのアップロード中にエラーが発生しました。';
                
            showError('エラーが発生しました', errorMessage, 'もう一度お試しください。');
        }
    }
}

// エラーメッセージを表示する関数
function showError(title, message, resolution = '') {
    // 既存のエラーメッセージを削除
    const existingError = document.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
    
    const errorHtml = `
        <div class="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-exclamation-circle text-red-400 text-xl"></i>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-red-700 font-medium">${title}</p>
                    <p class="text-sm text-red-600">${message}</p>
                    ${resolution ? `<p class="text-sm text-red-600 mt-1">${resolution}</p>` : ''}
                </div>
            </div>
        </div>
    `;
    
    // エラーメッセージを表示
    const container = document.querySelector('.max-w-4xl');
    if (container) {
        container.insertAdjacentHTML('afterbegin', errorHtml);
    }
    
    // エラーメッセージを自動で消去（5秒後）
    setTimeout(() => {
        const errorElement = container.querySelector('.bg-red-50');
        if (errorElement) {
            errorElement.remove();
        }
    }, 5000);
}

// 結果を表示する関数
function showResults(skills, extractedText) {
    if (!elements.skillsByCategory || !elements.resultSection) {
        console.warn('必要な要素が見つかりませんでした。');
        return;
    }
    
    // テキストプレビューを更新
    if (elements.textPreview) {
        elements.textPreview.textContent = extractedText || 'テキストを抽出できませんでした。';
    }
    
    // スキルをカテゴリごとにグループ化
    const categories = {};
    
    // スキルが配列でない場合や空の場合は処理をスキップ
    if (!Array.isArray(skills) || skills.length === 0) {
        console.warn('スキルデータが不正または空です。');
        return;
    }
    
    skills.forEach(skill => {
        if (skill && skill.category_name) {
            if (!categories[skill.category_name]) {
                categories[skill.category_name] = [];
            }
            categories[skill.category_name].push(skill);
        }
    });
    
    // スキルカテゴリを表示
    let skillsHtml = '';
    for (const [category, skillList] of Object.entries(categories)) {
        skillsHtml += `
            <div class="mb-6">
                <h3 class="text-lg font-medium text-gray-900 mb-2">${category}</h3>
                <div class="flex flex-wrap gap-2">
                    ${skillList.map(skill => 
                        `<span class="skill-badge inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 cursor-pointer hover:bg-blue-200 transition-colors">
                            ${skill.skill_name}
                        </span>`
                    ).join('')}
                </div>
            </div>`;
    }
    
    // スキルを表示
    if (elements.skillsByCategory) {
        elements.skillsByCategory.innerHTML = skillsHtml;
    }
    
    // テキストプレビューを設定
    let previewHtml = '';
    if (extractedText) {
        previewHtml = `
            <div class="mt-6">
                <h3 class="text-lg font-medium text-gray-900 mb-2">抽出されたテキスト</h3>
                <div class="bg-gray-50 p-4 rounded-md max-h-60 overflow-y-auto text-sm text-gray-700">
                    ${extractedText.split('\n').map(para => `<p class="mb-2">${para || '&nbsp;'}</p>`).join('')}
                </div>
            </div>`;
    }
    
    // テキストプレビューを表示
    if (elements.textPreview) {
        elements.textPreview.innerHTML = previewHtml;
    }
    
    // 結果セクションを表示
    if (elements.resultSection) {
        elements.resultSection.classList.remove('hidden');
        // 結果セクションまでスクロール
        elements.resultSection.scrollIntoView({ behavior: 'smooth' });
    }
}

// 戻るボタンのイベントリスナーを設定
function setupBackButton() {
    if (!elements.backToUpload) {
        console.warn('戻るボタンが見つかりませんでした。');
        return;
    }
    elements.backToUpload.addEventListener('click', function() {
        if (elements.resultSection) elements.resultSection.classList.add('hidden');
        if (elements.gmailResultsSection) elements.gmailResultsSection.classList.add('hidden');
        
        // ファイルアップロードフォームをリセット
        if (elements.fileInput) elements.fileInput.value = '';
        if (elements.fileInfo) elements.fileInfo.classList.add('hidden');
        if (elements.fileName) elements.fileName.textContent = '';
        if (elements.uploadProgress) elements.uploadProgress.classList.add('hidden');
        if (elements.progressBar) elements.progressBar.style.width = '0%';
        
        // エラーメッセージを削除
        const errorMessages = document.querySelectorAll('.error-message');
        errorMessages.forEach(el => el.remove());
    });
}

// 案件を探すボタンのイベントリスナーを設定
function setupFindProjectsButton() {
    if (!elements.findProjectsBtn) {
        console.warn('案件を探すボタンが見つかりませんでした。');
        return;
    }
    
    elements.findProjectsBtn.addEventListener('click', function() {
        // セッションストレージからスキルを取得
        const extractedSkills = sessionStorage.getItem('extractedSkills');
        if (!extractedSkills) {
            showError('スキルが見つかりません', 'スキルシートをアップロードしてから検索してください。');
            return;
        }
        
        try {
            const skillsData = JSON.parse(extractedSkills);
            let skills = [];
            
            // カテゴリ別のスキルをフラットな配列に変換
            Object.values(skillsData).forEach(category => {
                if (Array.isArray(category)) {
                    category.forEach(skill => {
                        if (typeof skill === 'string') {
                            skills.push(skill);
                        } else if (skill && typeof skill === 'object' && skill.skill_name) {
                            skills.push(skill.skill_name);
                        }
                    });
                }
            });
            
            // 重複を削除
            skills = [...new Set(skills)];
            
            if (skills.length > 0) {
                console.log('検索に使用するスキル:', skills);
                searchMatchingProjects(skills);
            } else {
                showError('スキルが見つかりません', '有効なスキルが見つかりませんでした。');
            }
        } catch (e) {
            console.error('スキルの取得中にエラーが発生しました:', e);
            showError('エラー', 'スキルの取得中にエラーが発生しました。', 'スキルシートを再度アップロードしてください。');
        }
    });
    
    // スキルがクリックされたらそのスキルで検索
    document.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('skill-badge')) {
            const skill = e.target.textContent.trim();
            console.log('スキルをクリック:', skill);
            searchMatchingProjects([skill]);
        }
    });
}

// 日付をフォーマットするヘルパー関数
function formatDate(dateString) {
    if (!dateString) return '日付不明';
    try {
        const date = new Date(dateString);
        return date.toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        console.error('日付のフォーマットに失敗しました:', e);
        return dateString; // パースできない場合はそのまま返す
    }
}

// メール詳細モーダルを表示する関数
function showEmailDetail(emailId) {
    // モーダルを表示
    const modal = document.getElementById('emailModal');
    if (!modal) {
        console.error('メールモーダル要素が見つかりません');
        return;
    }
    
    modal.classList.remove('hidden');
    
    // モーダルの内容をリセット
    document.getElementById('emailSubject').textContent = '読み込み中...';
    document.getElementById('emailFrom').textContent = '';
    document.getElementById('emailDate').textContent = '';
    document.getElementById('emailBody').textContent = '読み込み中...';
    document.getElementById('extractedSkills').innerHTML = '<div class="text-gray-500">スキルを抽出中...</div>';
    document.getElementById('matchedProjects').innerHTML = '<div class="text-gray-500 text-center py-4">マッチする案件を検索中...</div>';
    
    // メールの詳細を取得
    fetch(`/api/emails/${emailId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('メールの取得に失敗しました');
            }
            return response.json();
        })
        .then(data => {
            if (data.status !== 'success') {
                throw new Error(data.message || 'エラーが発生しました');
            }
            
            console.log('メール詳細:', data);
            
            // メール情報を表示
            document.getElementById('emailSubject').textContent = data.email.subject || '(件名なし)';
            document.getElementById('emailFrom').textContent = `差出人: ${data.email.from || '不明'}`;
            document.getElementById('emailDate').textContent = `受信日時: ${formatDate(data.email.date)}`;
            document.getElementById('emailBody').textContent = data.email.body || '本文がありません';
            
            // 抽出されたスキルを表示
            const skillsContainer = document.getElementById('extractedSkills');
            if (data.extracted_skills && data.extracted_skills.length > 0) {
                skillsContainer.innerHTML = data.extracted_skills.map(skill => 
                    `<span class="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded">
                        ${skill}
                    </span>`
                ).join('');
            } else {
                skillsContainer.innerHTML = '<div class="text-gray-500">スキルが見つかりませんでした</div>';
            }
            
            // マッチする案件を表示
            const projectsContainer = document.getElementById('matchedProjects');
            if (data.matched_projects && data.matched_projects.length > 0) {
                projectsContainer.innerHTML = data.matched_projects.map(project => {
                    const skills = project.required_skills_list ? 
                        project.required_skills_list.split(',').map(skill => 
                            `<span class="inline-block bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded mr-1 mb-1">
                                ${skill.trim()}
                            </span>`
                        ).join('') : '';
                    
                    return `
                        <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                            <div class="flex justify-between items-start mb-2">
                                <h4 class="font-semibold text-lg">${project.name || '無題の案件'}</h4>
                                <span class="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded">
                                    ${project.work_type || 'その他'}
                                </span>
                            </div>
                            <p class="text-gray-600 text-sm mb-3">${project.description || '説明はありません'}</p>
                            <div class="flex flex-wrap gap-1 mb-3">
                                ${skills}
                            </div>
                            <div class="flex justify-between items-center text-sm">
                                <span class="text-gray-500">${project.location || '場所未指定'}</span>
                                <span class="font-semibold">
                                    ${project.min_budget ? `¥${Number(project.min_budget).toLocaleString()}〜` : ''}
                                    ${project.max_budget ? `¥${Number(project.max_budget).toLocaleString()}` : ''}
                                    ${!project.min_budget && !project.max_budget ? '要相談' : ''}
                                </span>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                projectsContainer.innerHTML = `
                    <div class="text-center py-6">
                        <i class="fas fa-inbox text-4xl text-gray-300 mb-2"></i>
                        <p class="text-gray-500">マッチする案件が見つかりませんでした</p>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('emailBody').innerHTML = `
                <div class="bg-red-50 text-red-700 p-4 rounded">
                    <p class="font-semibold">エラーが発生しました</p>
                    <p>${error.message || '詳細情報の取得中に問題が発生しました。後でもう一度お試しください。'}</p>
                </div>
            `;
            document.getElementById('extractedSkills').innerHTML = '';
            document.getElementById('matchedProjects').innerHTML = '';
        });
    
    // モーダルを閉じるイベントリスナーを追加
    const closeModal = () => {
        modal.classList.add('hidden');
        document.removeEventListener('keydown', handleEscape);
    };
    
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    };
    
    // 既存のイベントリスナーを削除してから追加
    const closeButton = document.getElementById('closeEmailModal');
    const closeModalBtn = document.getElementById('closeModalBtn');
    
    // 古いイベントリスナーを削除
    closeButton.replaceWith(closeButton.cloneNode(true));
    closeModalBtn.replaceWith(closeModalBtn.cloneNode(true));
    
    // 新しいイベントリスナーを追加
    document.getElementById('closeEmailModal').onclick = closeModal;
    document.getElementById('closeModalBtn').onclick = closeModal;
    document.addEventListener('keydown', handleEscape);
    
    // モーダル外をクリックで閉じる
    modal.onclick = (e) => {
        if (e.target === modal) {
            closeModal();
        }
    };
}

// スキルに基づいてマッチング案件を検索する関数
async function searchMatchingProjects(skills) {
    console.log('searchMatchingProjects を開始します', { skills });
    
    // ローディング表示
    const resultsContainer = document.getElementById('matchingProjects');
    if (resultsContainer) {
        resultsContainer.innerHTML = `
            <div class="flex justify-center items-center p-8">
                <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
                <span class="ml-4 text-gray-600">案件を検索中...</span>
            </div>`;
        resultsContainer.classList.remove('hidden');
    }
    
    try {
        console.log('Gmailからメールを検索します', { skills });
        
        // 現在の日付と2日前の日付を取得
        const now = new Date();
        const twoDaysAgo = new Date(now);
        twoDaysAgo.setDate(now.getDate() - 2);
        
        // 日付をYYYY/MM/DD形式にフォーマット
        const formatDate = (date) => {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}/${month}/${day}`;
        };
        
        const dateQuery = `after:${formatDate(twoDaysAgo)}`;
        const searchQuery = `to:sales@artwize.co.jp ${dateQuery} ${skills.join(' OR ')}`;
        
        console.log('検索クエリ:', searchQuery);
        
        // Gmailを検索
        const response = await fetch('/search_gmail', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: searchQuery,
                maxResults: 10
            })
        });
        
        console.log('APIレスポンスを受信しました', { status: response.status });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.message || 'Gmailの検索中にエラーが発生しました';
            console.error('APIエラー:', { status: response.status, errorData });
            throw new Error(errorMsg);
        }
        
        const data = await response.json();
        console.log('Gmail検索結果:', data);
        
        if (data.status === 'success' && data.emails && data.emails.length > 0) {
            // メールを案件形式に変換
            const projects = data.emails.map(email => ({
                id: email.id,
                name: email.subject,
                client_name: email.from,
                date: email.date,
                snippet: email.snippet,
                source: 'gmail',
                matched_skills: skills.filter(skill => 
                    email.snippet.toLowerCase().includes(skill.toLowerCase()) ||
                    email.subject.toLowerCase().includes(skill.toLowerCase())
                ),
                match_count: 0, // 後で計算
                match_percentage: 0 // 後で計算
            }));
            
            // マッチ率を計算
            projects.forEach(project => {
                project.match_count = project.matched_skills.length;
                project.match_percentage = Math.min(project.match_count * 20, 100); // 1スキルあたり最大20%
            });
            
            // マッチ率でソート
            projects.sort((a, b) => b.match_percentage - a.match_percentage);
            
            console.log('案件を表示します', { count: projects.length });
            displayProjects(projects, skills);
        } else {
            console.log('該当するメールは見つかりませんでした');
            if (resultsContainer) {
                resultsContainer.innerHTML = `
                    <div class="text-center py-12">
                        <i class="fas fa-inbox text-4xl text-gray-300 mb-3"></i>
                        <p class="text-gray-500">該当する案件が見つかりませんでした</p>
                        <p class="text-sm text-gray-400 mt-2">検索条件を変更してお試しください</p>
                    </div>`;
            }
        }
    } catch (error) {
        console.error('案件検索中にエラーが発生しました:', {
            error,
            message: error.message,
            stack: error.stack
        });
        
        const errorMessage = error.message || '案件の検索中にエラーが発生しました';
        showError('検索エラー', errorMessage);
        
        if (resultsContainer) {
            resultsContainer.innerHTML = `
                <div class="p-4 bg-red-50 text-red-700 rounded">
                    <p class="font-semibold">エラーが発生しました</p>
                    <p class="text-sm mt-1">${errorMessage}</p>
                    <p class="text-xs mt-2">コンソールに詳細なエラー情報を表示しています</p>
                </div>`;
        }
    } finally {
        console.log('searchMatchingProjects を終了します');
    }
}

// Gmailを開く関数
function openGmailWithProject(project) {
    if (!project) {
        console.error('プロジェクト情報が無効です');
        return;
    }
    
    // GmailのメールIDが直接ある場合は、そのメールを開く
    if (project.id && project.source === 'gmail') {
        const gmailUrl = `https://mail.google.com/mail/u/0/#inbox/${project.id}`;
        console.log('Gmailを開きます:', gmailUrl);
        window.open(gmailUrl, '_blank');
        return;
    }
    
    // 通常のプロジェクトの場合は、検索クエリを作成
    let searchQuery = 'to:sales@artwize.co.jp ';
    
    if (project.name) {
        searchQuery += `subject:"${project.name}" `;
    }
    
    if (project.client_name) {
        searchQuery += `from:"${project.client_name}" `;
    }
    
    if (project.location) {
        searchQuery += `"${project.location}"`;
    }
    
    // Gmailの検索URLを作成
    const gmailSearchUrl = `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(searchQuery.trim())}`;
    
    console.log('Gmail検索を開きます:', gmailSearchUrl);
    window.open(gmailSearchUrl, '_blank');
}

// 案件を表示する関数
function displayProjects(projects, searchSkills = []) {
    console.log('displayProjects を開始します', { projects, searchSkills });
    
    const resultsContainer = document.getElementById('matchingProjects');
    if (!resultsContainer) {
        console.error('結果を表示するコンテナが見つかりません');
        return;
    }
    
    // 検索に使用されたスキルを表示
    const searchSkillsHtml = searchSkills.length > 0 
        ? `<div class="mb-4">
              <span class="text-sm text-gray-600">検索スキル: </span>
              ${searchSkills.map(skill => 
                  `<span class="inline-block bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded mr-1 mb-1">
                      ${skill}
                  </span>`
              ).join('')}
          </div>`
        : '';
        
    // プロジェクトカードのテンプレート
    const projectCardTemplate = (project, index) => {
        const isGmailProject = project.source === 'gmail';
        const matchPercentage = project.match_percentage || 0;
        const matchColor = matchPercentage >= 70 ? 'bg-green-100 text-green-800' : 
                          matchPercentage >= 40 ? 'bg-yellow-100 text-yellow-800' : 
                          'bg-red-100 text-red-800';
        
        // Gmailのメールかどうかで表示を分岐
        if (isGmailProject) {
            return `
                <div class="bg-white rounded-lg shadow-md overflow-hidden border border-gray-200 hover:shadow-lg transition-shadow mb-6">
                    <div class="p-6">
                        <div class="flex justify-between items-start mb-2">
                            <h3 class="text-lg font-semibold text-gray-900">${project.name || '件名なし'}</h3>
                            <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${matchColor}">
                                ${matchPercentage}% マッチ
                            </span>
                        </div>
                        
                        ${project.client_name ? `
                            <p class="text-gray-600 mb-2">
                                <i class="fas fa-user-tie mr-2 text-blue-500"></i>
                                ${project.client_name}
                            </p>
                        ` : ''}
                        
                        ${project.date ? `
                            <p class="text-gray-500 text-sm mb-4">
                                <i class="far fa-calendar-alt mr-2"></i>
                                ${formatDate(project.date)}
                            </p>
                        ` : ''}
                        
                        ${project.snippet ? `
                            <p class="text-gray-700 mb-4 line-clamp-3">${project.snippet}</p>
                        ` : ''}
                        
                        ${project.matched_skills && project.matched_skills.length > 0 ? `
                            <div class="mb-4">
                                <p class="text-sm font-medium text-gray-700 mb-2">マッチしたスキル:</p>
                                <div class="flex flex-wrap gap-2">
                                    ${project.matched_skills.map(skill => `
                                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                            ${skill}
                                        </span>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}
                        
                        <div class="flex justify-end space-x-3 mt-4">
                            <button onclick="event.stopPropagation(); openGmailWithProject(${JSON.stringify(project).replace(/"/g, '&quot;')})" 
                                    class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                                <i class="fas fa-envelope mr-2"></i>
                                Gmailで確認
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // 通常の案件カード
        const skills = project.required_skills_list 
            ? project.required_skills_list.split(',').map(skill => 
                `<span class="inline-block bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded mr-1 mb-1">
                    ${skill.trim()}
                </span>`
            ).join('') 
            : '';
            
        const matchedSkills = project.matched_skills || [];
        
        return `
            <div class="bg-white rounded-lg shadow-md overflow-hidden border border-gray-200 hover:shadow-lg transition-shadow cursor-pointer" 
                 onclick="event.stopPropagation(); openGmailWithProject(${JSON.stringify(project).replace(/"/g, '&quot;')})">
                <div class="p-6">
                    <div class="flex justify-between items-start mb-2">
                        <h3 class="text-xl font-semibold text-gray-800">${project.name || '無題の案件'}</h3>
                        <span class="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded">
                            ${project.work_type || 'その他'}
                        </span>
                    </div>
                    
                    <p class="text-gray-600 mb-4">${project.description || '説明はありません'}</p>
                    
                    <div class="mb-4">
                        <h4 class="text-sm font-medium text-gray-700 mb-1">必須スキル:</h4>
                        <div class="flex flex-wrap">
                            ${skills || '<span class="text-gray-500 text-sm">スキルが指定されていません</span>'}
                        </div>
                    </div>
                    
                    ${matchedSkills.length > 0 ? `
                        <div class="mb-4">
                            <h4 class="text-sm font-medium text-green-700 mb-1">マッチしたスキル (${matchedSkills.length}件):</h4>
                            <div class="flex flex-wrap">
                                ${matchedSkills.map(skill => 
                                    `<span class="inline-block bg-green-100 text-green-800 text-xs font-medium px-2 py-0.5 rounded mr-1 mb-1">
                                        ${skill}
                                    </span>`
                                ).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    <div class="flex justify-between items-center text-sm mt-4 pt-4 border-t border-gray-100">
                        <div>
                            <span class="text-gray-500">${project.location || '場所未指定'}</span>
                            <span class="mx-2 text-gray-300">|</span>
                            <span class="font-semibold">
                                ${project.min_budget ? `¥${Number(project.min_budget).toLocaleString()}〜` : ''}
                                ${project.max_budget ? `¥${Number(project.max_budget).toLocaleString()}` : ''}
                                ${!project.min_budget && !project.max_budget ? '要相談' : ''}
                            </span>
                        </div>
                        
                        <button class="gmail-button inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md" 
                                onclick="event.stopPropagation(); openGmailWithProject(${JSON.stringify(project).replace(/"/g, '&quot;')});">
                            Gmailで問い合わせる
                        </button>
                    </div>
                </div>
            </div>
        `;
    };
    
    if (!projects || projects.length === 0) {
        console.log('表示する案件がありません');
        resultsContainer.innerHTML = `
            <div class="text-center py-12">
                <i class="fas fa-inbox text-4xl text-gray-300 mb-3"></i>
                <p class="text-gray-500">マッチする案件が見つかりませんでした</p>
                <p class="text-sm text-gray-400 mt-2">検索条件を変更してお試しください</p>
            </div>
        `;
        return;
    }
    
    // 検索スキルを表示
    if (searchSkillsHtml) {
        resultsContainer.innerHTML = searchSkillsHtml;
    } else {
        resultsContainer.innerHTML = '';
    }
    
    // プロジェクトカードを追加
    const projectsGrid = document.createElement('div');
    projectsGrid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6';
    
    projects.forEach((project, index) => {
        const projectCard = document.createElement('div');
        projectCard.innerHTML = projectCardTemplate(project, index);
        projectsGrid.appendChild(projectCard.firstElementChild);
    });
    
    resultsContainer.appendChild(projectsGrid);
    
    // 検索結果セクションを表示してスクロール
    const resultsSection = document.getElementById('matchingProjectsSection');
    if (resultsSection) {
        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
}

// Gmailでマッチする案件を検索し、最初のメールに直接遷移
async function searchMatchingProjectsInGmail(skills) {
    if (!Array.isArray(skills) || skills.length === 0) {
        console.warn('スキルデータが不正または空です。');
        return;
    }
    
    // 検索クエリを作成
    const searchQuery = `to:sales@artwize.co.jp ${skills.map(skill => `(${skill})`).join(' OR ')}`;
    
    try {
        // メールを検索
        const searchResponse = await fetch('/search_gmail', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: searchQuery,
                maxResults: 1 // 最初の1件のみ取得
            })
        });
        
        if (!searchResponse.ok) {
            const errorData = await searchResponse.json().catch(() => ({}));
            throw new Error(errorData.message || 'メールの検索中にエラーが発生しました');
        }
        
        const data = await searchResponse.json();
        const emails = Array.isArray(data.messages) ? data.messages : [];
        
        if (emails.length > 0) {
            // 最初のメールを表示
            const emailId = emails[0].id;
            if (emailId) {
                // Gmailのメール詳細ページに直接遷移
                window.open(`https://mail.google.com/mail/u/0/#inbox/${emailId}`, '_blank');
                return;
            }
        }
        
        // メールが見つからない場合はエラーメッセージを表示
        showError('情報', '該当するメールが見つかりませんでした', 'Gmailで直接検索しますか？', () => {
            // Gmailの検索画面を開く
            window.open(`https://mail.google.com/mail/u/0/#search/${encodeURIComponent(searchQuery)}`, '_blank');
        });
        
    } catch (error) {
        console.error('Error searching Gmail:', error);
        // エラーが発生した場合はGmailの検索画面を開く
        window.open(`https://mail.google.com/mail/u/0/#search/${encodeURIComponent(searchQuery)}`, '_blank');
    }
}

// グローバル関数: メールを表示（新しいタブでGmailを開く）
function viewEmail(emailId) {
    if (emailId) {
        window.open(`https://mail.google.com/mail/u/0/#inbox/${emailId}`, '_blank');
    }
}

// スキルを保存する関数
function saveSkills() {
    console.log('スキル保存処理を開始します');
    const extractedSkills = sessionStorage.getItem('extractedSkills');
    console.log('セッションストレージから取得したスキル:', extractedSkills);
    
    if (!extractedSkills) {
        console.error('保存するスキルが見つかりません');
        showError('エラー', '保存するスキルが見つかりません。', 'スキルシートを再度アップロードしてください。');
        return;
    }
    
    let skills;
    try {
        skills = JSON.parse(extractedSkills);
        console.log('パースされたスキル:', skills);
    } catch (e) {
        console.error('スキルのパースに失敗しました:', e);
        showError('エラー', 'スキルデータの形式が正しくありません。', 'スキルシートを再度アップロードしてください。');
        return;
    }
    
    const engineerId = document.getElementById('engineerId')?.value || '1';
    console.log('エンジニアID:', engineerId);
    
    // ローディング表示
    const saveBtn = elements.saveSkillsBtn;
    if (!saveBtn) {
        console.error('保存ボタンが見つかりません');
        return;
    }
    
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>保存中...';
    console.log('保存ボタンを無効化しました');
    
    // スキルをスキル名の配列に変換
    console.log('スキルを変換します:', skills);
    let skillNames = [];
    
    try {
        // カテゴリ別のスキルをフラットな配列に変換
        Object.values(skills).forEach(category => {
            if (Array.isArray(category)) {
                category.forEach(skill => {
                    if (typeof skill === 'string') {
                        skillNames.push(skill);
                    } else if (skill && typeof skill === 'object' && skill.skill_name) {
                        skillNames.push(skill.skill_name);
                    }
                });
            }
        });
        
        // 重複を削除
        skillNames = [...new Set(skillNames)];
        
        console.log('変換後のスキル名:', skillNames);
    } catch (e) {
        console.error('スキルの変換中にエラーが発生しました:', e);
        showError('エラー', 'スキルデータの変換中にエラーが発生しました。', 'スキルシートを再度アップロードしてください。');
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
        return;
    }
    
    // スキルをサーバーに送信
    console.log('APIリクエストを送信します:', {
        engineerId: engineerId,
        skills: skillNames
    });
    
    fetch('/api/save_skills', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            engineerId: engineerId,
            skills: skillNames
        })
    })
    .then(response => {
        console.log('APIレスポンスを受信しました。ステータスコード:', response.status);
        if (!response.ok) {
            console.error('APIエラーレスポンス:', response.status, response.statusText);
            return response.text().then(text => {
                console.error('エラーレスポンス本文:', text);
                throw new Error(`APIリクエストが失敗しました: ${response.status} ${response.statusText}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('APIレスポンスデータ:', data);
        if (data.status === 'success') {
            console.log('スキルが正常に保存されました');
            // 成功メッセージを表示
            showError('成功', 'スキルが正常に保存されました。', '案件検索に進んでください。');
            // エラーメッセージを緑色に変更
            const errorMessage = document.getElementById('errorMessage');
            if (errorMessage) {
                errorMessage.classList.remove('bg-red-50', 'border-red-400', 'text-red-700');
                errorMessage.classList.add('bg-green-50', 'border-green-400', 'text-green-700');
                
                const errorIcon = document.getElementById('errorIcon');
                if (errorIcon) {
                    errorIcon.classList.remove('text-red-400', 'fa-exclamation-circle');
                    errorIcon.classList.add('text-green-400', 'fa-check-circle');
                }
            }
        } else {
            console.error('APIレスポンスが成功ではありません:', data);
            throw new Error(data.message || 'スキルの保存に失敗しました。');
        }
    })
    .catch(error => {
        console.error('スキル保存中にエラーが発生しました:', error);
        showError('エラー', 'スキルの保存中にエラーが発生しました。', error.message || '後でもう一度お試しください。');
    })
    .finally(() => {
        console.log('保存処理を終了します');
        // ボタンの状態をリセット
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
            console.log('保存ボタンの状態をリセットしました');
        }
    });
}

// 初期化関数
function initializeApp() {
    // DOM要素を初期化
    initElements();
    
    // ドラッグ＆ドロップの初期化
    initDragAndDrop();
    
    // 各種ボタンのイベントリスナーを設定
    setupBackButton();
    setupFindProjectsButton();
    
    // スキル保存ボタンのイベントリスナーを設定
    if (elements.saveSkillsBtn) {
        elements.saveSkillsBtn.addEventListener('click', saveSkills);
    }
    
    // Gmail認証状態を確認
    if (typeof checkGmailAuthStatus === 'function') {
        checkGmailAuthStatus();
    }
}

// メール詳細ボタンのクリックイベントを委譲
document.addEventListener('click', function(event) {
    // 詳細ボタンまたはその子要素がクリックされたか確認
    const detailButton = event.target.closest('.view-detail-button, .view-detail-button *');
    if (!detailButton) return;  // 詳細ボタンでない場合は処理をスキップ
    if (detailButton) {
        event.preventDefault();
        const emailId = detailButton.closest('[data-email-id]')?.dataset.emailId;
        if (emailId) {
            showEmailDetail(emailId);
        }
    }
});

// DOMの読み込みが完了したら初期化を実行
document.addEventListener('DOMContentLoaded', initializeApp);

// グローバルスコープに公開
window.initDragAndDrop = initDragAndDrop;
window.viewEmail = viewEmail;
