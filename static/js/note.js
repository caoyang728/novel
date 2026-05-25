let currentProjectId = null;
let currentNoteId = null;
let originalContent = '';
let originalTitle = '';
let isEditMode = false;

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    const urlParams = new URLSearchParams(window.location.search);
    currentProjectId = urlParams.get('project_id');

    if (currentProjectId) {
        loadProjectInfo();
        loadNotes();
    } else {
        window.location.href = '/index.html';
    }
});

async function checkAuth() {
    try {
        const data = await api.get('/api/auth/user/');
        if (!data.success) {
        }
    } catch (error) {
    }
}

async function loadProjectInfo() {
    try {
        const data = await api.get(`/api/projects/${currentProjectId}/`);
        if (data.success) {
            document.getElementById('project-title').textContent = data.project.title || '未知项目';
        }
    } catch (error) {
        console.error('加载项目信息失败:', error);
    }
}

async function loadNotes() {
    if (!currentProjectId) return;

    try {
        const data = await api.get(`/api/projects/${currentProjectId}/notes/`);

        if (data.success) {
            renderNotes(data.data);
        }
    } catch (error) {
        console.error('加载随手记失败:', error);
    }
}

function renderNotes(notes) {
    const notesList = document.getElementById('notes-list');

    if (!notes || notes.length === 0) {
        notesList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-feather"></i>
                <p>暂无随手记</p>
                <p class="hint">点击上方按钮添加</p>
            </div>
        `;
        return;
    }

    notesList.innerHTML = notes.map(note => `
        <div class="note-item" data-note-id="${note.id}" onclick="selectNote(${note.id})">
            <div class="note-item-title">${escapeHtml(note.title)}</div>
            <div class="note-item-content">${escapeHtml(note.content)}</div>
            <div class="note-item-footer">
                <span>${note.created_at}</span>
                <span class="status-badge status-${note.status}">${note.status_display}</span>
            </div>
        </div>
    `).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function selectNote(noteId) {
    currentNoteId = noteId;

    document.querySelectorAll('.note-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-note-id="${noteId}"]`).classList.add('active');

    try {
        const data = await api.get(`/api/projects/${currentProjectId}/notes/${noteId}/`);

        if (data.success) {
            showNoteDetail(data.note);
        }
    } catch (error) {
        console.error('加载笔记详情失败:', error);
    }
}

function showNoteDetail(note) {
    document.getElementById('placeholder-content').style.display = 'none';
    document.getElementById('note-editor').style.display = 'flex';

    document.getElementById('note-title').value = note.title;
    document.getElementById('note-content-textarea').value = note.content;
    document.getElementById('status-select').value = note.status;
    
    const updateTimeEl = document.querySelector('.title-section .update-time');
    updateTimeEl.innerHTML = `<i class="far fa-clock"></i> ${note.updated_at}`;

    originalContent = note.content;
    originalTitle = note.title;
    isEditMode = false;

    document.getElementById('note-title').disabled = true;
    document.getElementById('note-content-textarea').disabled = true;
    document.getElementById('status-select').disabled = true;
    document.getElementById('btn-edit').disabled = false;
    document.getElementById('btn-delete').disabled = false;
    document.getElementById('btn-ai-footer').disabled = true;
    document.getElementById('btn-save').style.display = 'none';
    document.getElementById('btn-cancel').style.display = 'none';

    updateWordCount();
}

function enterEditMode() {
    isEditMode = true;
    
    document.getElementById('note-title').disabled = false;
    document.getElementById('note-content-textarea').disabled = false;
    document.getElementById('btn-edit').disabled = true;
    document.getElementById('btn-delete').disabled = true;
    document.getElementById('btn-ai-footer').disabled = false;
    document.getElementById('btn-save').style.display = 'inline-flex';
    document.getElementById('btn-cancel').style.display = 'inline-flex';

    document.getElementById('note-content-textarea').focus();
}

function cancelEdit() {
    isEditMode = false;
    
    document.getElementById('note-title').value = originalTitle;
    document.getElementById('note-content-textarea').value = originalContent;

    document.getElementById('note-title').disabled = true;
    document.getElementById('note-content-textarea').disabled = true;
    document.getElementById('btn-edit').disabled = false;
    document.getElementById('btn-delete').disabled = false;
    document.getElementById('btn-ai-footer').disabled = true;
    document.getElementById('btn-save').style.display = 'none';
    document.getElementById('btn-cancel').style.display = 'none';
    
    updateWordCount();
}

