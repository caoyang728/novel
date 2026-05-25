let projectId = null;

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    // 从 URL 参数中获取项目 ID
    const urlParams = new URLSearchParams(window.location.search);
    projectId = urlParams.get('project_id');
    
    if (projectId) {
        loadProjectInfo();
        loadProjectStats();
    } else {
        window.location.href = 'index.html';
    }
    
    // 返回书架按钮点击事件
    const backButton = document.getElementById('backButton');
    if (backButton) {
        backButton.addEventListener('click', goBack);
    }
});

async function checkAuth() {
    try {
        const data = await api.get('/api/auth/user/');
        if (!data.success) {
            // 认证失败交给 common.js 的 request 函数处理（弹窗登录）
        }
    } catch (error) {
        // 认证失败交给 common.js 的 request 函数处理（弹窗登录）
    }
}

async function loadProjectInfo() {
    try {
        const data = await api.get(`/api/projects/${projectId}/`);
        console.log('API返回数据:', JSON.stringify(data));  // 调试日志
        if (data.success) {
            const project = data.project;
            const versionCount = data.project.version_count || 0;
            const latestVersionNumber = data.project.latest_version_number ?? 0;
            console.log('项目状态:', project.status, '版本数量:', versionCount, '最新版本号:', latestVersionNumber);  // 调试日志
            document.getElementById('project-title').textContent = project.title;
            document.getElementById('project-description').textContent = project.description || '暂无描述';

            // 根据最新版本的 version_number 更新功能入口
            updateActionCards(project.status, versionCount, latestVersionNumber);
        }
    } catch (error) {
        console.error('Failed to load project info:', error);
    }
}

function updateActionCards(status, versionCount, latestVersionNumber) {
    const outlineAction = document.getElementById('action-outline');
    const volumeAction = document.getElementById('action-volume');
    const chapterAction = document.getElementById('action-chapter');
    const contentAction = document.getElementById('action-content');
    const noteAction = document.getElementById('action-note');

    // 根据最新版本的 version_number 决定显示"大纲构建"还是"大纲优化"
    // 只有 latest_version_number === 0 或没有版本时，显示"大纲构建"
    // 否则显示"大纲优化"
    if (latestVersionNumber === 0) {
        // 大纲构建
        outlineAction.querySelector('.action-title').textContent = '大纲构建';
        outlineAction.querySelector('.action-desc').textContent = '通过AI对话构建小说大纲';
        outlineAction.classList.remove('disabled');
        outlineAction.onclick = openNewProjectBuilder;

        // 其他功能可用
        setActionDisabled(volumeAction, false);
        setActionDisabled(chapterAction, false);
        setActionDisabled(contentAction, false);
        setActionDisabled(noteAction, false);

        volumeAction.onclick = openVolumeGenerator;
        chapterAction.onclick = openChapterGenerator;
        contentAction.onclick = openContentGenerator;
        noteAction.onclick = openNoteManager;
    } else {
        // 大纲优化
        outlineAction.querySelector('.action-title').textContent = '大纲优化';
        outlineAction.querySelector('.action-desc').textContent = '编辑和优化小说大纲，支持AI辅助生成';
        outlineAction.classList.remove('disabled');
        outlineAction.onclick = openOutlineBuilder;

        // 其他功能可用
        setActionDisabled(volumeAction, false);
        setActionDisabled(chapterAction, false);
        setActionDisabled(contentAction, false);
        setActionDisabled(noteAction, false);

        volumeAction.onclick = openVolumeGenerator;
        chapterAction.onclick = openChapterGenerator;
        contentAction.onclick = openContentGenerator;
        noteAction.onclick = openNoteManager;
    }
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
    window.location.href = '/index.html';
}

function openOutlineBuilder() {
    window.location.href = `outline.html?project_id=${projectId}`;
}

// 大纲构建入口（从新项目页面跳转）
function openNewProjectBuilder() {
    window.location.href = `new_project.html?project_id=${projectId}`;
}

function openTimelineManager() {
    window.location.href = `timeline.html?project_id=${projectId}`;
}

