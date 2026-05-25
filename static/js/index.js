document.addEventListener('DOMContentLoaded', function() {
    loadUserInfo();
    loadProjects();
});

async function loadUserInfo() {
    try {
        const data = await api.get('/api/auth/user/');
        if (data.success) {
            document.getElementById('username').textContent = data.user.username;
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
        // 重定向交给 common.js 中的 request 函数处理
    }

    try {
        const data = await api.get('/api/token-usage/today/');
        if (data.success) {
            const total = data.usage.total_tokens || 0;
            const formatted = total >= 1000 ? (total / 1000).toFixed(1) + 'k' : total;
            document.getElementById('token-usage').textContent = '今日 Token: ' + formatted;
        }
    } catch (error) {
        console.error('Failed to load token usage:', error);
    }
}

async function loadProjects() {
    try {
        const data = await api.get('/api/projects/');
        renderProjects(data.projects || []);
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

    container.innerHTML = projects.map(project => `
        <div class="col-md-4">
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
                        <button class="btn btn-outline-primary btn-sm" onclick="event.stopPropagation(); editProject(${project.id})">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-sm" onclick="event.stopPropagation(); deleteProject(${project.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
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

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN');
}

function openProject(projectId) {
    window.location.href = `project.html?project_id=${projectId}`;
}

// 根据版本数量决定跳转页面
function openProjectByVersion(projectId, versionCount, latestVersionNumber) {
    // 如果最新版本号为0（尚未构建大纲），进入project.html显示"大纲构建"
    // 其他情况进入project.html显示"大纲优化"
    window.location.href = `project.html?project_id=${projectId}`;
}

// 直接进入项目编辑页面（大纲构建）
function openProjectToNewProject(projectId) {
    window.location.href = `new_project.html?project_id=${projectId}`;
}

async function deleteProject(projectId) {
    const confirmModal = document.createElement('div');
    confirmModal.className = 'custom-modal-overlay';
    confirmModal.id = 'deleteConfirmModal';
    confirmModal.innerHTML = `
        <div class="custom-modal" style="max-width: 450px;">
            <div class="custom-modal-header">
                <h5><i class="fas fa-exclamation-triangle text-warning me-2"></i>确认删除</h5>
            </div>
            <div class="custom-modal-body">
                <p>删除项目后将无法恢复，确定要继续吗？</p>
            </div>
            <div class="custom-modal-footer">
                <button class="btn btn-secondary" onclick="closeDeleteConfirmModal()">取消</button>
                <button class="btn btn-danger" onclick="showDeleteConfirmStep2(${projectId})">确认</button>
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
    confirmModal.className = 'custom-modal-overlay';
    confirmModal.id = 'deleteConfirmModal';
    confirmModal.innerHTML = `
        <div class="custom-modal" style="max-width: 450px;">
            <div class="custom-modal-header">
                <h5><i class="fas fa-trash text-danger me-2"></i>二次确认</h5>
            </div>
            <div class="custom-modal-body">
                <p>请输入 <strong>"确认删除"</strong> 以确认操作：</p>
                <input type="text" id="delete-confirm-input" class="form-control mt-3" placeholder="请输入确认文字">
            </div>
            <div class="custom-modal-footer">
                <button class="btn btn-secondary" onclick="closeDeleteConfirmModal()">取消</button>
                <button class="btn btn-danger" onclick="confirmDeleteProject(${projectId})">删除</button>
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
                alert(data.message || '删除失败');
            }
        } catch (error) {
            closeDeleteConfirmModal();
            alert('网络错误，请重试');
        }
    } else {
        alert('请输入正确的确认文字');
    }
}

let editingProjectId = null;

function editProject(projectId) {
    const project = getProjectData(projectId);
    if (project) {
        editingProjectId = projectId;
        document.getElementById('edit-project-title').value = project.title;
        document.getElementById('edit-project-description').value = project.description || '';
        document.getElementById('editProjectModal').classList.add('show');
    }
}

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
        alert('请输入项目名称');
        return;
    }

    try {
        const data = await api.post(`/api/projects/${editingProjectId}/update/`, { title, description });
        if (data.success) {
            closeEditProjectModal();
            loadProjects();
        } else {
            alert(data.message || '更新失败');
        }
    } catch (error) {
        alert('网络错误，请重试');
    }
}

async function logout() {
    try {
        await api.post('/logout/', {});
    } catch (error) {
        console.error('Logout failed:', error);
    }
    api.logout();
}