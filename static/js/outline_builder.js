let projectId = null;
let messages = [];
let confirmCallback = null;

let currentVersionId = null;

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    const params = new URLSearchParams(window.location.search);
    projectId = params.get('project_id');
    currentVersionId = params.get('version_id');
    
    if (projectId) {
        loadProjectInfo();
        loadOutlineVersions();
    }

    document.getElementById('outline-content').addEventListener('input', function() {
        updateButtons();
    });

    document.getElementById('send-message').addEventListener('click', sendMessage);
    document.getElementById('chat-input').addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    const versionSelect = document.getElementById('version-select');
    let ignoreNextBlur = false;
    
    versionSelect.addEventListener('focus', function() {
        Array.from(this.options).forEach(option => {
            if (option.dataset.originalText) {
                option.text = option.dataset.originalText;
            }
        });
    });
    
    versionSelect.addEventListener('change', function() {
        const versionId = this.value;
        if (versionId) {
            loadOutlineVersion(versionId);
            ignoreNextBlur = true;
        }
    });
    
    versionSelect.addEventListener('blur', function() {
        if (ignoreNextBlur) {
            ignoreNextBlur = false;
            return;
        }
        const selectedOption = this.options[this.selectedIndex];
        if (selectedOption && selectedOption.dataset.originalText) {
            selectedOption.text = `当前版本 ${selectedOption.dataset.originalText}`;
        }
    });
});

