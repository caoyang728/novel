let projectId = null;

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    const params = new URLSearchParams(window.location.search);
    projectId = params.get('id');
    
    if (projectId) {
        loadProjectInfo();
        loadProjectStats();
    } else {
        window.location.href = '/index.html';
    }
    
    // 返回书架按钮点击事件
    const backButton = document.getElementById('backButton');
    if (backButton) {
        backButton.addEventListener('click', goBack);
    }
});

async function checkAuth() {
    try {
        const response = await fetch('/api/auth/user/', {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (!data.success) {
            window.location.href = '/login.html';
        }
    } catch (error) {
        window.location.href = '/login.html';
    }
}

async function loadProjectInfo() {
    try {
        const response = await fetch(`/api/projects/${projectId}/`, {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (data.success) {
            const project = data.project;
            document.getElementById('project-title').textContent = project.title;
            document.getElementById('project-description').textContent = project.description || '暂无描述';
        }
    } catch (error) {
        console.error('Failed to load project info:', error);
    }
}

async function loadProjectStats() {
    try {
        const response = await fetch(`/api/projects/${projectId}/stats/`, {
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
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
    window.location.href = `outline_builder.html?project_id=${projectId}`;
}

function openVolumeGenerator() {
    window.location.href = `volume_generator.html?project_id=${projectId}`;
}

function openChapterGenerator() {
    window.location.href = `chapter_generator.html?project_id=${projectId}`;
}

function openContentManager() {
    window.location.href = `content_manager.html?project_id=${projectId}`;
}

function editProject() {
    fetch(`/api/projects/${projectId}/`, {
        headers: { 'X-CSRFToken': getCookie('csrftoken') }
    }).then(res => res.json()).then(data => {
        if (data.success) {
            document.getElementById('edit-title').value = data.project.title;
            document.getElementById('edit-description').value = data.project.description || '';
            
            // 隐藏之前的推荐
            const suggestionsContainer = document.getElementById('title-suggestions-container');
            if (suggestionsContainer) {
                suggestionsContainer.style.display = 'none';
            }
            
            const modal = new bootstrap.Modal(document.getElementById('editProjectModal'));
            modal.show();
            
            setTimeout(() => {
                const btn = document.getElementById('ai-generate-btn');
                if (btn) {
                    console.log('AI生成按钮已找到，绑定事件');
                    btn.onclick = generateProjectInfo;
                } else {
                    console.error('AI生成按钮未找到');
                }
            }, 100);
        }
    });
}

function selectTitle(title) {
    document.getElementById('edit-title').value = title;
}

async function generateProjectInfo() {
    console.log('AI生成按钮被点击');
    const generateBtn = document.getElementById('ai-generate-btn');
    
    if (!generateBtn) {
        console.error('找不到AI生成按钮');
        alert('页面加载错误，请刷新页面重试');
        return;
    }
    
    if (!projectId) {
        console.error('projectId为空');
        alert('项目ID不存在，请刷新页面重试');
        return;
    }
    
    console.log('projectId:', projectId);
    
    const originalText = generateBtn.innerHTML;
    
    generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
    generateBtn.disabled = true;
    
    try {
        console.log('正在发起API请求...');
        const response = await fetch('/api/ai/project/info/generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: `project_id=${encodeURIComponent(projectId)}`
        });
        
        console.log('API响应状态:', response.status);
        const data = await response.json();
        console.log('API响应数据:', data);
        
        if (data.success) {
            // 填充描述
            document.getElementById('edit-description').value = data.description;
            
            // 处理项目名称推荐
            const suggestionsContainer = document.getElementById('title-suggestions-container');
            const suggestionsList = document.getElementById('title-suggestions-list');
            
            if (data.titles && data.titles.length > 0) {
                // 显示推荐区域
                suggestionsContainer.style.display = 'block';
                
                // 清空之前的推荐
                suggestionsList.innerHTML = '';
                
                // 添加新的推荐
                data.titles.forEach((title, index) => {
                    const item = document.createElement('div');
                    item.className = 'title-suggestion-item';
                    item.innerHTML = `<i class="fas fa-hand-pointer"></i><span>${title}</span>`;
                    item.onclick = () => selectTitle(title);
                    suggestionsList.appendChild(item);
                });
                
                // 默认选中第一个
                document.getElementById('edit-title').value = data.titles[0];
            } else if (data.title) {
                // 兼容单个标题的情况
                document.getElementById('edit-title').value = data.title;
                suggestionsContainer.style.display = 'none';
            }
            
            console.log('成功填充项目信息');
        } else {
            alert(data.message || '生成失败');
        }
    } catch (error) {
        console.error('生成项目信息失败:', error);
        alert('生成失败，请重试');
    } finally {
        generateBtn.innerHTML = originalText;
        generateBtn.disabled = false;
    }
}

async function saveProjectEdit() {
    const title = document.getElementById('edit-title').value;
    const description = document.getElementById('edit-description').value;

    const response = await fetch(`/api/projects/${projectId}/update/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: `title=${encodeURIComponent(title)}&description=${encodeURIComponent(description)}`
    });

    const data = await response.json();
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
        fetch(`/api/projects/${projectId}/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        }).then(res => res.json()).then(data => {
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