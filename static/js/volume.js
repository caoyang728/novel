let projectId = null;
let currentVolumes = [];
let currentVolumeVersionId = null;
let selectedOutlineVersionId = null;
let selectedVolumeIndex = null;
let modalAction = null;

document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    projectId = urlParams.get('project_id');
    
    if (projectId) {
        loadProjectInfo();
        loadOutlineVersions();
        loadVolumeVersions();
    }

    document.getElementById('outline-select').addEventListener('change', function() {
        selectedOutlineVersionId = this.value;
        document.getElementById('generate-btn').disabled = !selectedOutlineVersionId;
    });

    document.getElementById('volume-version-select').addEventListener('change', function() {
        const versionId = this.value;
        if (versionId) {
            loadVolumeVersion(versionId);
        }
    });

    document.getElementById('chat-input').addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    const chatInput = document.getElementById('chat-input');
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 160) + 'px';
    });
});

async function loadProjectInfo() {
    const data = await api.get(`/api/projects/${projectId}/`);
    if (data.success) {
        document.getElementById('project-title').textContent = data.project.title;
    }
}

async function loadOutlineVersions() {
    const data = await api.get(`/api/projects/${projectId}/outline/versions/`);
    if (data.success) {
        const select = document.getElementById('outline-select');
        select.innerHTML = '<option value="">请选择大纲版本</option>';
        
        let finalizedVersion = null;
        data.versions.forEach(v => {
            const option = document.createElement('option');
            option.value = v.id;
            option.textContent = v.is_finalized 
                ? `v${v.version_number} (定稿)` 
                : `v${v.version_number}`;
            select.appendChild(option);
            if (v.is_finalized) finalizedVersion = v;
        });
        
        if (finalizedVersion) {
            select.value = finalizedVersion.id;
            selectedOutlineVersionId = finalizedVersion.id;
            document.getElementById('generate-btn').disabled = false;
        }
    }
}

async function loadVolumeVersions() {
    const data = await api.get(`/api/projects/${projectId}/volume-versions/`);
    if (data.success) {
        const select = document.getElementById('volume-version-select');
        select.innerHTML = '<option value="">请选择卷版本</option>';
        
        data.versions.forEach(v => {
            const option = document.createElement('option');
            option.value = v.id;
            option.textContent = v.is_finalized 
                ? `v${v.version_number} (定稿)` 
                : `v${v.version_number}`;
            select.appendChild(option);
        });

        if (data.versions && data.versions.length > 0) {
            let defaultVersion = data.versions.find(v => v.is_finalized);
            if (!defaultVersion) {
                defaultVersion = data.versions[0];
            }
            if (defaultVersion) {
                loadVolumeVersion(defaultVersion.id);
            }
        }
    }
}

async function loadVolumeVersion(versionId) {
    currentVolumeVersionId = versionId;
    const data = await api.get(`/api/volume/version/${versionId}/`);
    if (data.success) {
        currentVolumes = data.volumes;
        renderVolumes(data.volumes);
        selectedVolumeIndex = null;
        renderVolumeDetail(null);
        
        document.getElementById('volume-version-select').value = versionId;

        if (data.outline_version_id) {
            document.getElementById('outline-select').value = data.outline_version_id;
            selectedOutlineVersionId = data.outline_version_id;
        }

        document.getElementById('save-btn').disabled = false;
        document.getElementById('finalize-btn').disabled = data.is_finalized;
    }
}

async function generateVolumes() {
    const outlineVersionId = document.getElementById('outline-select').value;
    if (!outlineVersionId) {
        showToast('请先选择大纲版本', 'error');
        return;
    }

    addMessage('assistant', '正在根据大纲内容生成卷结构，请稍候...');
    document.getElementById('generate-btn').disabled = true;
    
    try {
        const data = await api.postForm('/api/volume/generate/', `project_id=${projectId}&outline_version_id=${outlineVersionId}`);
        if (data.success) {
            currentVolumes = data.volumes;
            renderVolumes(data.volumes);
            selectedVolumeIndex = null;
            renderVolumeDetail(null);
            addMessage('assistant', `已为您生成 ${data.volumes.length} 卷！您可以继续对话调整卷结构，或点击保存按钮保存为版本。`);
            document.getElementById('save-btn').disabled = false;
            document.getElementById('finalize-btn').disabled = false;
            currentVolumeVersionId = null;
            document.getElementById('volume-version-select').value = '';
        } else {
            addMessage('assistant', `生成失败：${data.message || '未知错误'}`);
        }
    } catch (e) {
        addMessage('assistant', '生成过程出错，请重试');
    }
    
    document.getElementById('generate-btn').disabled = false;
}

