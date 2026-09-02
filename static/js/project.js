let projectId = null;

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    // 从 URL 参数中获取项目 ID
    projectId = getProjectIdFromUrl();
    
    if (projectId) {
        showLoading('加载中...');
        Promise.all([loadProjectInfo(projectId, (data) => {
            const project = data.project;
            const versionCount = data.project.version_count || 0;
            const latestVersionNumber = data.project.latest_version_number ?? 0;
            updateActionCards(project.status, versionCount, latestVersionNumber);
        }), loadProjectStats()]).finally(() => hideLoading());
    } else {
        window.location.href = '/';
    }
    
    // 返回书架按钮点击事件
    const backButton = document.getElementById('backButton');
    if (backButton) {
        backButton.addEventListener('click', goBack);
    }
});

function updateActionCards(status, versionCount, latestVersionNumber) {
    const outlineAction = document.getElementById('action-outline');
    const volumeAction = document.getElementById('action-volume');
    const chapterAction = document.getElementById('action-chapter');
    const noteAction = document.getElementById('action-note');

    // 大纲优化
    outlineAction.querySelector('.action-title').textContent = '大纲优化';
    outlineAction.querySelector('.action-desc').textContent = '编辑和优化小说大纲，支持AI辅助生成';
    outlineAction.classList.remove('disabled');
    outlineAction.onclick = openOutlineBuilder;

    // 其他功能可用
    setActionDisabled(volumeAction, false);
    setActionDisabled(chapterAction, false);
    setActionDisabled(noteAction, false);

    volumeAction.onclick = openVolumeGenerator;
    chapterAction.onclick = openChapterGenerator;
    noteAction.onclick = openNoteManager;
}

function setActionDisabled(actionCard, disabled) {
    if (disabled) {
        actionCard.classList.add('disabled');
        actionCard.style.opacity = '0.5';
        actionCard.style.pointerEvents = 'none';
    } else {
        actionCard.classList.remove('disabled');
        actionCard.style.opacity = '1';
        actionCard.style.pointerEvents = 'auto';
    }
}

async function loadProjectStats() {
    try {
        const data = await api.get(`/api/projects/${projectId}/stats/`);
        if (data.success) {
            document.getElementById('volume-count').textContent = data.volume_count || 0;
            document.getElementById('chapter-count').textContent = data.chapter_count || 0;
            document.getElementById('chapter-summary').textContent = data.chapter_with_summary || 0;
            document.getElementById('chapter-content').textContent = data.chapter_with_content || 0;
            document.getElementById('chapter-finalized').textContent = data.chapter_finalized || 0;
            document.getElementById('chapter-published').textContent = data.chapter_published || 0;
        }
    } catch (error) {
        console.error('Failed to load project stats:', error);
    }
}

function goBack() {
    window.location.href = '/';
}

function openOutlineBuilder() {
    window.location.href = `/${projectId}/outline/`;
}


function openTimelineManager() {
    window.location.href = `/${projectId}/timeline/`;
}

function openVolumeGenerator() {
    window.location.href = `/${projectId}/volume/`;
}

function openChapterGenerator() {
    window.location.href = `/${projectId}/chapter/`;
}



function openNoteManager() {
    window.location.href = `/${projectId}/note/`;
}



function editProject() {
    api.get(`/api/projects/${projectId}/`).then(data => {
        if (data.success) {
            document.getElementById('edit-title').value = data.project.title;
            document.getElementById('edit-description').value = data.project.description || '';
            document.getElementById('edit-min-words').value = data.project.min_words_per_chapter || 3000;
            
            // 隐藏之前的推荐
            const suggestionsContainer = document.getElementById('title-suggestions-container');
            if (suggestionsContainer) {
                suggestionsContainer.style.display = 'none';
            }
            
            const descContainer = document.getElementById('description-suggestions-container');
            if (descContainer) {
                descContainer.style.display = 'none';
            }
            
            // 显示自定义弹窗
            document.getElementById('editProjectModal').classList.add('show');
        }
    });
}

function closeEditModal() {
    document.getElementById('editProjectModal').classList.remove('show');
}

function selectTitle(title) {
    document.getElementById('edit-title').value = title;
    // 选择书名后隐藏推荐列表
    const suggestionsContainer = document.getElementById('title-suggestions-container');
    if (suggestionsContainer) {
        suggestionsContainer.style.display = 'none';
    }
}

function selectDescription(description) {
    document.getElementById('edit-description').value = description;
    document.getElementById('description-suggestions-container').style.display = 'none';
}

async function generateTitle() {
    const btn = document.getElementById('ai-generate-title-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';

    try {
        const data = await api.post(`/api/projects/${projectId}/title/suggest/`);
        
        if (data.success && data.titles && data.titles.length > 0) {
            const container = document.getElementById('title-suggestions-container');
            const list = document.getElementById('title-suggestions-list');
            list.innerHTML = data.titles.map((title, i) => `
                <div class="title-suggestion-item" onclick="selectTitle('${escapeHtml(title).replace(/'/g, "\\'")}')">
                    ${i + 1}. ${escapeHtml(title)}
                </div>
            `).join('');
            container.style.display = 'block';
            document.getElementById('edit-title').value = data.titles[0];
        } else {
            showToast(data.message || '生成失败', 'error');
        }
    } catch (error) {
        showToast('网络错误，请重试', 'error');
    }

    btn.disabled = false;
    btn.innerHTML = originalText;
}

async function generateDescription() {
    const btn = document.getElementById('ai-generate-desc-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const data = await api.post(`/api/projects/${projectId}/description/suggest/`);
        
        if (data.success && data.description) {
            const container = document.getElementById('description-suggestions-container');
            const content = document.getElementById('description-suggestion-content');
            content.innerHTML = '<div class="suggestion-tip"><i class="fas fa-hand-pointer"></i> 点击此区域将简介填入输入框</div>' + escapeHtml(data.description).replace(/\n/g, '<br>');
            content.onclick = function() {
                selectDescription(data.description);
            };
            container.style.display = 'block';
        } else {
            showToast(data.message || '生成失败', 'error');
        }
    } catch (error) {
        showToast('网络错误，请重试', 'error');
    }

    btn.disabled = false;
    btn.innerHTML = originalText;
}



async function saveProjectEdit() {
    const title = document.getElementById('edit-title').value;
    const description = document.getElementById('edit-description').value;
    const minWords = parseInt(document.getElementById('edit-min-words').value) || 3000;

    const data = await api.put(`/api/projects/${projectId}/`, { title, description, min_words_per_chapter: minWords });

    if (data.success) {
        location.reload();
    } else {
        alert(data.message || '保存失败');
    }
}


// ============ 世界观管理 ============

async function openWorldWorkspace() {
    window.location.href = `/${projectId}/worldview/`;
}

// ============ 人物管理 ============

function openCharacterManager() {
    window.location.href = `/${projectId}/character/`;
}

function openGraphManager() {
    window.location.href = `/${projectId}/graph/`;
}