async function checkAuth() {
    try {
        const response = await fetch('/api/auth/user/', {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (!data.success) {
            window.location.href = 'login.html';
        }
    } catch (error) {
        window.location.href = 'login.html';
    }
}

async function loadProjectInfo() {
    try {
        const response = await fetch(`/api/projects/${projectId}/`, {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success) {
            document.getElementById('project-title').textContent = data.project.title;
        }
    } catch (error) {
        console.error('Failed to load project:', error);
    }
}

async function loadOutlineVersions() {
    try {
        const response = await fetch(`/api/projects/${projectId}/outline/versions/`, {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success) {
            const select = document.getElementById('version-select');
            select.innerHTML = '<option value="">选择版本...</option>';
            
            let finalizedVersion = null;
            let latestVersion = null;
            
            data.versions.forEach(version => {
                const option = document.createElement('option');
                option.value = version.id;
                const text = `v${version.version_number}${version.is_finalized ? ' (定稿)' : ''}`;
                option.textContent = text;
                option.dataset.originalText = text;
                select.appendChild(option);
                
                if (version.is_finalized) {
                    finalizedVersion = version;
                }
                if (!latestVersion || version.version_number > latestVersion.version_number) {
                    latestVersion = version;
                }
            });
            
            if (currentVersionId) {
                select.value = currentVersionId;
                const option = select.querySelector(`option[value="${currentVersionId}"]`);
                if (option) {
                    option.text = `当前版本 ${option.dataset.originalText}`;
                }
                loadOutlineVersion(currentVersionId);
            } else if (finalizedVersion) {
                select.value = finalizedVersion.id;
                const option = select.querySelector(`option[value="${finalizedVersion.id}"]`);
                if (option) {
                    option.text = `当前版本 ${option.dataset.originalText}`;
                }
                loadOutlineVersion(finalizedVersion.id);
            } else if (latestVersion) {
                select.value = latestVersion.id;
                const option = select.querySelector(`option[value="${latestVersion.id}"]`);
                if (option) {
                    option.text = `当前版本 ${option.dataset.originalText}`;
                }
                loadOutlineVersion(latestVersion.id);
            }
        }
    } catch (error) {
        console.error('Failed to load outline versions:', error);
    }
}

async function loadLatestOutline() {
    try {
        const response = await fetch(`/api/projects/${projectId}/outline/latest/`, {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success && data.outline) {
            document.getElementById('outline-content').value = data.outline.content;
            document.getElementById('outline-preview').innerHTML = marked.parse(data.outline.content || '');
            if (data.outline.version_number !== undefined) {
                document.getElementById('outline-version').textContent = `v${data.outline.version_number}`;
            }
            updateButtons();
        } else {
            document.getElementById('outline-preview').innerHTML = '<div class="text-center py-8 text-muted"><i class="fas fa-file-text text-4xl mb-4"></i><p>暂无大纲内容</p></div>';
        }
    } catch (error) {
        console.error('Failed to load latest outline:', error);
    }
}

async function loadOutlineVersion(versionId) {
    currentVersionId = versionId;
    
    try {
        const response = await fetch(`/api/outline/version/${versionId}/`, {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        console.log('Loaded outline version:', data);
        
        if (data.success) {
            const content = data.content || '';
            console.log('Outline content length:', content.length);
            
            document.getElementById('outline-content').value = content;
            document.getElementById('outline-preview').innerHTML = content ? marked.parse(content) : '<div class="text-center py-8 text-muted"><i class="fas fa-file-text text-4xl mb-4"></i><p>暂无大纲内容</p></div>';
            
            if (data.version_number !== undefined) {
                document.getElementById('outline-version').textContent = `v${data.version_number}`;
            }
            
            const select = document.getElementById('version-select');
            const selectedOption = select.querySelector(`option[value="${versionId}"]`);
            if (selectedOption) {
                select.options[select.selectedIndex].text = `当前版本 v${data.version_number}${data.is_finalized ? ' (定稿)' : ''}`;
            }
            
            updateButtons();
        } else {
            console.log('No outline data found');
            document.getElementById('outline-preview').innerHTML = '<div class="text-center py-8 text-muted"><i class="fas fa-file-text text-4xl mb-4"></i><p>暂无大纲内容</p></div>';
        }
    } catch (error) {
        console.error('Failed to load outline version:', error);
    }
}

function updateButtons() {
    const content = document.getElementById('outline-content').value;
    const hasContent = content.trim() !== '';
    document.getElementById('save-btn').disabled = !hasContent;
    document.getElementById('finalize-btn').disabled = !hasContent;
}

function showEditMode() {
    document.getElementById('outline-content').classList.remove('d-none');
    document.getElementById('outline-preview').classList.add('d-none');
    document.getElementById('btn-edit').classList.add('active');
    document.getElementById('btn-preview').classList.remove('active');
}

function showPreviewMode() {
    const content = document.getElementById('outline-content').value;
    document.getElementById('outline-preview').innerHTML = marked.parse(content || '');
    document.getElementById('outline-content').classList.add('d-none');
    document.getElementById('outline-preview').classList.remove('d-none');
    document.getElementById('btn-preview').classList.add('active');
    document.getElementById('btn-edit').classList.remove('active');
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    input.disabled = true;
    document.getElementById('send-message').disabled = true;

    const chatMessages = document.getElementById('chat-messages');
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-message user';
    userDiv.innerHTML = `
        <div class="chat-bubble chat-bubble-user">${escapeHtml(message).replace(/\n/g, '<br>')}</div>
        <div class="chat-message-avatar avatar-me ms-2">ME</div>
    `;
    chatMessages.appendChild(userDiv);

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-message assistant';
    loadingDiv.innerHTML = `
        <div class="chat-message-avatar avatar-ai me-2">AI</div>
        <div class="chat-bubble chat-bubble-assistant">
            <i class="fas fa-spinner fa-spin"></i> 思考中...
        </div>
    `;
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    messages.push({ role: 'user', content: message });
    input.value = '';

    try {
        const response = await fetch('/api/ai/chat/outline/stream/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: `project_id=${projectId}&message=${encodeURIComponent(message)}&current_outline=${encodeURIComponent(document.getElementById('outline-content').value)}&messages=${encodeURIComponent(JSON.stringify(messages))}`
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let result = '';
        let responseDiv = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        result += data.chunk;

                        if (!responseDiv) {
                            responseDiv = document.createElement('div');
                            responseDiv.className = 'chat-message assistant';
                            chatMessages.appendChild(responseDiv);
                            loadingDiv.remove();
                        }

                        responseDiv.innerHTML = `
                            <div class="chat-message-avatar avatar-ai me-2">AI</div>
                            <div class="chat-bubble chat-bubble-assistant">${escapeHtml(result).replace(/\n/g, '<br>')}</div>
                        `;
                        chatMessages.scrollTop = chatMessages.scrollHeight;

                        document.getElementById('outline-content').value = result;
                        updateButtons();
                    } catch (e) {}
                }
            }
        }

        messages.push({ role: 'assistant', content: result });

    } catch (error) {
        console.error('Error:', error);
    }

    input.disabled = false;
    document.getElementById('send-message').disabled = false;
}

function openSaveModal() {
    document.getElementById('saveModal').classList.add('show');
}

function closeSaveModal() {
    document.getElementById('saveModal').classList.remove('show');
}

async function saveVersion(isNewVersion) {
    closeSaveModal();
    
    const content = document.getElementById('outline-content').value;
    
    try {
        const response = await fetch('/api/ai/save/outline/version/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: `project_id=${projectId}&content=${encodeURIComponent(content)}&messages=${encodeURIComponent(JSON.stringify(messages))}` + (isNewVersion ? '&new_version=true' : '')
        });
        
        const data = await response.json();
        if (data.success) {
            showConfirmModal('保存成功', `v${data.version_number} 已保存`, function() {
                window.location.href = `project.html?id=${projectId}`;
            });
        } else {
            showConfirmModal('保存失败', data.message || '保存失败');
        }
    } catch (error) {
        showConfirmModal('保存失败', '网络错误，请重试');
    }
}

function confirmFinalize() {
    showConfirmModal('确认定稿', '确定要定稿这个大纲吗？定稿后可以继续创建新版本，但此版本将被锁定，且之前的定稿版本将被取消。', function() {
        finalizeOutline();
    });
}

async function finalizeOutline() {
    try {
        const response = await fetch('/api/outline/finalize/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: `project_id=${projectId}${currentVersionId ? `&version_id=${currentVersionId}` : ''}`
        });
        
        const data = await response.json();
        if (data.success) {
            showConfirmModal('定稿成功', '大纲已定稿', function() {
                window.location.href = `project.html?id=${projectId}`;
            });
        } else {
            showConfirmModal('定稿失败', data.message || '定稿失败');
        }
    } catch (error) {
        showConfirmModal('定稿失败', '网络错误，请重试');
    }
}

function showConfirmModal(title, message, callback) {
    document.getElementById('confirmModalTitle').textContent = title;
    document.getElementById('confirmModalMessage').textContent = message;
    confirmCallback = callback;
    document.getElementById('confirmModal').classList.add('show');
}

function closeConfirmModal() {
    document.getElementById('confirmModal').classList.remove('show');
    confirmCallback = null;
}

function confirmAction() {
    const callback = confirmCallback;
    closeConfirmModal();
    if (callback) callback();
}

function goBack() {
    window.location.href = `project.html?id=${projectId}`;
}

async function logout() {
    try {
        await fetch('/api/auth/logout/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        window.location.href = 'login.html';
    } catch (error) {
        window.location.href = 'login.html';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}