function openVolumeGenerator() {
    window.location.href = `volume.html?project_id=${projectId}`;
}

function openChapterGenerator() {
    window.location.href = `chapter.html?project_id=${projectId}`;
}

function openContentManager() {
    window.location.href = `content.html?project_id=${projectId}`;
}

function openContentGenerator() {
    window.location.href = `content.html?project_id=${projectId}`;
}

function openNoteManager() {
    window.location.href = `note.html?project_id=${projectId}`;
}

// 显示提示信息
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'}"></i>${message}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
    document.body.appendChild(container);
    return container;
}

function editProject() {
    api.get(`/api/projects/${projectId}/`).then(data => {
        if (data.success) {
            document.getElementById('edit-title').value = data.project.title;
            document.getElementById('edit-description').value = data.project.description || '';
            
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
        const data = await api.postForm('/api/title/suggest/', `project_id=${encodeURIComponent(projectId)}`);
        
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
        const data = await api.postForm('/api/description/suggest/', `project_id=${encodeURIComponent(projectId)}`);
        
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

function escapeHtml(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
}

function showToast(msg, type = 'success') {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = `toast-item toast-${type}`;
    t.innerHTML = `<i class="fas ${type==='success'?'fa-check-circle':'fa-exclamation-circle'}"></i>${msg}`;
    c.appendChild(t);
    setTimeout(()=>{ 
        t.style.animation='toastSlideOut 0.3s ease forwards'; 
        setTimeout(()=>t.remove(),300); 
    }, 3000);
}

async function saveProjectEdit() {
    const title = document.getElementById('edit-title').value;
    const description = document.getElementById('edit-description').value;

    const data = await api.postForm(`/api/projects/${projectId}/update/`, `title=${encodeURIComponent(title)}&description=${encodeURIComponent(description)}`);

    if (data.success) {
        location.reload();
    } else {
        alert(data.message || '保存失败');
    }
}

function deleteProject() {
    document.getElementById('confirmModalMessage').textContent = '确定要删除这个项目吗？此操作不可撤销。';
    const confirmModal = new bootstrap.Modal(document.getElementById('confirmModal'));
    confirmModal.show();
    
    document.getElementById('confirmModalBtn').onclick = function() {
        confirmModal.hide();
        api.request(`/api/projects/${projectId}/`, {
            method: 'DELETE'
        }).then(data => {
            if (data.success) {
                window.location.href = '/index.html';
            } else {
                alert(data.message || '删除失败');
            }
        });
    };
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

// ============ 世界观管理 ============

function openWorldviewManager() {
    window.location.href = `worldview.html?project_id=${projectId}`;
}

async function openWorldWorkspace() {
    window.location.href = `worldview.html?project_id=${projectId}`;
}

function showWorldviewForm(worldview = null) {
    document.getElementById('worldviewForm').style.display = 'block';
    if (worldview) {
        document.getElementById('worldview-id').value = worldview.id;
        document.getElementById('worldview-category').value = worldview.category;
        document.getElementById('worldview-title').value = worldview.title;
        document.getElementById('worldview-keywords').value = worldview.keywords || '';
        document.getElementById('worldview-content').value = worldview.content || '';
    } else {
        document.getElementById('worldview-id').value = '';
        document.getElementById('worldview-category').value = 'worldview';
        document.getElementById('worldview-title').value = '';
        document.getElementById('worldview-keywords').value = '';
        document.getElementById('worldview-content').value = '';
    }
}

function hideWorldviewForm() {
    document.getElementById('worldviewForm').style.display = 'none';
}

async function loadWorldviews() {
    try {
        const data = await api.get(`/api/projects/${projectId}/worldviews/`);
        if (data.success) {
            renderWorldviewList(data.worldviews);
        }
    } catch (error) {
        console.error('加载世界观失败:', error);
    }
}

function renderWorldviewList(worldviews) {
    const container = document.getElementById('worldviewList');
    if (!worldviews || worldviews.length === 0) {
        container.innerHTML = '<div class="text-center text-muted py-5"><i class="fas fa-globe fa-3x mb-3"></i><p>暂无世界观设定</p></div>';
        return;
    }

    // 按分类分组
    const grouped = {};
    worldviews.forEach(w => {
        const cat = w.category;
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(w);
    });

    let html = '';
    const categoryNames = {
        'worldview': '世界观',
        'setting': '设定体系',
        'history': '历史背景',
        'culture': '文化风俗',
        'location': '地点场景',
        'rule': '规则设定',
        'plot_foreshadow': '情节伏笔',
        'other': '其他'
    };

    for (const [cat, items] of Object.entries(grouped)) {
        html += `<div class="mb-4">
            <h6 class="text-muted border-bottom pb-2 mb-3"><i class="fas fa-folder me-2"></i>${categoryNames[cat] || cat}</h6>
            <div class="row g-2">`;
        items.forEach(w => {
            html += `<div class="col-md-6">
                <div class="card h-100">
                    <div class="card-body py-2">
                        <div class="d-flex justify-content-between align-items-start">
                            <h6 class="mb-1">${w.title}</h6>
                            <div class="btn-group btn-group-sm">
                                <button class="btn btn-outline-primary" onclick="editWorldview(${w.id})"><i class="fas fa-edit"></i></button>
                                <button class="btn btn-outline-danger" onclick="deleteWorldview(${w.id})"><i class="fas fa-trash"></i></button>
                            </div>
                        </div>
                        ${w.keywords ? `<p class="mb-1 small text-muted">${w.keywords}</p>` : ''}
                        ${w.content ? `<p class="mb-0 small text-secondary" style="display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${w.content}</p>` : ''}
                    </div>
                </div>
            </div>`;
        });
        html += '</div></div>';
    }
    container.innerHTML = html;
}

async function saveWorldview() {
    const id = document.getElementById('worldview-id').value;
    const category = document.getElementById('worldview-category').value;
    const title = document.getElementById('worldview-title').value;
    const keywords = document.getElementById('worldview-keywords').value;
    const content = document.getElementById('worldview-content').value;

    if (!title) {
        alert('请输入标题');
        return;
    }

    const url = id ? `/api/projects/${projectId}/worldviews/${id}/` : `/api/projects/${projectId}/worldviews/`;
    const method = id ? 'PUT' : 'POST';

    try {
        const data = await api.request(url, {
            method: method,
            body: JSON.stringify({ category, title, keywords, content })
        });
        if (data.success) {
            hideWorldviewForm();
            loadWorldviews();
            showToast(id ? '更新成功' : '创建成功', 'success');
        }
    } catch (error) {
        console.error('保存世界观失败:', error);
        showToast('保存失败', 'error');
    }
}

function editWorldview(id) {
    api.get(`/api/projects/${projectId}/worldviews/`).then(data => {
        if (data.success) {
            const worldview = data.worldviews.find(w => w.id === id);
            if (worldview) showWorldviewForm(worldview);
        }
    });
}

function deleteWorldview(id) {
    if (!confirm('确定要删除这个世界观设定吗？')) return;
    api.request(`/api/projects/${projectId}/worldviews/${id}/`, {
        method: 'DELETE'
    }).then(data => {
        if (data.success) {
            loadWorldviews();
            showToast('删除成功', 'success');
        }
    });
}

// ============ 人物管理 ============

function openCharacterManager() {
    window.location.href = `character.html?project_id=${projectId}`;
}

function showCharacterForm(character = null) {
    document.getElementById('characterForm').style.display = 'block';
    if (character) {
        document.getElementById('character-id').value = character.id;
        document.getElementById('character-name').value = character.name;
        document.getElementById('character-role-type').value = character.role_type;
        document.getElementById('character-gender').value = character.gender;
        document.getElementById('character-tagline').value = character.tagline || '';
        document.getElementById('character-appearance').value = character.appearance || '';
        document.getElementById('character-personality').value = character.personality || '';
        document.getElementById('character-backstory').value = character.backstory || '';
        document.getElementById('character-motivation').value = character.motivation || '';
    } else {
        document.getElementById('character-id').value = '';
        document.getElementById('character-name').value = '';
        document.getElementById('character-role-type').value = 'supporting';
        document.getElementById('character-gender').value = 'unknown';
        document.getElementById('character-tagline').value = '';
        document.getElementById('character-appearance').value = '';
        document.getElementById('character-personality').value = '';
        document.getElementById('character-backstory').value = '';
        document.getElementById('character-motivation').value = '';
    }
}

function hideCharacterForm() {
    document.getElementById('characterForm').style.display = 'none';
}

async function loadCharacters() {
    try {
        const data = await api.get(`/api/projects/${projectId}/characters/`);
        if (data.success) {
            renderCharacterList(data.characters);
        }
    } catch (error) {
        console.error('加载人物失败:', error);
    }
}

function renderCharacterList(characters) {
    const container = document.getElementById('characterList');
    if (!characters || characters.length === 0) {
        container.innerHTML = '<div class="text-center text-muted py-5"><i class="fas fa-users fa-3x mb-3"></i><p>暂无人物</p></div>';
        return;
    }

    const roleIcons = {
        'protagonist': 'fa-star',
        'supporting': 'fa-user',
        'antagonist': 'fa-skull',
        'minor': 'fa-user-circle',
        'narrator': 'fa-comment'
    };
    const roleColors = {
        'protagonist': 'warning',
        'supporting': 'primary',
        'antagonist': 'danger',
        'minor': 'secondary',
        'narrator': 'info'
    };

    let html = '<div class="table-responsive"><table class="table table-hover align-middle mb-0"><thead><tr><th>姓名</th><th>类型</th><th>性别</th><th>性格</th><th>签名</th><th style="width: 100px;">操作</th></tr></thead><tbody>';
    characters.forEach(c => {
        html += `<tr>
            <td><strong>${c.name}</strong></td>
            <td><span class="badge bg-${roleColors[c.role_type] || 'secondary'}"><i class="fas ${roleIcons[c.role_type] || 'fa-user'} me-1"></i>${c.role_type_display}</span></td>
            <td>${c.gender_display}</td>
            <td><small class="text-muted">${c.personality || '-'}</small></td>
            <td><small>${c.tagline || '-'}</small></td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary" onclick="editCharacter(${c.id})" title="编辑"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-outline-danger" onclick="deleteCharacter(${c.id})" title="删除"><i class="fas fa-trash"></i></button>
                </div>
            </td>
        </tr>`;
    });
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

async function saveCharacter() {
    const id = document.getElementById('character-id').value;
    const name = document.getElementById('character-name').value;
    const role_type = document.getElementById('character-role-type').value;
    const gender = document.getElementById('character-gender').value;
    const tagline = document.getElementById('character-tagline').value;
    const appearance = document.getElementById('character-appearance').value;
    const personality = document.getElementById('character-personality').value;
    const backstory = document.getElementById('character-backstory').value;
    const motivation = document.getElementById('character-motivation').value;

    if (!name) {
        alert('请输入姓名');
        return;
    }

    const url = id ? `/api/projects/${projectId}/characters/${id}/` : `/api/projects/${projectId}/characters/`;
    const method = id ? 'PUT' : 'POST';

    try {
        const data = await api.request(url, {
            method: method,
            body: JSON.stringify({ name, role_type, gender, tagline, appearance, personality, backstory, motivation })
        });
        if (data.success) {
            hideCharacterForm();
            loadCharacters();
            showToast(id ? '更新成功' : '创建成功', 'success');
        }
    } catch (error) {
        console.error('保存人物失败:', error);
        showToast('保存失败', 'error');
    }
}

function editCharacter(id) {
    api.get(`/api/projects/${projectId}/characters/`).then(data => {
        if (data.success) {
            const character = data.characters.find(c => c.id === id);
            if (character) showCharacterForm(character);
        }
    });
}

function deleteCharacter(id) {
    if (!confirm('确定要删除这个人物吗？')) return;
    api.request(`/api/projects/${projectId}/characters/${id}/`, {
        method: 'DELETE'
    }).then(data => {
        if (data.success) {
            loadCharacters();
            showToast('删除成功', 'success');
        }
    });
}