function renderVolumes(volumes) {
    const container = document.getElementById('volume-list');
    if (!volumes || volumes.length === 0) {
        container.innerHTML = `
            <div class="volume-empty">
                <i class="fas fa-file-text"></i>
                <p>暂无卷内容</p>
            </div>
        `;
        document.getElementById('volume-count').textContent = '0 卷';
        return;
    }

    container.innerHTML = volumes.map((v, idx) => `
        <div class="volume-item ${selectedVolumeIndex === idx ? 'active' : ''}" 
             onclick="selectVolume(${idx})" 
             data-volume-index="${idx}">
            <div class="volume-item-header">
                <div class="volume-item-title">
                    <span class="volume-item-number">${idx + 1}</span>
                    ${v.title}
                </div>
            </div>
            <div class="volume-item-summary">${v.summary}</div>
        </div>
    `).join('');
    
    document.getElementById('volume-count').textContent = `${volumes.length} 卷`;
}

function selectVolume(index) {
    selectedVolumeIndex = index;
    
    document.querySelectorAll('.volume-item').forEach((item, idx) => {
        item.classList.toggle('active', idx === index);
    });
    
    renderVolumeDetail(currentVolumes[index]);
    
    const editBtn = document.getElementById('detail-actions').querySelector('.detail-btn-edit');
    const deleteBtn = document.getElementById('detail-actions').querySelector('.detail-btn-delete');
    editBtn.disabled = false;
    deleteBtn.disabled = false;
}

