let currentProjectId = null;
let currentNoteId = null;
let originalContent = '';
let originalTitle = '';
let isEditMode = false;

document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    currentProjectId = getProjectIdFromUrl();

    if (currentProjectId) {
        showLoading('加载中...');
        Promise.all([loadProjectInfo(currentProjectId), loadNotes()]).finally(() => hideLoading());
    } else {
        window.location.href = '/index.html';
    }

    initBackToProjectButton('.back-btn', 'project.html');
});

let allNotes = [];

async function loadNotes() {
    if (!currentProjectId) return;

    try {
        const data = await api.get(`/api/projects/${currentProjectId}/notes/`);

        if (data.success) {
            allNotes = data.data;
            filterAndRenderNotes();
        }
    } catch (error) {
        console.error('加载随手记失败:', error);
    }
}

function filterAndRenderNotes() {
    const statusFilter = document.getElementById('status-filter').value;
    const searchQuery = document.getElementById('search-input').value.toLowerCase();
    let filtered = statusFilter ? allNotes.filter(n => n.status === statusFilter) : allNotes;
    if (searchQuery) {
        filtered = filtered.filter(n => n.title.toLowerCase().includes(searchQuery) || n.content.toLowerCase().includes(searchQuery));
    }
    renderNotes(filtered);
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
    document.getElementById('status-select').disabled = false;
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
    document.getElementById('actions-section').style.display = 'none';
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
    document.getElementById('actions-section').style.display = '';
    document.getElementById('btn-ai-footer').disabled = true;
    document.getElementById('btn-save').style.display = 'none';
    document.getElementById('btn-cancel').style.display = 'none';

    updateWordCount();
}

async function saveNote() {
    const title = document.getElementById('note-title').value;
    const content = document.getElementById('note-content-textarea').value;

    if (!content.trim()) {
        showError('内容不能为空');
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
            document.getElementById('actions-section').style.display = '';
            document.getElementById('btn-ai-footer').disabled = true;
            document.getElementById('btn-save').style.display = 'none';
            document.getElementById('btn-cancel').style.display = 'none';

            const updateTimeEl = document.querySelector('.title-section .update-time');
            updateTimeEl.innerHTML = `<i class="far fa-clock"></i> ${data.note.updated_at}`;

            loadNotes();
            showSuccess('保存成功');
        } else {
            showError('保存失败: ' + data.error);
        }
    } catch (error) {
        console.error('保存失败:', error);
        showError('保存失败');
    }
}

function updateStatus() {
    if (!currentNoteId) return;

    const status = document.getElementById('status-select').value;

    api.put(`/api/projects/${currentProjectId}/notes/${currentNoteId}/`, { status })
        .then(data => {
            if (data.success) {
                loadNotes();
                showSuccess('状态已更新');
            } else {
                showError('更新状态失败');
            }
        })
        .catch(error => {
            console.error('更新状态失败:', error);
            showError('更新状态失败');
        });
}

/**
 * 统一的AI润色方法
 * @param {string} mode - 'edit' 编辑模式 | 'new' 新建模式
 */
