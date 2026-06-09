let projectId = null;
let currentVolumes = [];
let currentVolumeVersionId = null;
let isVersionFinalized = false;
let selectedOutlineVersionId = null;
let selectedVolumeIndex = null;
let messages = [];
let selectedMessages = new Set();
let isSelectionMode = false;
let isSending = false;
let savedContentBaseline = '';  // 对话前的内容缓存，用于 diff 对比

// 编辑器相关
function initOutlineEditor() {
    const container = document.getElementById('edit-outline-editor');
    if (!container) return;
    if (container.querySelector('textarea')) return;

    const ta = document.createElement('textarea');
    ta.id = 'edit-outline-textarea';
    ta.className = 'outline-editor-textarea';
    ta.placeholder = '输入卷大纲内容（支持Markdown格式）';
    ta.spellcheck = false;
    container.appendChild(ta);
}

function setOutlineContent(text) {
    const ta = document.getElementById('edit-outline-textarea');
    if (ta) {
        ta.value = text || '';
    }
}

function getOutlineContent() {
    const ta = document.getElementById('edit-outline-textarea');
    return ta ? ta.value.trim() : '';
}

document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    projectId = urlParams.get('project_id');

    initBackToProjectButton('.btn-back');

    if (projectId) {
        // 检查认证状态，未登录则弹窗，登录成功后加载数据
        if (!api.isAuthenticated()) {
            api.forceReLogin(() => loadAllData());
        } else {
            loadAllData();
        }
    }

    document.getElementById('outline-select').addEventListener('change', function() {
        selectedOutlineVersionId = this.value;
        const genBtn = document.getElementById('generate-btn');
        if (genBtn) genBtn.disabled = !selectedOutlineVersionId;
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

    const contextDropdown = document.getElementById('context-count-dropdown');
    if (contextDropdown) {
        const saved = localStorage.getItem('volume_context_count');
        if (saved) contextDropdown.value = saved;
        contextDropdown.addEventListener('change', function() {
            localStorage.setItem('volume_context_count', this.value);
        });
    }

    updateButtons();
});

async function loadAllData() {
    showLoading('加载中...');
    try {
        await Promise.all([
            loadProjectInfo(),
            loadOutlineVersions(),
            loadVolumeVersions()
        ]);
    } finally {
        hideLoading();
        const genBtn = document.getElementById('generate-btn');
        if (genBtn) {
            genBtn.style.display = '';
            genBtn.disabled = !selectedOutlineVersionId;
        }
    }
}

async function loadProjectInfo() {
    const data = await api.get(`/api/projects/${projectId}/`);
    if (data && data.success) {
        document.getElementById('project-title').textContent = data.project.title;
    }
}

async function loadOutlineVersions() {
    const data = await api.get(`/api/projects/${projectId}/outline/versions/`);
    if (!data || !data.success) return;

    const select = document.getElementById('outline-select');
    select.innerHTML = '<option value="">请选择大纲版本</option>';

    let latestVersion = null;
    data.versions.forEach(v => {
        const option = document.createElement('option');
        option.value = v.id;
        option.textContent = v.is_finalized
            ? `v${v.version_number} (已锁定)`
            : `v${v.version_number}`;
        select.appendChild(option);
        if (!latestVersion || v.version_number > latestVersion.version_number) {
            latestVersion = v;
        }
    });

    if (latestVersion) {
        select.value = latestVersion.id;
        selectedOutlineVersionId = latestVersion.id;
    }
}

async function loadVolumeVersions() {
    const data = await api.get(`/api/volume-versions/?project_id=${projectId}`);
    if (!data || !data.success) return;

    const select = document.getElementById('volume-version-select');
    select.innerHTML = '<option value="">请选择卷版本</option>';

    let latestVersion = null;
    data.versions.forEach(v => {
        const option = document.createElement('option');
        option.value = v.id;
        option.textContent = v.is_finalized
            ? `v${v.version_number} (已锁定)`
            : `v${v.version_number}`;
        select.appendChild(option);
        if (!latestVersion || v.version_number > latestVersion.version_number) {
            latestVersion = v;
        }
    });

    if (currentVolumeVersionId) {
        select.value = currentVolumeVersionId;
        await loadVolumeVersion(currentVolumeVersionId);
    } else if (latestVersion) {
        select.value = latestVersion.id;
        await loadVolumeVersion(latestVersion.id);
    }
}

async function loadVolumeVersion(versionId) {
    currentVolumeVersionId = versionId;

    const data = await api.get(`/api/volume-versions/${versionId}/`);
    if (data.success) {
        currentVolumes = data.volumes;
        isVersionFinalized = data.is_finalized || false;
        renderVolumes(data.volumes);
        selectedVolumeIndex = null;
        renderVolumeDetail(null);
        updateDetailActions();

        document.getElementById('volume-version-select').value = versionId;

        if (data.outline_version_id) {
            document.getElementById('outline-select').value = data.outline_version_id;
            selectedOutlineVersionId = data.outline_version_id;
        }

        updateButtons();
    }
}

