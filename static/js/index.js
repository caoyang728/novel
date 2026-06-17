document.addEventListener('DOMContentLoaded', function() {
    showLoading('加载中...');
    Promise.all([loadUserInfo(), loadProjects()]).finally(() => hideLoading());
});

async function loadUserInfo() {
    // 如果未登录，直接显示登录弹窗，登录成功后重新加载数据
    if (!api.isAuthenticated()) {
        showLoginModal(() => {
            loadUserInfo();
            loadProjects();
        });
        return;
    }

    try {
        const data = await api.get('/api/auth/user/');
        if (data && data.success) {
            document.getElementById('username').textContent = data.user.username;
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
    }

    try {
        const data = await api.get('/api/token-usage/today/');
        if (data && data.success) {
            const total = data.usage.total_tokens || 0;
            document.getElementById('token-usage').textContent = '今日 Token: ' + formatTokenCount(total);
        }
    } catch (error) {
        console.error('Failed to load token usage:', error);
    }
}

async function loadProjects() {
    // 如果未登录，不加载项目，登录弹窗已经显示
    if (!api.isAuthenticated()) {
        return;
    }

    try {
        const data = await api.get('/api/projects/');
        if (data) {
            renderProjects(data.projects || []);
        }
    } catch (error) {
        console.error('Failed to load projects:', error);
        document.getElementById('projects-container').innerHTML = `
            <div class="col-md-12">
                <div class="empty-state">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>加载项目失败</p>
                </div>
            </div>
        `;
    }
}

function renderProjects(projects) {
    const container = document.getElementById('projects-container');

    if (projects.length === 0) {
        container.innerHTML = `
            <div class="col-md-12">
                <div class="empty-state">
                    <i class="fas fa-book-open"></i>
                    <p>暂无项目，点击上方按钮创建</p>
                </div>
            </div>
        `;
        return;
    }

    // 按更新时间倒排序
    projects.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));

    container.innerHTML = projects.map(project => `
            <div class="project-card" onclick="openProjectByVersion(${project.id}, ${project.version_count || 0}, ${project.latest_version_number || 0})" data-project='${JSON.stringify(project)}'>
                <div class="project-card-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <h3>${project.title}</h3>
                        <span class="badge ${getStatusBadgeClass(project.status)}">${getStatusText(project.status)}</span>
                    </div>
                </div>
                <div class="project-card-body">
                    <p>${project.description || '暂无描述'}</p>
                </div>
                <div class="project-card-footer">
                    <span class="status">更新于 ${formatDate(project.updated_at)}</span>
                    <div class="actions">
                        <button class="btn-outline-primary btn-sm" onclick="event.stopPropagation(); editProject(${project.id})">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn-outline-danger btn-sm" onclick="event.stopPropagation(); deleteProject(${project.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
    `).join('');
}

function getStatusBadgeClass(status) {
    const classes = {
        'outline_building': 'badge-primary',
        'outline_built': 'badge-info',
        'writing': 'badge-warning',
        'completed': 'badge-success'
    };
    return classes[status] || 'badge-secondary';
}

function getStatusText(status) {
    const texts = {
        'outline_building': '大纲构建中',
        'outline_built': '大纲已构建',
        'writing': '创作中',
        'completed': '已完成'
    };
    return texts[status] || status;
}

// 根据版本数量决定跳转页面
function openProjectByVersion(projectId, versionCount, latestVersionNumber) {
    window.location.href = `project.html?project_id=${projectId}`;
}


async function deleteProject(projectId) {
    const confirmModal = document.createElement('div');
    confirmModal.className = 'dialog-overlay';
    confirmModal.id = 'deleteConfirmModal';
    confirmModal.innerHTML = `
        <div class="dialog" style="max-width: 450px;">
            <div class="dialog-header">
                <h5><i class="fas fa-exclamation-triangle text-warning me-2"></i>确认删除</h5>
                <button class="btn-close" onclick="closeDeleteConfirmModal()"><i class="fas fa-times"></i></button>
            </div>
            <div class="dialog-body">
                <p>删除项目后将无法恢复，确定要继续吗？</p>
            </div>
            <div class="dialog-footer">
                <button class="btn-cancel" onclick="closeDeleteConfirmModal()">取消</button>
                <button class="btn-danger" onclick="showDeleteConfirmStep2(${projectId})">确认</button>
            </div>
        </div>
    `;
    document.body.appendChild(confirmModal);
    confirmModal.classList.add('show');
}

function closeDeleteConfirmModal() {
    const modal = document.getElementById('deleteConfirmModal');
    if (modal) {
        modal.remove();
    }
}

function showDeleteConfirmStep2(projectId) {
    closeDeleteConfirmModal();

    const confirmModal = document.createElement('div');
    confirmModal.className = 'dialog-overlay';
    confirmModal.id = 'deleteConfirmModal';
    confirmModal.innerHTML = `
        <div class="dialog" style="max-width: 450px;">
            <div class="dialog-header">
                <h5><i class="fas fa-trash text-danger me-2"></i>二次确认</h5>
                <button class="btn-close" onclick="closeDeleteConfirmModal()"><i class="fas fa-times"></i></button>
            </div>
            <div class="dialog-body">
                <p>请输入 <strong>"确认删除"</strong> 以确认操作：</p>
                <input type="text" id="delete-confirm-input" class="form-control mt-3" placeholder="请输入确认文字">
            </div>
            <div class="dialog-footer">
                <button class="btn-cancel" onclick="closeDeleteConfirmModal()">取消</button>
                <button class="btn-danger" onclick="confirmDeleteProject(${projectId})">删除</button>
            </div>
        </div>
    `;
    document.body.appendChild(confirmModal);
    confirmModal.classList.add('show');
}