function renderVolumeDetail(volume) {
    const container = document.getElementById('volume-detail');
    if (!volume) {
        container.innerHTML = `
            <div class="detail-empty">
                <i class="fas fa-search"></i>
                <p>请从左侧选择一个卷</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="detail-content">
            <div class="detail-header-row">
                <span class="detail-number">${selectedVolumeIndex + 1}</span>
                <span class="detail-title">${volume.title}</span>
            </div>
            <div class="detail-summary">${volume.summary}</div>
        </div>
    `;
}

function openEditModal() {
    if (selectedVolumeIndex === null || !currentVolumes[selectedVolumeIndex]) {
        showToast('请先选择一个卷', 'error');
        return;
    }
    
    const volume = currentVolumes[selectedVolumeIndex];
    document.getElementById('edit-volume-index').value = selectedVolumeIndex;
    document.getElementById('edit-title').value = volume.title;
    document.getElementById('edit-summary').value = volume.summary;
    document.getElementById('edit-modal').classList.add('show');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('show');
}

function saveEditVolume() {
    const index = parseInt(document.getElementById('edit-volume-index').value);
    const title = document.getElementById('edit-title').value.trim();
    const summary = document.getElementById('edit-summary').value.trim();
    
    if (!title) {
        showToast('请输入卷标题', 'error');
        return;
    }
    
    currentVolumes[index] = {
        ...currentVolumes[index],
        title: title,
        summary: summary
    };
    
    renderVolumes(currentVolumes);
    selectVolume(index);
    closeEditModal();
    showToast('修改成功！', 'success');
    
    document.getElementById('save-btn').disabled = false;
    if (currentVolumeVersionId) {
        currentVolumeVersionId = null;
        document.getElementById('volume-version-select').value = '';
    }
}

function deleteVolume() {
    if (selectedVolumeIndex === null) {
        showToast('请先选择一个卷', 'error');
        return;
    }
    
    const volumeTitle = currentVolumes[selectedVolumeIndex].title;
    showModal('删除卷', `确定要删除"${volumeTitle}"吗？`, function() {
        doDeleteVolume();
    });
}

function doDeleteVolume() {
    currentVolumes.splice(selectedVolumeIndex, 1);
    selectedVolumeIndex = null;
    renderVolumes(currentVolumes);
    renderVolumeDetail(null);
    closeModal();
    showToast('删除成功！', 'success');
    
    document.getElementById('save-btn').disabled = currentVolumes.length === 0;
    if (currentVolumeVersionId) {
        currentVolumeVersionId = null;
        document.getElementById('volume-version-select').value = '';
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    input.value = '';
    input.style.height = 'auto';
    addMessage('user', message);
    
    addMessage('assistant', '正在处理您的请求...');
    
    try {
        const versionInfo = currentVolumeVersionId ? `&volume_version_id=${currentVolumeVersionId}` : '';
        const data = await api.postForm('/api/volume/chat/', `project_id=${projectId}&message=${encodeURIComponent(message)}${versionInfo}`);
        if (data.success) {
            const chatBody = document.getElementById('chat-messages');
            const lastMessage = chatBody.lastElementChild;
            if (lastMessage) {
                lastMessage.remove();
            }
            
            addMessage('assistant', data.response);
            
            if (data.volumes) {
                currentVolumes = data.volumes;
                selectedVolumeIndex = null;
                renderVolumes(data.volumes);
                renderVolumeDetail(null);
                document.getElementById('save-btn').disabled = false;
                document.getElementById('finalize-btn').disabled = false;
                currentVolumeVersionId = null;
                document.getElementById('volume-version-select').value = '';
            }
        } else {
            addMessage('assistant', `抱歉，处理失败：${data.message || '未知错误'}`);
        }
    } catch (e) {
        addMessage('assistant', '处理失败，请重试');
    }
}

function addMessage(role, content) {
    const container = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    
    messageDiv.innerHTML = role === 'user' ? `
        <div class="chat-bubble chat-bubble-user">${content}</div>
        <div class="chat-message-avatar avatar-me ms-2">我</div>
    ` : `
        <div class="chat-message-avatar avatar-ai me-2">AI</div>
        <div class="chat-bubble chat-bubble-assistant">${content}</div>
    `;
    
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

function saveVersion() {
    if (!currentVolumes || currentVolumes.length === 0) {
        showToast('请先生成卷内容', 'error');
        return;
    }

    showModal('保存版本', `确定要将当前 ${currentVolumes.length} 卷结构保存为新版本吗？`, function() {
        doSaveVersion();
    });
}

async function doSaveVersion() {
    const volumesJson = JSON.stringify(currentVolumes);
    const data = await api.postForm('/api/volume/save/', `project_id=${projectId}&outline_version_id=${selectedOutlineVersionId || ''}&volumes=${encodeURIComponent(volumesJson)}`);
    if (data.success) {
        showToast(`保存成功！版本号：v${data.version_number}`, 'success');
        currentVolumeVersionId = data.version_id;
        loadVolumeVersions();
        loadVolumeVersion(data.version_id);
    } else {
        showToast(`保存失败：${data.message}`, 'error');
    }
    closeModal();
}

function finalizeVersion() {
    const select = document.getElementById('volume-version-select');
    const selectedText = select.options[select.selectedIndex]?.text || '当前版本';
    showModal('定稿版本', `确定要将 ${selectedText} 标记为定稿吗？定稿后其他版本将自动取消定稿状态。`, function() {
        doFinalizeVersion();
    });
}

async function doFinalizeVersion() {
    const data = await api.postForm('/api/volume/finalize/', `project_id=${projectId}&version_id=${currentVolumeVersionId || ''}`);
    if (data.success) {
        showToast('定稿成功！', 'success');
        loadVolumeVersions();
        if (currentVolumeVersionId) {
            loadVolumeVersion(currentVolumeVersionId);
        }
    } else {
        showToast(`定稿失败：${data.message}`, 'error');
    }
    closeModal();
}

function showModal(title, message, action) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').textContent = message;
    document.getElementById('modal-input').style.display = 'none';
    document.getElementById('confirm-modal').classList.add('show');
    modalAction = action;
}

function closeModal() {
    document.getElementById('confirm-modal').classList.remove('show');
    modalAction = null;
}

function executeModalAction() {
    if (modalAction) {
        modalAction();
    }
}

function showToast(message, type) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>${message}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function goBack() {
    window.location.href = `project.html?project_id=${projectId}`;
}