async function saveNote() {
    const title = document.getElementById('note-title').value;
    const content = document.getElementById('note-content-textarea').value;

    if (!content.trim()) {
        alert('内容不能为空');
        return;
    }

    try {
        const data = await api.put(`/api/projects/${currentProjectId}/notes/${currentNoteId}/`, { title, content });

        if (data.success) {
            isEditMode = false;
            originalContent = content;
            originalTitle = title;

            document.getElementById('note-title').disabled = true;
            document.getElementById('note-content-textarea').disabled = true;
            document.getElementById('btn-edit').disabled = false;
            document.getElementById('btn-delete').disabled = false;
            document.getElementById('btn-ai-footer').disabled = true;
            document.getElementById('btn-save').style.display = 'none';
            document.getElementById('btn-cancel').style.display = 'none';

            const updateTimeEl = document.querySelector('.title-section .update-time');
            updateTimeEl.innerHTML = `<i class="far fa-clock"></i> ${data.note.updated_at}`;

            loadNotes();
        } else {
            alert('保存失败: ' + data.error);
        }
    } catch (error) {
        console.error('保存失败:', error);
        alert('保存失败');
    }
}

function updateStatus() {
    if (!currentNoteId) return;

    const status = document.getElementById('status-select').value;

    api.put(`/api/projects/${currentProjectId}/notes/${currentNoteId}/`, { status })
        .then(data => {
            if (data.success) {
                loadNotes();
            }
        })
        .catch(error => {
            console.error('更新状态失败:', error);
        });
}

async function aiPolishInEditMode() {
    if (!isEditMode) {
        alert('请先进入编辑模式');
        return;
    }
    
    if (!currentNoteId) return;

    const btnAi = document.getElementById('btn-ai-footer');
    const originalHtml = btnAi.innerHTML;
    btnAi.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 优化中...';
    btnAi.disabled = true;

    const TITLE_START = '════TITLE_START════';
    const TITLE_END = '════TITLE_END════';
    const CONTENT_START = '════CONTENT_START════';
    const CONTENT_END = '════CONTENT_END════';

    let streamingBuffer = '';
    let titleComplete = false;
    let contentComplete = false;
    let finalContent = '';

    try {
        const token = api.getToken();
        // 获取当前编辑的内容
        const currentContent = document.getElementById('note-content-textarea').value;
        const response = await fetch(`/api/projects/${currentProjectId}/notes/${currentNoteId}/polish/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ content: currentContent })
        });

        if (!response.ok) {
            if (response.status === 401) {
                alert('登录已过期，请重新登录');
                window.location.href = '/login.html';
                return;
            }
            throw new Error('请求失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'chunk') {
                            const chunkContent = data.content || '';
                            streamingBuffer += chunkContent;
                            
                            if (!titleComplete) {
                                const titleStartIdx = streamingBuffer.indexOf(TITLE_START);
                                if (titleStartIdx !== -1) {
                                    const afterTitleStart = streamingBuffer.substring(titleStartIdx + TITLE_START.length);
                                    const titleEndIdx = afterTitleStart.indexOf(TITLE_END);

                                    if (titleEndIdx !== -1) {
                                        const titleContent = afterTitleStart.substring(0, titleEndIdx).trim();
                                        document.getElementById('note-title').value = titleContent;
                                        titleComplete = true;
                                    }
                                }
                            }
                        } else if (data.type === 'complete') {
                            // 更新时间显示
                            if (data.updated_at) {
                                const updateTimeEl = document.querySelector('.title-section .update-time');
                                updateTimeEl.innerHTML = `<i class="far fa-clock"></i> ${data.updated_at}`;
                            }
                            
                            // 解析最终内容
                            const contentStartIdx = streamingBuffer.indexOf(CONTENT_START);
                            const contentEndIdx = streamingBuffer.indexOf(CONTENT_END);
                            
                            if (contentStartIdx !== -1 && contentEndIdx !== -1) {
                                finalContent = streamingBuffer.substring(contentStartIdx + CONTENT_START.length, contentEndIdx).trim();
                                // 使用打字机效果
                                typewriterEffect(finalContent);
                            }
                        } else if (data.type === 'error') {
                            alert('AI优化失败: ' + data.message);
                        }
                    } catch (e) {
                        console.error('解析数据失败:', e);
                    }
                }
            }
        }

    } catch (error) {
        console.error('AI优化失败:', error);
        alert('AI优化失败');
    } finally {
        btnAi.innerHTML = originalHtml;
        btnAi.disabled = false;
    }
}

function typewriterEffect(text) {
    const textarea = document.getElementById('note-content-textarea');
    let index = 0;
    
    clearInterval(window.currentTypewriter);
    
    textarea.value = '';
    updateWordCount();
    
    window.currentTypewriter = setInterval(() => {
        if (index < text.length) {
            textarea.value += text[index];
            index++;
            updateWordCount();
            textarea.scrollTop = textarea.scrollHeight;
        } else {
            clearInterval(window.currentTypewriter);
            originalContent = textarea.value;
            originalTitle = document.getElementById('note-title').value;
            loadNotes();
        }
    }, 20);
}

function showAddModal() {
    document.getElementById('new-content').value = '';
    document.getElementById('modal-word-count').textContent = '0 字';
    document.getElementById('add-modal').classList.add('show');
}

function closeAddModal() {
    document.getElementById('add-modal').classList.remove('show');
}

async function addNote() {
    const content = document.getElementById('new-content').value;

    if (!content.trim()) {
        alert('内容不能为空');
        return;
    }

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/notes/`, { content });

        if (data.success) {
            closeAddModal();
            loadNotes();
            selectNote(data.note.id);
        } else {
            alert('添加失败: ' + data.error);
        }
    } catch (error) {
        console.error('添加失败:', error);
        alert('添加失败');
    }
}