async function confirmDeleteProject(projectId) {
    const input = document.getElementById('delete-confirm-input');
    if (input && input.value.trim() === '确认删除') {
        try {
            const data = await api.post(`/api/projects/${projectId}/delete/`, {});
            closeDeleteConfirmModal();
            if (data.success) {
                loadProjects();
            } else {
                showError(data.message || '删除失败');
            }
        } catch (error) {
            closeDeleteConfirmModal();
            showError('网络错误，请重试');
        }
    } else {
        showError('请输入正确的确认文字');
    }
}

let editingProjectId = null;


function getProjectData(projectId) {
    const projectCards = document.querySelectorAll('.project-card');
    for (let card of projectCards) {
        const project = JSON.parse(card.dataset.project || '{}');
        if (project.id === projectId) {
            return project;
        }
    }
    return null;
}

function closeEditProjectModal() {
    document.getElementById('editProjectModal').classList.remove('show');
    editingProjectId = null;
}

async function saveProjectEdit() {
    const title = document.getElementById('edit-project-title').value.trim();
    const description = document.getElementById('edit-project-description').value.trim();

    if (!title) {
        showError('请输入项目名称');
        return;
    }

    try {
        const data = await api.put(`/api/projects/${editingProjectId}/`, { title, description });
        if (data.success) {
            closeEditProjectModal();
            loadProjects();
        } else {
            showError(data.message || '更新失败');
        }
    } catch (error) {
        showError('网络错误，请重试');
    }
}


function openCreateProjectModal() {
    document.getElementById('create-project-title').value = '';
    document.getElementById('create-project-description').value = '';
    document.getElementById('ai-enhance-btn').disabled = true;
    document.getElementById('createProjectModal').classList.add('show');
}

function closeCreateProjectModal() {
    document.getElementById('createProjectModal').classList.remove('show');
}

document.getElementById('create-project-description').addEventListener('input', function() {
    const hasDescription = this.value.trim().length > 0;
    document.getElementById('ai-enhance-btn').disabled = !hasDescription;
});

async function confirmCreateProject() {
    const title = document.getElementById('create-project-title').value.trim();
    const description = document.getElementById('create-project-description').value.trim();

    if (!title) {
        showError('请输入书名');
        return;
    }

    try {
        const data = await api.post('/api/projects/create/', { title, description });
        if (data.success) {
            closeCreateProjectModal();
            loadProjects();
        } else {
            showError(data.error || '创建失败');
        }
    } catch (error) {
        showError('网络错误，请重试');
    }
}

async function aiEnhanceCreateProject() {
    const description = document.getElementById('create-project-description').value.trim();
    const title = document.getElementById('create-project-title').value.trim();

    if (!description) {
        showError('请先输入描述内容');
        return;
    }

    const btn = document.getElementById('ai-enhance-btn');
    const originalText = btn.innerHTML;
    const titleInput = document.getElementById('create-project-title');
    const descriptionInput = document.getElementById('create-project-description');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>完善中...';

    showLoading('AI正在完善描述...');

    try {
        const data = await api.post('/api/projects/description-optimization/', {
            title: title,
            description: description
        });

        if (data.success) {
            if (data.title) {
                titleInput.value = data.title;
            }
            if (data.description) {
                descriptionInput.value = data.description;
            }
            showSuccess('AI完善成功');
        } else {
            showError(data.error || 'AI完善失败');
        }
    } catch (error) {
        console.error('AI完善失败:', error);
        showError(error.message || '网络错误，请重试');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

let editingProjectData = null;

function editProject(projectId) {
    const project = getProjectData(projectId);
    if (project) {
        editingProjectId = projectId;
        editingProjectData = project;
        document.getElementById('edit-project-title').value = project.title;
        document.getElementById('edit-project-description').value = project.description || '';
        document.getElementById('editProjectModal').classList.add('show');
    }
}

async function aiEnhanceEditProject() {
    if (!editingProjectId || !editingProjectData) {
        showError('项目信息加载失败');
        return;
    }

    const description = document.getElementById('edit-project-description').value.trim();
    const title = document.getElementById('edit-project-title').value.trim();

    if (!description) {
        showError('请先输入描述内容');
        return;
    }

    const btn = document.getElementById('ai-enhance-edit-btn');
    const originalText = btn.innerHTML;
    const titleInput = document.getElementById('edit-project-title');
    const descriptionInput = document.getElementById('edit-project-description');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>完善中...';

    showLoading('AI正在完善描述...');

    try {
        const data = await api.post(`/api/projects/${editingProjectId}/description-optimization/`, {
            title: title,
            description: description
        });

        if (data.success) {
            if (data.title) {
                titleInput.value = data.title;
            }
            if (data.description) {
                descriptionInput.value = data.description;
            }
            showSuccess('AI完善成功');
        } else {
            showError(data.error || 'AI完善失败');
        }
    } catch (error) {
        console.error('AI完善失败:', error);
        showError(error.message || '网络错误，请重试');
    } finally {
        hideLoading();
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
