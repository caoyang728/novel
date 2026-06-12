const projectId = new URLSearchParams(window.location.search).get('project_id');

document.addEventListener('DOMContentLoaded', function() {
    initBackToProjectButton('.back-btn');
    loadProjectInfo();
    loadOutlineVersions();
});

document.getElementById('outline-tab').addEventListener('click', function() {
    loadOutlineVersions();
});
document.getElementById('volume-tab').addEventListener('click', function() {
    loadVolumeVersions();
});
document.getElementById('chapter-tab').addEventListener('click', function() {
    loadChapters();
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
        const container = document.getElementById('outline-list');
        if (data.versions.length === 0) {
            container.innerHTML = '<div class="text-center py-4 text-muted">暂无大纲版本</div>';
            return;
        }
        container.innerHTML = data.versions.map(v => `
            <div class="content-card" onclick="loadOutlineContent(${v.id})">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="fw-medium">v${v.version_number}</span>
                        ${v.is_finalized ? '<span class="badge-success ms-2">定稿</span>' : ''}
                    </div>
                    <small class="text-muted">${formatDate(v.updated_at)}</small>
                </div>
            </div>
        `).join('');
    }
}

async function loadOutlineContent(id) {
    document.querySelectorAll('#outline-list .content-card').forEach(el => el.classList.remove('active'));
    event.currentTarget?.classList.add('active');
    
    const data = await api.get(`/api/outline/version/${id}/`);
    if (data.success) {
        const content = data.content || '<p class="text-muted">空内容</p>';
        document.getElementById('outline-preview').innerHTML = safeMarkdownParse(content);
    }
}

async function loadVolumeVersions() {
    const data = await api.get(`/api/projects/${projectId}/volume/versions/`);
    if (data.success) {
        const container = document.getElementById('volume-list');
        if (data.versions.length === 0) {
            container.innerHTML = '<div class="text-center py-4 text-muted">暂无卷版本</div>';
            return;
        }
        container.innerHTML = data.versions.map(v => `
            <div class="content-card" onclick="loadVolumeContent(${v.id})">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="fw-medium">v${v.version_number}</span>
                        ${v.is_finalized ? '<span class="badge-success ms-2">定稿</span>' : ''}
                    </div>
                    <small class="text-muted">${formatDate(v.updated_at)}</small>
                </div>
            </div>
        `).join('');
    }
}

async function loadVolumeContent(id) {
    document.querySelectorAll('#volume-list .content-card').forEach(el => el.classList.remove('active'));
    event.currentTarget?.classList.add('active');
    
    const data = await api.get(`/api/volume/version/${id}/`);
    if (data.success) {
        const content = data.content || '<p class="text-muted">空内容</p>';
        document.getElementById('volume-preview').innerHTML = safeMarkdownParse(content);
    }
}

async function loadChapters() {
    const data = await api.get(`/api/projects/${projectId}/chapters/`);
    if (data.success) {
        const container = document.getElementById('chapter-list');
        if (data.chapters.length === 0) {
            container.innerHTML = '<div class="text-center py-4 text-muted">暂无章节</div>';
            return;
        }
        container.innerHTML = data.chapters.map(c => `
            <div class="content-card" onclick="loadChapterContent(${c.id})">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="fw-medium">第${c.chapter_number}章 ${c.title}</span>
                    </div>
                    <small class="text-muted">${formatDate(c.updated_at)}</small>
                </div>
            </div>
        `).join('');
    }
}

async function loadChapterContent(id) {
    document.querySelectorAll('#chapter-list .content-card').forEach(el => el.classList.remove('active'));
    event.currentTarget?.classList.add('active');
    
    const data = await api.get(`/api/chapters/${id}/`);
    if (data.success) {
        const content = data.content || '<p class="text-muted">空内容</p>';
        document.getElementById('chapter-preview').innerHTML = safeMarkdownParse(content);
    }
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