async function generateVolumes() {
    const outlineVersionId = document.getElementById('outline-select').value;
    if (!outlineVersionId) {
        showError('请先选择大纲版本');
        return;
    }

    showLoading('正在生成卷结构...');
    const genBtn = document.getElementById('generate-btn');
    if (genBtn) genBtn.disabled = true;

    // 重置卷列表
    currentVolumes = [];
    renderVolumes([]);
    selectedVolumeIndex = null;
    renderVolumeDetail(null);

    try {
        let versionId = null;

        await api.streamRequestRaw('/api/volume-versions/', {
            method: 'POST',
            body: { project_id: projectId, outline_version_id: outlineVersionId }
        }, (chunk) => {
            if (chunk.done) return;
            const data = chunk.data;
            if (!data) return;

            if (data.type === 'analysis') {
                showLoading(`大纲分析完成\n共 ${data.total_volumes} 卷，${data.total_chapters} 章`);
            } else if (data.type === 'progress') {
                showLoading(data.message);
            } else if (data.type === 'volume') {
                currentVolumes.push(data.volume);
                renderVolumes(currentVolumes);
                updateDetailActions();
                showLoading(`正在生成第 ${data.volume_count}/${data.total_volumes} 卷\n总计已生成 ${data.total_chars} 字`);
            } else if (data.type === 'volume_failed') {
                // 卷生成失败，创建占位卷（无章节）
                currentVolumes.push({
                    id: data.volume_id,
                    volume_number: data.volume_number,
                    title: `第${data.volume_number}卷`,
                    content: '',
                    _failed: true,
                });
                renderVolumes(currentVolumes);
                updateDetailActions();
                showWarning(data.message);
            } else if (data.type === 'complete') {
                versionId = data.version_id;
                currentVolumeVersionId = data.version_id;
                showSuccess(`共生成 ${data.volume_count} 卷`);
                loadVolumeVersions();
                updateButtons();
            } else if (data.type === 'error') {
                showError(`生成失败：${data.message || '未知错误'}`);
            } else if (data.type === 'volume_error') {
                showError(data.message || '部分卷解析失败');
            }
        });
    } catch (e) {
        showError('生成过程出错，请重试');
    } finally {
        hideLoading();
        if (genBtn) genBtn.disabled = false;
    }
}

async function generateSingleVolume(volumeId, volumeNumber) {
    if (!volumeId) {
        showError('卷ID不存在，请刷新页面后重试');
        return;
    }

    if (isVersionFinalized) {
        showError('该版本已锁定，无法修改');
        return;
    }

    const volume = currentVolumes.find(v => v.id === volumeId);
    if (volume && volume.is_locked) {
        showError('该卷已锁定，无法修改');
        return;
    }

    showLoading(`正在生成第 ${volumeNumber} 卷...`);

    try {
        await api.streamRequestRaw(`/api/volume/${volumeId}/generate/`, {
            method: 'POST',
            body: { project_id: projectId }
        }, (chunk) => {
            if (chunk.done) return;
            const data = chunk.data;
            if (!data) return;

            if (data.type === 'progress') {
                showLoading(data.message);
            } else if (data.type === 'complete') {
                // 更新当前卷数据
                const vol = data.volume;
                const idx = currentVolumes.findIndex(v => v.volume_number === vol.volume_number);
                if (idx !== -1) {
                    currentVolumes[idx] = { ...currentVolumes[idx], ...vol, _failed: false };
                    renderVolumes(currentVolumes);
                    if (selectedVolumeIndex === idx) {
                        renderVolumeDetail(currentVolumes[idx]);
                    }
                }
                showSuccess(`第${vol.volume_number}卷生成完成`);
            } else if (data.type === 'error') {
                showError(`生成失败：${data.message || '未知错误'}`);
            }
        });
    } catch (e) {
        showError('生成过程出错，请重试');
    } finally {
        hideLoading();
    }
}

