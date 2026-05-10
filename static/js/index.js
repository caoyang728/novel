document.addEventListener('DOMContentLoaded', function() {
    loadUserInfo();
    loadProjects();
});

async function loadUserInfo() {
    try {
        const response = await fetch('/api/auth/user/', {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success) {
            document.getElementById('username').textContent = data.user.username;
        }
    } catch (error) {
        console.error('Failed to load user info:', error);
        window.location.href = 'login.html';
    }
    
    try {
        const response = await fetch('/api/token-usage/today/', {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
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
        const response = await fetch('/api/projects/', {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
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
            <div class="project-card" onclick="openProject(${project.id})" data-project='${JSON.stringify(project)}'>
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
        'draft': 'badge-info',
        'writing': 'badge-warning',
        'completed': 'badge-success'
    };
    return classes[status] || 'badge-secondary';
}

function getStatusText(status) {
    const texts = {
        'draft': '构思中',
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
    window.location.href = `project.html?id=${projectId}`;
}

function openAddProjectModal() {
    document.getElementById('addProjectModal').classList.add('show');
    document.getElementById('project-title').value = '';
    document.getElementById('project-description').value = '';
}

function closeAddProjectModal() {
    document.getElementById('addProjectModal').classList.remove('show');
}

async function createProject() {
    const title = document.getElementById('project-title').value.trim();
    const description = document.getElementById('project-description').value.trim();
    
    if (!title) {
        alert('请输入项目名称');
        return;
    }

    try {
        const response = await fetch('/api/projects/create/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ title, description })
        });
        
        const data = await response.json();
        if (data.success) {
            closeAddProjectModal();
            loadProjects();
        } else {
            alert(data.message || '创建失败');
        }
    } catch (error) {
        alert('网络错误，请重试');
    }
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
            const response = await fetch(`/api/projects/${projectId}/delete/`, {
                method: 'DELETE',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });
            
            const data = await response.json();
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
        const response = await fetch(`/api/projects/${editingProjectId}/update/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ title, description })
        });
        
        const data = await response.json();
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
        await fetch('/api/auth/logout/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        window.location.href = 'login.html';
    } catch (error) {
        console.error('Logout failed:', error);
        window.location.href = 'login.html';
    }
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