async function aiPolish(mode) {
    const TITLE_START = '════TITLE_START════';
    const TITLE_END = '════TITLE_END════';
    const CONTENT_START = '════CONTENT_START════';
    const CONTENT_END = '════CONTENT_END════';

    const isEdit = mode === 'edit';
    const contentEl = isEdit ? document.getElementById('note-content-textarea') : document.getElementById('new-content');
    const content = contentEl.value;

    if (!content.trim()) {
        showError(isEdit ? '请先进入编辑模式' : '请先输入内容');
        return;
    }

    if (isEdit && !currentNoteId) return;

    const title = isEdit ? document.getElementById('note-title').value : '';

    showLoading('AI润色中...', 0.3);

    let streamingBuffer = '';
    let titleComplete = false;
    let finalContent = '';
    let finalTitle = '';

    try {
        const requestBody = { content };
        if (title) requestBody.title = title;

        await api.streamRequestRaw(
            `/api/projects/${currentProjectId}/notes/polish/`,
            { body: requestBody },
            (event) => {
                if (event.done) return;
                const parsed = event.data;
                if (!parsed) return;

                if (parsed.type === 'chunk') {
                    const chunkContent = parsed.content || '';
                    streamingBuffer += chunkContent;

                    if (!titleComplete && isEdit) {
                        const titleStartIdx = streamingBuffer.indexOf(TITLE_START);
                        if (titleStartIdx !== -1) {
                            const afterTitleStart = streamingBuffer.substring(titleStartIdx + TITLE_START.length);
                            const titleEndIdx = afterTitleStart.indexOf(TITLE_END);

                            if (titleEndIdx !== -1) {
                                finalTitle = afterTitleStart.substring(0, titleEndIdx).trim();
                                document.getElementById('note-title').value = finalTitle;
                                titleComplete = true;
                            }
                        }
                    }
                } else if (parsed.type === 'complete') {
                    // 从流式缓冲区解析标题
                    if (!finalTitle) {
                        const titleStartIdx = streamingBuffer.indexOf(TITLE_START);
                        const titleEndIdx = streamingBuffer.indexOf(TITLE_END);
                        if (titleStartIdx !== -1 && titleEndIdx !== -1) {
                            finalTitle = streamingBuffer.substring(titleStartIdx + TITLE_START.length, titleEndIdx).trim();
                            if (isEdit) {
                                document.getElementById('note-title').value = finalTitle;
                            } else {
                                document.getElementById('new-title').value = finalTitle;
                            }
                        }
                    }
                    // 从流式缓冲区解析内容
                    const contentStartIdx = streamingBuffer.indexOf(CONTENT_START);
                    const contentEndIdx = streamingBuffer.indexOf(CONTENT_END);
                    if (contentStartIdx !== -1 && contentEndIdx !== -1) {
                        finalContent = streamingBuffer.substring(contentStartIdx + CONTENT_START.length, contentEndIdx).trim();
                    }

                    if (finalContent) {
                        if (isEdit) {
                            typewriterEffect(finalContent, async () => {
                                // 打字机效果完成后，通过NoteDetailAPIView保存
                                try {
                                    const data = await api.put(`/api/projects/${currentProjectId}/notes/${currentNoteId}/`, {
                                        title: finalTitle,
                                        content: finalContent
                                    });
                                    if (data.success) {
                                        originalContent = finalContent;
                                        originalTitle = finalTitle;
                                        const updateTimeEl = document.querySelector('.title-section .update-time');
                                        updateTimeEl.innerHTML = `<i class="far fa-clock"></i> ${data.note.updated_at}`;
                                        loadNotes();
                                        showSuccess('AI优化完成');
                                    }
                                } catch (e) {
                                    console.error('保存失败:', e);
                                    showError('保存失败');
                                }
                            });
                        } else {
                            contentEl.value = finalContent;
                            updateNewWordCount();
                            showSuccess('AI润色完成');
                        }
                    }
                } else if (parsed.type === 'error') {
                    showError('AI润色失败: ' + parsed.message);
                }
            }
        );
    } catch (error) {
        console.error('AI润色失败:', error);
        showError('AI润色失败');
    } finally {
        hideLoading();
    }
}

function typewriterEffect(text, onComplete) {
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
            if (onComplete) onComplete();
        }
    }, 20);
}

function showAddModal() {
    document.getElementById('new-title').value = '';
    document.getElementById('new-content').value = '';
    document.getElementById('modal-word-count').textContent = '0 字';
    document.getElementById('add-modal').classList.add('show');
}

function closeAddModal() {
    document.getElementById('add-modal').classList.remove('show');
}

async function addNote() {
    const title = document.getElementById('new-title').value.trim();
    const content = document.getElementById('new-content').value;

    if (!content.trim()) {
        showError('内容不能为空');
        return;
    }

    try {
        const data = await api.post(`/api/projects/${currentProjectId}/notes/`, { title, content });

        if (data.success) {
            closeAddModal();
            await loadNotes();
            selectNote(data.note.id);
            showSuccess('添加成功');
        } else {
            showError('添加失败: ' + data.error);
        }
    } catch (error) {
        console.error('添加失败:', error);
        showError('添加失败');
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
            document.getElementById('actions-section').style.display = '';
            document.getElementById('btn-edit').disabled = true;
            document.getElementById('btn-delete').disabled = true;
            document.getElementById('btn-ai-footer').disabled = true;

            loadNotes();
            currentNoteId = null;
            showSuccess('删除成功');
        } else {
            showError('删除失败: ' + data.error);
        }
    } catch (error) {
        console.error('删除失败:', error);
        showError('删除失败');
    }
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