function renderVolumes(volumes) {
    const container = document.getElementById('volume-list');
    const addVolumeBtn = document.getElementById('add-volume-btn');
    const generateBtn = document.getElementById('generate-btn');
    
    if (!volumes || volumes.length === 0) {
        container.innerHTML = `
            <div class="volume-empty">
                <button class="btn btn-gradient-success generate-btn-center" onclick="generateVolumes()" ${!selectedOutlineVersionId ? 'disabled' : ''}>
                    <i class="fas fa-magic"></i> AI生成卷
                </button>
                <p>暂无卷, 选择大纲版本并生成卷</p>
            </div>
        `;
        document.getElementById('volume-count').textContent = '0 卷';
        addVolumeBtn.style.display = 'none';
        return;
    }

    addVolumeBtn.style.display = 'inline-flex';
    
    container.innerHTML = volumes.map((v, idx) => `
        <div class="volume-item ${selectedVolumeIndex === idx ? 'active' : ''} ${v.is_locked ? 'locked' : ''} ${v._failed ? 'volume-failed' : ''}"
             onclick="selectVolume(${idx})"
             data-volume-index="${idx}">
            <div class="volume-item-row">
                <span class="volume-item-number">${v.volume_number || (idx + 1)}</span>
                <span class="volume-item-title">${escapeHtml(v.title)}</span>
                ${v.is_locked ? '<i class="fas fa-lock volume-item-lock-icon"></i>' : ''}
                ${v._failed ? '<span class="volume-failed-badge">生成失败</span>' : ''}
            </div>
            <div class="volume-item-meta">${
                v.chapter_count ? `预估 ${v.chapter_count} 章 · ` : ''
            }${v.updated_at ? `${v.updated_at} · ` : ''
            }${v.content ? `${v.content.length} 字` : '暂无大纲'}</div>
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
    updateDetailActions();
}

function updateDetailActions() {
    const detailActions = document.getElementById('detail-actions');
    const lockBtn = document.getElementById('lock-volume-btn');
    const editBtn = document.getElementById('edit-volume-btn');
    const deleteBtn = document.getElementById('delete-volume-btn');
    
    if (selectedVolumeIndex === null || !currentVolumes[selectedVolumeIndex]) {
        detailActions.style.display = 'none';
        return;
    }
    
    detailActions.style.display = 'flex';
    const volume = currentVolumes[selectedVolumeIndex];
    const isLocked = volume.is_locked;
    
    // 更新锁定按钮状态
    if (isLocked) {
        lockBtn.innerHTML = '<i class="fas fa-unlock"></i> 解锁';
        lockBtn.classList.add('locked');
    } else {
        lockBtn.innerHTML = '<i class="fas fa-lock"></i> 锁定';
        lockBtn.classList.remove('locked');
    }
    
    // 锁定状态下禁用编辑和删除
    editBtn.disabled = isLocked;
    deleteBtn.disabled = isLocked;
}

function renderVolumeDetail(volume) {
    const container = document.getElementById('volume-detail');
    const headerTitle = document.querySelector('.volume-detail-card .card-header h5');

    if (!volume) {
        container.innerHTML = `
            <div class="detail-empty">
                <i class="fas fa-search"></i>
                <p>请从左侧选择一个卷</p>
            </div>
        `;
        if (headerTitle) headerTitle.innerHTML = '<i class="fas fa-file-alt me-2"></i>卷详情';
        return;
    }

    const lockBadge = volume.is_locked 
        ? '<span class="badge badge-warning" style="font-size: 0.75rem; margin-left: 0.5rem;"><i class="fas fa-lock"></i> 已锁定</span>' 
        : '';

    // 更新 card-header 标题
    if (headerTitle) {
        const chapterInfo = volume.chapter_count ? ` · 预估${volume.chapter_count}章` : '';
        headerTitle.innerHTML = `<span class="detail-number">${volume.volume_number || (selectedVolumeIndex + 1)}</span> ${escapeHtml(volume.title)}${chapterInfo} ${lockBadge}`;
    }

    const contentHtml = volume.content
        ? `<div class="markdown-content">${safeMarkdownParse(volume.content)}</div>`
        : volume.id
            ? `<div class="detail-content-empty">
                    <button class="btn btn-gradient-success generate-btn-center" onclick="generateSingleVolume(${volume.id}, ${volume.volume_number})" ${!currentVolumeVersionId ? 'disabled' : ''}>
                        <i class="fas fa-magic"></i> AI生成卷大纲
                    </button>
                    <p>该卷暂无大纲，点击生成</p>
                </div>`
            : `<div class="detail-content-empty">
                    <p>该卷暂无大纲</p>
                </div>`;

    container.innerHTML = contentHtml;
}

async function addNewVolume() {
    if (isVersionFinalized) {
        showError('该版本已锁定，无法新增卷');
        return;
    }

    const newVolumeNumber = currentVolumes.length > 0
        ? Math.max(...currentVolumes.map(v => v.volume_number || 0)) + 1
        : 1;

    document.getElementById('edit-volume-index').value = 'new';
    document.getElementById('edit-volume-number').value = newVolumeNumber;
    document.getElementById('edit-title').value = '';
    document.getElementById('edit-summary').value = '';
    document.getElementById('edit-chapter-count').value = '';
    document.getElementById('edit-modal-title').innerHTML = '<i class="fas fa-plus me-2"></i>新增卷';
    document.getElementById('ai-optimize-btn').style.display = 'none';
    document.getElementById('edit-modal').classList.add('show');
    initOutlineEditor();
    setOutlineContent('');
}

async function openEditModal() {
    if (selectedVolumeIndex === null || !currentVolumes[selectedVolumeIndex]) {
        showError('请先选择一个卷');
        return;
    }

    if (isVersionFinalized) {
        showError('该版本已锁定，无法编辑');
        return;
    }

    const volume = currentVolumes[selectedVolumeIndex];
    if (volume.is_locked) {
        showError('该卷已锁定，无法编辑');
        return;
    }
    
    document.getElementById('edit-volume-index').value = selectedVolumeIndex;
    document.getElementById('edit-volume-number').value = volume.volume_number || '';
    document.getElementById('edit-title').value = volume.title;
    document.getElementById('edit-summary').value = volume.summary || '';
    document.getElementById('edit-chapter-count').value = volume.chapter_count || '';
    document.getElementById('edit-modal-title').innerHTML = '<i class="fas fa-pencil me-2"></i>编辑卷';
    document.getElementById('ai-optimize-btn').style.display = 'inline-flex';
    document.getElementById('edit-modal').classList.add('show');
    initOutlineEditor();
    setOutlineContent(volume.content || '');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('show');
}

async function aiOptimizeVolume() {
    const indexValue = document.getElementById('edit-volume-index').value;
    if (indexValue === 'new') {
        showError('新增卷不支持AI优化');
        return;
    }

    if (isVersionFinalized) {
        showError('该版本已锁定，无法修改');
        return;
    }

    const index = parseInt(indexValue);
    const volume = currentVolumes[index];
    if (!volume) return;

    if (volume.is_locked) {
        showError('该卷已锁定，无法修改');
        return;
    }

    const title = document.getElementById('edit-title').value.trim();
    const summary = document.getElementById('edit-summary').value.trim();
    if (!title && !summary) {
        showError('请先输入卷标题或概述');
        return;
    }

    const aiBtn = document.getElementById('ai-optimize-btn');
    aiBtn.disabled = true;
    aiBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 优化中...';

    const currentContent = getOutlineContent();
    let streamText = '';
    const ta = document.getElementById('edit-outline-textarea');

    try {
        await api.streamRequestRaw('/api/volume/optimize/', {
            method: 'POST',
            body: {
                project_id: projectId,
                version_id: currentVolumeVersionId,
                volume_number: volume.volume_number,
                volume_title: title,
                volume_summary: summary,
                current_content: currentContent,
                user_feedback: '请优化这一卷的大纲，以扩展和丰富内容为主'
            }
        }, async (chunk) => {
            if (chunk.done) return;
            const data = chunk.data;
            if (!data) return;

            if (data.type === 'chunk') {
                const chunkStr = chunk.content || '';
                if (chunkStr) {
                    streamText += chunkStr;
                    if (ta) {
                        ta.value = streamText;
                        ta.scrollTop = ta.scrollHeight;
                    }
                }
            } else if (data.type === 'complete' && data.volume) {
                if (data.volume.content) {
                    setOutlineContent(data.volume.content);
                }
                showSuccess('AI优化完成');
            } else if (data.type === 'error') {
                showError(`AI优化失败：${data.message || '未知错误'}`);
            }
        });
    } catch (e) {
        showError('AI优化失败，请重试');
    } finally {
        aiBtn.disabled = false;
        aiBtn.innerHTML = '<i class="fas fa-magic"></i> AI优化';
    }
}

async function saveEditVolume() {
    const indexValue = document.getElementById('edit-volume-index').value;
    const title = document.getElementById('edit-title').value.trim();
    const summary = document.getElementById('edit-summary').value.trim();
    const content = getOutlineContent();
    let volumeNumber = parseInt(document.getElementById('edit-volume-number').value) || null;
    let chapterCount = parseInt(document.getElementById('edit-chapter-count').value) || 0;

    if (!title) {
        showError('请输入卷标题');
        return;
    }

    if (volumeNumber !== null && volumeNumber < 1) {
        showError('卷编号必须为正整数');
        return;
    }

    if (chapterCount < 0) {
        showError('预估章节数不能为负数');
        return;
    }

    // 准备保存数据（不直接修改 currentVolumes，避免保存失败时数据损坏）
    let volumesToSave = currentVolumes.map(v => ({...v}));

    // 卷编号唯一性处理：如果编号与其他卷冲突，自动递增冲突卷的编号
    if (volumeNumber !== null) {
        const usedNumbers = new Set();
        volumesToSave.forEach((v, i) => {
            const isCurrentEdit = (indexValue !== 'new' && i === parseInt(indexValue));
            if (v.volume_number === volumeNumber && !isCurrentEdit) {
                // 跳过，稍后分配新编号
            } else {
                usedNumbers.add(v.volume_number);
            }
        });
        // 为冲突卷分配新的唯一编号
        volumesToSave.forEach((v, i) => {
            const isCurrentEdit = (indexValue !== 'new' && i === parseInt(indexValue));
            if (v.volume_number === volumeNumber && !isCurrentEdit) {
                let newNum = volumeNumber + 1;
                while (usedNumbers.has(newNum)) newNum++;
                usedNumbers.add(newNum);
                v.volume_number = newNum;
            }
        });
    }

    if (indexValue === 'new') {
        // 新增卷
        if (!volumeNumber) {
            volumeNumber = volumesToSave.length > 0
                ? Math.max(...volumesToSave.map(v => v.volume_number || 0)) + 1
                : 1;
        }
        volumesToSave.push({
            volume_number: volumeNumber,
            title: title,
            summary: summary,
            chapter_count: chapterCount,
            content: content,
            is_locked: false
        });
    } else {
        // 编辑卷
        const index = parseInt(indexValue);
        volumesToSave[index] = {
            ...volumesToSave[index],
            volume_number: volumeNumber,
            title: title,
            summary: summary,
            chapter_count: chapterCount,
            content: content
        };
    }

    // 保存到后端（先保存再关弹窗，避免保存失败时数据丢失）
    showLoading('保存中...');
    try {
        const payload = {
            project_id: projectId,
            outline_version_id: selectedOutlineVersionId || '',
            volumes: JSON.stringify(volumesToSave)
        };
        const data = await api.put(`/api/volume-versions/${currentVolumeVersionId}/`, payload);
        if (!data.success) {
            showError(`保存失败：${data.message}`);
            return;
        }
    } catch (e) {
        showError('保存失败，请重试');
        return;
    } finally {
        hideLoading();
    }

    closeEditModal();

    // 保存成功后更新本地数据
    currentVolumes = volumesToSave;
    renderVolumes(currentVolumes);
    if (indexValue === 'new') {
        selectedVolumeIndex = currentVolumes.length - 1;
        selectVolume(selectedVolumeIndex);
    } else {
        selectVolume(parseInt(indexValue));
    }
    showSuccess(indexValue === 'new' ? '新增成功！' : '修改成功！');
}

function deleteVolume() {
    if (selectedVolumeIndex === null) {
        showError('请先选择一个卷');
        return;
    }
    
    if (isVersionFinalized) {
        showError('该版本已整体锁定，无法删除卷');
        return;
    }
    
    const volume = currentVolumes[selectedVolumeIndex];
    if (volume.is_locked) {
        showError('该卷已锁定，无法删除');
        return;
    }
    
    const volumeTitle = volume.title;
    
    if (currentVolumes.length === 1) {
        showModal('删除卷', `该版本仅剩此卷，删除后版本将一并删除且无法恢复。确定要删除"${volumeTitle}"吗？`, function() {
            doDeleteVolume();
        });
    } else {
        showModal('删除卷', `确定要删除"${volumeTitle}"吗？`, function() {
            doDeleteVolume();
        });
    }
}

async function doDeleteVolume() {
    const volume = currentVolumes[selectedVolumeIndex];
    const deleteIndex = selectedVolumeIndex;

    closeModal();

    // 如果没有卷了（删除后），删除该版本
    if (currentVolumes.length === 1 && currentVolumeVersionId) {
        // 先从本地移除再删版本
        currentVolumes.splice(deleteIndex, 1);
        selectedVolumeIndex = null;
        await deleteVersion(currentVolumeVersionId);
        return;
    }

    // 保存到后端（先保存再修改本地数据，避免API失败时数据损坏）
    showLoading('删除中...');
    try {
        const remainingVolumes = currentVolumes.filter((_, i) => i !== deleteIndex);
        const payload = {
            project_id: projectId,
            outline_version_id: selectedOutlineVersionId || '',
            volumes: JSON.stringify(remainingVolumes)
        };
        const data = await api.put(`/api/volume-versions/${currentVolumeVersionId}/`, payload);
        if (!data.success) {
            showError(`删除失败：${data.message}`);
        } else {
            // API成功后再更新本地数据
            currentVolumes = remainingVolumes;
            selectedVolumeIndex = null;
            showSuccess('删除成功！');
        }
    } catch (e) {
        showError('删除失败，请重试');
    } finally {
        hideLoading();
    }
    renderVolumes(currentVolumes);
    renderVolumeDetail(null);
    updateDetailActions();
}

async function deleteVersion(versionId) {
    showLoading('删除中...');
    try {
        await api.delete(`/api/volume-versions/${versionId}/`);
    } catch (e) {
        // 忽略错误，继续清理
    } finally {
        hideLoading();
    }
    currentVolumeVersionId = null;
    isVersionFinalized = false;
    currentVolumes = [];
    renderVolumes([]);
    renderVolumeDetail(null);
    updateDetailActions();
    loadVolumeVersions();
    updateButtons();
    showSuccess('版本已删除');
}

async function lockVolume() {
    if (selectedVolumeIndex === null || !currentVolumes[selectedVolumeIndex]) {
        return;
    }

    if (isVersionFinalized) {
        showError('该版本已锁定，无法操作单卷锁定');
        return;
    }

    const volume = currentVolumes[selectedVolumeIndex];
    const newLockState = !volume.is_locked;
    
    // 如果有 volume id，调用后端 API
    if (volume.id && currentVolumeVersionId) {
        showLoading(newLockState ? '锁定中...' : '解锁中...');
        try {
            const data = await api.put(`/api/volume/${volume.id}/lock/`, {
                is_locked: newLockState
            });
            if (!data.success) {
                showError(`操作失败：${data.message || '未知错误'}`);
                return;
            }
        } catch (e) {
            showError('操作失败，请重试');
            return;
        } finally {
            hideLoading();
        }
    }
    
    // 更新本地数据
    currentVolumes[selectedVolumeIndex].is_locked = newLockState;
    renderVolumes(currentVolumes);
    selectVolume(selectedVolumeIndex);
    showSuccess(newLockState ? '已锁定' : '已解锁');
}

function updateButtons() {
    const hasContent = currentVolumes && currentVolumes.length > 0;
    const saveAsBtn = document.getElementById('save-as-btn');
    const finalizeBtn = document.getElementById('finalize-btn');
    if (saveAsBtn) saveAsBtn.disabled = !hasContent;
    if (finalizeBtn) {
        finalizeBtn.disabled = !hasContent || !currentVolumeVersionId;
        if (isVersionFinalized) {
            finalizeBtn.innerHTML = '<i class="fas fa-unlock"></i> 版本解锁';
            finalizeBtn.classList.add('btn-finalize-locked');
        } else {
            finalizeBtn.innerHTML = '<i class="fas fa-lock"></i> 版本锁定';
            finalizeBtn.classList.remove('btn-finalize-locked');
        }
    }
}

// 另存为新版本
function saveVersion() {
    if (!currentVolumes || currentVolumes.length === 0) {
        showError('请先生成卷内容');
        return;
    }
    const btn = document.getElementById('save-as-btn');
    const msg = btn ? btn.getAttribute('data-msg') : '确认另存为新版本？';
    showModal('另存为新版本', msg, function() {
        doSaveVersion();
    });
}

async function doSaveVersion() {
    if (!currentVolumeVersionId) {
        showError('请先选择或生成一个卷版本');
        closeModal();
        return;
    }
    showLoading('保存中...');
    try {
        const payload = {
            project_id: projectId,
            outline_version_id: selectedOutlineVersionId || '',
            volumes: JSON.stringify(currentVolumes)
        };

        const data = await api.post(`/api/volume-versions/${currentVolumeVersionId}/save/`, payload);
        if (data.success) {
            showSuccess(`另存成功！版本号：v${data.version_number}`);
            currentVolumeVersionId = data.version_id;
            await loadVolumeVersions();
        } else {
            showError(`保存失败：${data.message}`);
        }
    } catch (e) {
        showError('保存失败，请重试');
    } finally {
        hideLoading();
    }
    closeModal();
}

function finalizeVersion() {
    const select = document.getElementById('volume-version-select');
    const selectedText = select.options[select.selectedIndex]?.text || '当前版本';
    if (isVersionFinalized) {
        showModal('版本解锁', `确定要将 ${selectedText} 解除锁定吗？`, function() {
            doFinalizeVersion();
        });
    } else {
        showModal('版本锁定', `确定要将 ${selectedText} 标记为锁定吗？`, function() {
            doFinalizeVersion();
        });
    }
}

async function doFinalizeVersion() {
    showLoading(isVersionFinalized ? '解锁中...' : '锁定中...');
    try {
        const data = await api.post(`/api/volume-versions/${currentVolumeVersionId}/finalize/`);
        if (data.success) {
            isVersionFinalized = data.is_finalized;
            showSuccess(isVersionFinalized ? '版本锁定成功！' : '版本解锁成功！');
            loadVolumeVersions();
            updateButtons();
        } else {
            showError(`操作失败：${data.message}`);
        }
    } catch (e) {
        showError('操作失败，请重试');
    } finally {
        hideLoading();
    }
    closeModal();
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;
    if (!currentVolumeVersionId) {
        showWarning('请先选择或生成卷版本');
        return;
    }
    if (isVersionFinalized) {
        showWarning('该版本已锁定，无法修改');
        return;
    }
    if (selectedVolumeIndex === null || !currentVolumes[selectedVolumeIndex]) {
        showWarning('请先选择需要调整的篇章');
        return;
    }
    
    // 检查选中卷是否锁定
    const currentVolume = currentVolumes[selectedVolumeIndex];
    if (currentVolume.is_locked) {
        showWarning('该卷已锁定，无法修改');
        return;
    }
    
    if (isSending) return;

    isSending = true;
    const sendBtn = document.querySelector('.btn-send');
    if (sendBtn) sendBtn.disabled = true;
    input.disabled = true;

    // 缓存当前卷内容作为 diff 基线
    savedContentBaseline = currentVolume.content || '';

    input.value = '';
    input.style.height = 'auto';
    messages.push({ role: 'user', content: message });
    renderChatHistory();

    const placeholderIdx = messages.length;
    messages.push({ role: 'assistant', content: '' });
    renderChatHistory();

    // 分隔符常量
    const CONTENT_START = '════CONTENT_START════';
    const CONTENT_END = '════CONTENT_END════';
    const QUESTION_START = '════QUESTION_START════';
    const QUESTION_END = '════QUESTION_END════';

    // 流式解析状态
    let rawBuffer = '';
    let inContent = false;
    let inQuestion = false;
    let contentFinished = false;
    let parsedContent = '';
    let parsedQuestion = '';
    let preambleText = '';  // CONTENT_START 之前的前言文本
    let chatTypingDiv = null;

    // 获取聊天加载/打字气泡 DOM
    function getLoadingDiv() {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return null;
        const allMsgs = chatMessages.querySelectorAll('.chat-message.assistant');
        return allMsgs[allMsgs.length - 1] || null;
    }

    // 初始化聊天打字气泡（从"思考中..."切换到"输出中..."）
    function initChatTyping() {
        const loadingDiv = getLoadingDiv();
        if (!loadingDiv) return null;
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble chat-bubble-assistant';
        bubble.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 输出中...';
        loadingDiv.innerHTML = '<div class="chat-message-avatar avatar-ai me-2">AI</div>';
        loadingDiv.appendChild(bubble);
        return bubble;
    }

    // 滚动详情区到底部
    function scrollDetailToBottom() {
        const detailContainer = document.getElementById('volume-detail');
        if (detailContainer) {
            detailContainer.scrollTop = detailContainer.scrollHeight;
        }
    }

    // diff 高亮函数
    function diffHighlight(oldContent, newContent) {
        const oldHtml = oldContent.trim() ? safeMarkdownParse(oldContent) : '';
        const newHtml = newContent.trim() ? safeMarkdownParse(newContent) : '';

        if (!oldHtml.trim()) {
            return newHtml;
        }

        const oldLines = oldHtml.split('\n');
        const newLines = newHtml.split('\n');
        let result = '';
        let lineIndex = 0;

        while (lineIndex < newLines.length) {
            const newLine = newLines[lineIndex];
            const oldLine = oldLines[lineIndex];

            if (oldLine === newLine) {
                result += newLine + '\n';
            } else if (!oldLine) {
                result += `<div class="diff-change">${newLine}</div>\n`;
            } else {
                result += `<div class="diff-change">${newLine}</div>\n`;
            }
            lineIndex++;
        }
        return result.trim();
    }

    // 流式解析函数
    function processStream() {
        // 提取 content 区
        if (!contentFinished) {
            if (!inContent && rawBuffer.includes(CONTENT_START)) {
                inContent = true;
                // 提取 CONTENT_START 之前的前言文本（LLM 可能在分隔符前输出说明）
                const csIdx = rawBuffer.indexOf(CONTENT_START);
                preambleText = rawBuffer.substring(0, csIdx).trim();
                // 首次收到内容，切换气泡到"输出中..."
                if (!chatTypingDiv) {
                    chatTypingDiv = initChatTyping();
                }
                const startIdx = csIdx + CONTENT_START.length;
                const endIdx = rawBuffer.indexOf(CONTENT_END, startIdx);
                if (endIdx !== -1) {
                    parsedContent = rawBuffer.substring(startIdx, endIdx).trim();
                    inContent = false;
                    contentFinished = true;
                } else {
                    parsedContent = rawBuffer.substring(startIdx).trim();
                }
            } else if (inContent) {
                const csIdx = rawBuffer.indexOf(CONTENT_START);
                const endIdx = rawBuffer.indexOf(CONTENT_END);
                if (endIdx !== -1) {
                    parsedContent = rawBuffer.substring(csIdx + CONTENT_START.length, endIdx).trim();
                    inContent = false;
                    contentFinished = true;
                } else {
                    parsedContent = rawBuffer.substring(csIdx + CONTENT_START.length).trim();
                }
            }

            // 渲染 content 到详情区（打字机效果 + diff 高亮）
            if (parsedContent) {
                const detailContainer = document.getElementById('volume-detail');
                if (detailContainer) {
                    const highlighted = diffHighlight(savedContentBaseline, parsedContent);
                    detailContainer.innerHTML = `<div class="markdown-content">${highlighted}</div>`;
                    scrollDetailToBottom();
                }
            }
        }

        // 提取 question 区
        if (contentFinished) {
            if (!inQuestion && rawBuffer.includes(QUESTION_START)) {
                inQuestion = true;
                const startIdx = rawBuffer.indexOf(QUESTION_START) + QUESTION_START.length;
                const endIdx = rawBuffer.indexOf(QUESTION_END, startIdx);
                if (endIdx !== -1) {
                    parsedQuestion = rawBuffer.substring(startIdx, endIdx).trim();
                    inQuestion = false;
                } else {
                    parsedQuestion = rawBuffer.substring(startIdx).trim();
                }
                if (!chatTypingDiv) {
                    chatTypingDiv = initChatTyping();
                }
            } else if (inQuestion) {
                const startIdx = rawBuffer.indexOf(QUESTION_START) + QUESTION_START.length;
                const endIdx = rawBuffer.indexOf(QUESTION_END, startIdx);
                if (endIdx !== -1) {
                    parsedQuestion = rawBuffer.substring(startIdx, endIdx).trim();
                    inQuestion = false;
                } else {
                    parsedQuestion = rawBuffer.substring(startIdx).trim();
                }
            }

            // 渲染 question 到聊天区（打字机效果）
            if (parsedQuestion && chatTypingDiv) {
                chatTypingDiv.innerHTML = `<div class="markdown-content">${safeMarkdownParse(parsedQuestion)}</div>`;
                const chatMessages = document.getElementById('chat-messages');
                if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        }
    }

    try {
        const contextCount = document.getElementById('context-count-dropdown')?.value || '10';
        let historyMessages = messages.slice(0, -1);
        if (contextCount !== 'all') {
            historyMessages = historyMessages.slice(-parseInt(contextCount) * 2);
        }

        // 获取当前选中卷的卷号
        const currentVolumeNumber = currentVolume ? currentVolume.volume_number : null;

        await api.streamRequestRaw(`/api/volume-versions/${currentVolumeVersionId}/chat/`, {
            method: 'POST',
            body: { message, context_messages: historyMessages, current_volume_number: currentVolumeNumber }
        }, (chunk) => {
            if (chunk.done) return;
            const data = chunk.data;
            if (!data) return;

            if (data.type === 'chunk') {
                rawBuffer += data.data || '';
                processStream();
            } else if (data.type === 'target_merge') {
                // 跨卷合并中，追加提示到聊天区
                if (chatTypingDiv) {
                    const mergeHint = `\n\n正在优化第${data.target_volume_number}卷「${data.target_volume_title}」...`;
                    chatTypingDiv.innerHTML += `<p style="color: var(--text-muted); margin-top: 0.5rem;">${mergeHint}</p>`;
                }
            } else if (data.type === 'complete') {
                // 最终处理：更新 question 到消息历史（不回退到 rawBuffer，避免分隔符和 content 泄漏到聊天区）
                const finalQuestion = parsedQuestion || preambleText || '修改完成';
                messages[placeholderIdx] = { role: 'assistant', content: finalQuestion };
                renderChatHistory();

                // 更新卷数据（保持当前选择）
                if (data.volumes) {
                    currentVolumes = data.volumes;
                    renderVolumes(data.volumes);
                    // 保持选中当前卷
                    if (currentVolumeNumber) {
                        const newIdx = currentVolumes.findIndex(v => v.volume_number === currentVolumeNumber);
                        if (newIdx !== -1) {
                            selectedVolumeIndex = newIdx;
                            // 用 diff 高亮渲染
                            const vol = currentVolumes[newIdx];
                            if (vol.content) {
                                const detailContainer = document.getElementById('volume-detail');
                                if (detailContainer) {
                                    detailContainer.innerHTML = `<div class="markdown-content">${diffHighlight(savedContentBaseline, vol.content)}</div>`;
                                    scrollDetailToBottom();
                                }
                            } else {
                                renderVolumeDetail(vol);
                            }
                        } else {
                            renderVolumeDetail(null);
                        }
                    }
                    updateDetailActions();
                    // 更新基线为当前内容
                    if (selectedVolumeIndex !== null && currentVolumes[selectedVolumeIndex]) {
                        savedContentBaseline = currentVolumes[selectedVolumeIndex].content || '';
                    }
                } else if (parsedContent) {
                    // 仅更新当前卷的 content
                    if (currentVolume) {
                        currentVolumes[selectedVolumeIndex].content = parsedContent;
                        // diff 高亮已在 processStream 中渲染，更新基线
                        savedContentBaseline = parsedContent;
                    }
                }
            } else if (data.type === 'error') {
                messages[placeholderIdx] = {
                    role: 'assistant',
                    content: `抱歉，处理失败：${data.message || '未知错误'}`
                };
                renderChatHistory();
            }
        });
    } catch (e) {
        messages[placeholderIdx] = { role: 'assistant', content: '处理失败，请重试' };
        renderChatHistory();
    } finally {
        isSending = false;
        if (sendBtn) sendBtn.disabled = false;
        input.disabled = false;
    }
}

function renderChatHistory() {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    if (!messages || messages.length === 0) {
        container.innerHTML = `
            <div class="chat-message assistant">
                <div class="chat-message-avatar avatar-ai me-2">AI</div>
                <div class="chat-bubble chat-bubble-assistant"><div class="markdown-content">您好！我是卷生成助手。请先选择大纲版本，然后点击"生成卷"按钮，我将根据大纲内容为您生成卷结构。</div></div>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    messages.forEach((msg, idx) => {
        const div = document.createElement('div');
        div.className = `chat-message ${msg.role}${selectedMessages.has(idx) ? ' selected' : ''}`;
        div.dataset.messageIndex = idx;

        if (msg.role === 'user') {
            div.innerHTML = `
                ${isSelectionMode ? `<input type="checkbox" class="chat-message-checkbox" onchange="toggleMessageSelect(${idx})" ${selectedMessages.has(idx) ? 'checked' : ''}>` : ''}
                <div class="chat-bubble chat-bubble-user">${escapeHtml(msg.content).replace(/\n/g, '<br>')}</div>
                <div class="chat-message-avatar avatar-me ms-2">我</div>
            `;
        } else {
            const content = msg.content
                ? `<div class="markdown-content">${safeMarkdownParse(msg.content)}</div>`
                : '<i class="fas fa-spinner fa-spin"></i> 思考中...';
            div.innerHTML = `
                ${isSelectionMode ? `<input type="checkbox" class="chat-message-checkbox" onchange="toggleMessageSelect(${idx})" ${selectedMessages.has(idx) ? 'checked' : ''}>` : ''}
                <div class="chat-message-avatar avatar-ai me-2">AI</div>
                <div class="chat-bubble chat-bubble-assistant">${content}</div>
            `;
        }
        container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
}

function enterSelectionMode() {
    isSelectionMode = true;
    selectedMessages.clear();
    document.getElementById('toggle-selection-btn').style.display = 'none';
    document.getElementById('selection-actions').style.display = 'flex';
    document.getElementById('context-count-select').style.display = 'none';
    renderChatHistory();
}

function cancelSelection() {
    isSelectionMode = false;
    selectedMessages.clear();
    document.getElementById('toggle-selection-btn').style.display = 'flex';
    document.getElementById('selection-actions').style.display = 'none';
    document.getElementById('context-count-select').style.display = 'flex';
    renderChatHistory();
}

function toggleMessageSelect(index) {
    if (selectedMessages.has(index)) {
        selectedMessages.delete(index);
    } else {
        selectedMessages.add(index);
    }
    const div = document.querySelector(`.chat-message[data-message-index="${index}"]`);
    if (div) div.classList.toggle('selected');
    const delBtn = document.getElementById('delete-selected-btn');
    if (delBtn) delBtn.disabled = selectedMessages.size === 0;
}

function toggleSelectAll() {
    const checkboxes = document.querySelectorAll('.chat-message-checkbox');
    const allChecked = selectedMessages.size === messages.length;
    if (allChecked) {
        selectedMessages.clear();
    } else {
        messages.forEach((_, i) => selectedMessages.add(i));
    }
    checkboxes.forEach((cb, i) => {
        cb.checked = !allChecked;
        const div = document.querySelector(`.chat-message[data-message-index="${i}"]`);
        if (div) div.classList.toggle('selected', !allChecked);
    });
    const delBtn = document.getElementById('delete-selected-btn');
    if (delBtn) delBtn.disabled = selectedMessages.size === 0;
}

function deleteSelectedMessages() {
    if (selectedMessages.size === 0) return;
    showModal('删除对话', `确定要删除选中的 ${selectedMessages.size} 条对话吗？`, function() {
        const sorted = Array.from(selectedMessages).sort((a, b) => b - a);
        sorted.forEach(i => messages.splice(i, 1));
        selectedMessages.clear();
        cancelSelection();
        closeModal();
        showSuccess('删除成功！');
    });
}