function deleteNote() {
    document.getElementById('confirm-modal').classList.add('show');
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.remove('show');
}

async function confirmDelete() {
    try {
        const data = await api.delete(`/api/projects/${currentProjectId}/notes/${currentNoteId}/`);

        if (data.success) {
            closeConfirmModal();

            document.getElementById('placeholder-content').style.display = 'flex';
            document.getElementById('note-editor').style.display = 'none';
            document.getElementById('btn-edit').disabled = true;
            document.getElementById('btn-delete').disabled = true;
            document.getElementById('btn-ai-footer').disabled = true;

            loadNotes();
            currentNoteId = null;
        } else {
            alert('删除失败: ' + data.error);
        }
    } catch (error) {
        console.error('删除失败:', error);
        alert('删除失败');
    }
}

function searchNotes() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const noteItems = document.querySelectorAll('.note-item');

    noteItems.forEach(item => {
        const title = item.querySelector('.note-item-title').textContent.toLowerCase();
        const content = item.querySelector('.note-item-content').textContent.toLowerCase();

        if (title.includes(query) || content.includes(query)) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}

function updateWordCount() {
    const content = document.getElementById('note-content-textarea').value;
    const count = content.length;
    document.getElementById('word-count').textContent = count + ' 字';
}

function updateNewWordCount() {
    const content = document.getElementById('new-content').value;
    const count = content.length;
    document.getElementById('modal-word-count').textContent = count + ' 字';
}

async function aiPolishNewNote() {
    const content = document.getElementById('new-content').value;
    
    if (!content.trim()) {
        alert('请先输入内容');
        return;
    }

    const btnAi = document.getElementById('btn-new-ai');
    const originalHtml = btnAi.innerHTML;
    btnAi.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 润色中...';
    btnAi.disabled = true;

    try {
        const prompt = `请帮我整理和优化以下小说片段，并为它提炼一个合适的标题：

原文内容：
${content}

请按照以下格式返回：
标题：[提炼的标题]
内容：[整理优化后的内容]

要求：
1. 标题要简洁明了，能够概括内容核心
2. 内容优化要保持原意，但让表达更流畅、更具文学性
3. 可以适当调整语序和用词，使片段更具可读性`;
        
        const messages = [
            {'role': 'system', 'content': '你是一位专业的文学编辑，擅长整理和优化小说片段。'},
            {'role': 'user', 'content': prompt}
        ];

        const data = await api.post('/api/ai/chat/', { messages });

        if (data.success && data.response) {
            const result = data.response;
            
            let title = '';
            let polishedContent = '';
            
            const lines = result.split('\n');
            for (const line of lines) {
                if (line.startsWith('标题：')) {
                    title = line.substring(3).trim();
                } else if (line.startsWith('内容：')) {
                    polishedContent = line.substring(3).trim();
                }
            }
            
            if (!polishedContent) {
                polishedContent = result;
            }
            
            document.getElementById('new-content').value = polishedContent;
            updateNewWordCount();
        } else {
            alert('AI润色失败: ' + (data.message || '未知错误'));
        }
    } catch (error) {
        console.error('AI润色失败:', error);
        alert('AI润色失败');
    } finally {
        btnAi.innerHTML = originalHtml;
        btnAi.disabled = false;
    }
}

function goBack() {
    window.location.href = `project.html?project_id=${currentProjectId}`;
}
