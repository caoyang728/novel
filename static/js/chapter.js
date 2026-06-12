// 全局变量
let projectId = null;
let currentVolumeVersionId = null;
let currentVolumeId = null;
let currentChapterId = null;
let volumes = [];
let allChapters = [];  // 当前显示的章节列表
let confirmCallback = null;
let aiChatHistory = [];
let currentEditorTab = 'content'; // 'content' or 'summary'
let typewriterAbortVersion = 0;
let isDirty = false; // 是否有未保存的手动修改
let isSaving = false; // 是否正在保存中，防止重复提交
let savedSnapshot = {}; // 保存时的快照，用于取消恢复

// DOM 缓存（避免重复查询）
const dom = {};

function initDomCache() {
    dom.volumeVersionSelect = document.getElementById('volume-version-select');
    dom.volumeSelect = document.getElementById('volume-select');
    dom.generateChaptersBtn = document.getElementById('generate-chapters-btn');
    dom.chapterList = document.getElementById('chapter-list');
    dom.totalChaptersCount = document.getElementById('total-chapters-count');
    dom.editorEmptyState = document.getElementById('editor-empty-state');
    dom.editorContentArea = document.getElementById('editor-content-area');
    dom.currentChapterLabel = document.getElementById('current-chapter-label');
    dom.chapterTitleInput = document.getElementById('chapter-title-input');
    dom.chapterTitleEditIcon = document.getElementById('chapter-title-edit-icon');
    dom.chapterTitleSaveBtn = document.getElementById('chapter-title-save-btn');
    dom.chapterContentInput = document.getElementById('chapter-content-input');
    dom.chapterSummaryInput = document.getElementById('chapter-summary-input');
    dom.editorContentWrapper = document.getElementById('editor-content-wrapper');
    dom.tabContent = document.getElementById('tab-content');
    dom.tabSummary = document.getElementById('tab-summary');
    dom.emptyContentPlaceholder = document.getElementById('empty-content-placeholder');
    dom.btnGenerateSingle = document.getElementById('btn-generate-single');
    dom.deletedChapterActions = document.getElementById('deleted-chapter-actions');
    dom.btnVerify = document.getElementById('btn-verify');
    dom.btnSplit = document.getElementById('btn-split');
    dom.btnSave = document.getElementById('btn-save');
    dom.btnCancel = document.getElementById('btn-cancel');
    dom.btnPublish = document.getElementById('btn-publish');
    dom.btnLock = document.getElementById('btn-lock');
    dom.btnDelete = document.getElementById('btn-delete');
    dom.quickPrompts = document.getElementById('quick-prompts');
    dom.aiChatInput = document.getElementById('ai-chat-input');
    dom.aiChatMessages = document.getElementById('ai-chat-messages');
    dom.btnAiSend = document.getElementById('btn-ai-send');
    dom.toastContainer = document.getElementById('toast-container');
    dom.statusFilterSelect = document.getElementById('chapter-status-filter');
    dom.verifyModal = document.getElementById('verify-modal');
    dom.verifyResult = document.getElementById('verify-result');
    dom.confirmModal = document.getElementById('confirm-modal');
    dom.confirmTitle = document.getElementById('confirm-title');
    dom.confirmMessage = document.getElementById('confirm-message');
    dom.splitModal = document.getElementById('split-modal');
    dom.hardDeleteModal = document.getElementById('hard-delete-modal');
    dom.hardDeleteMessage = document.getElementById('hard-delete-message');
    dom.hardDeleteInput = document.getElementById('hard-delete-input');
    dom.hardDeleteConfirmBtn = document.getElementById('hard-delete-confirm-btn');
    dom.reorderModal = document.getElementById('reorder-modal');
    dom.deletedWarningModal = document.getElementById('deleted-warning-modal');
    dom.deletedWarningMessages = document.getElementById('deleted-warning-messages');
    dom.chatCompareModal = document.getElementById('chat-compare-modal');
    dom.compareChapterListBody = document.getElementById('compare-chapter-list-body');
    dom.compareStatusBadge = document.getElementById('compare-status-badge');
    dom.compareTitleOriginal = document.getElementById('compare-title-original');
    dom.compareTitleArrow = document.getElementById('compare-title-arrow');
    dom.compareTitleModified = document.getElementById('compare-title-modified');
    dom.compareRows = document.getElementById('compare-rows');
    dom.compareChatMessages = document.getElementById('compare-chat-messages');
    dom.compareChatInput = document.getElementById('compare-chat-input');
    dom.btnCompareChatSend = document.getElementById('btn-compare-chat-send');
    dom.btnCompareSave = document.getElementById('btn-compare-save');
}

document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    projectId = urlParams.get('project_id');

    initDomCache();
    initBackToProjectButton('.btn-back');

    if (projectId) {
        // console.log('projectId:', projectId);
        loadProjectInfo();
        loadVolumeVersions();
    }

    document.getElementById('volume-version-select').addEventListener('change', function() {
        currentVolumeVersionId = this.value;
        document.getElementById('volume-select').disabled = !currentVolumeVersionId;
        if (currentVolumeVersionId) {
            loadVolumes(currentVolumeVersionId);
        } else {
            document.getElementById('volume-select').innerHTML = '<option value="">请选择卷</option>';
            clearChapterList();
        }
    });

    document.getElementById('volume-select').addEventListener('change', function() {
        // console.log('volume-select changed, this.value:', this.value, 'typeof:', typeof this.value);
        currentVolumeId = this.value;
        // console.log('currentVolumeId after change:', currentVolumeId);
        document.getElementById('generate-chapters-btn').disabled = !currentVolumeId;
        if (currentVolumeId) {
            loadChaptersByVolume(currentVolumeId);
        } else {
            clearChapterList();
        }
    });

    // 监听手动修改
    document.getElementById('chapter-content-input').addEventListener('input', function() {
        markDirty();
    });
    document.getElementById('chapter-summary-input').addEventListener('input', function() {
        markDirty();
    });

    // AI对话输入框
    const aiInput = document.getElementById('ai-chat-input');
    if (aiInput) {
        aiInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendAiMessage();
            }
        });
        aiInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 168) + 'px';
        });
    }

    // 对比弹窗AI输入框
    const compareInput = document.getElementById('compare-chat-input');
    if (compareInput) {
        compareInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendCompareChatMessage();
            }
        });
        compareInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }

    // 标题行内编辑：Enter确认，Escape取消
    const titleInput = document.getElementById('chapter-title-input');
    if (titleInput) {
        titleInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                finishEditTitle();
            } else if (e.key === 'Escape') {
                cancelEditTitle();
            }
        });
    }
});

async function loadProjectInfo() {
    const data = await api.get(`/api/projects/${projectId}/`);
    if (data.success) {
        document.getElementById('project-title').textContent = data.project.title;
    }
}

async function loadVolumeVersions() {
    const data = await api.get(`/api/volume-versions/?project_id=${projectId}`);
    if (data.success) {
        const select = document.getElementById('volume-version-select');
        select.innerHTML = '<option value="">请选择卷版本</option>';

        let finalizedVersion = null;
        data.versions.forEach(v => {
            const option = document.createElement('option');
            option.value = v.id;
            option.textContent = `v${v.version_number} (${v.volume_count}卷)${v.is_finalized ? ' ✓' : ''}`;
            select.appendChild(option);
            if (v.is_finalized) finalizedVersion = v;
        });

        if (finalizedVersion) {
            // console.log('Found finalized version:', finalizedVersion);
            select.value = finalizedVersion.id;
            currentVolumeVersionId = finalizedVersion.id;
            document.getElementById('volume-select').disabled = false;
            // console.log('Calling loadVolumes with versionId:', finalizedVersion.id);
            loadVolumes(finalizedVersion.id);
        }
    }
}

async function loadVolumes(versionId) {
    if (!versionId) return;

    showLoading('加载卷列表...', 0.3);
    try {
        const data = await api.get(`/api/volume-versions/${versionId}/`);
        // console.log('loadVolumes API response:', data);
        if (data.success) {
            volumes = data.volumes;
            // console.log('volumes array:', volumes);
            const select = document.getElementById('volume-select');
            select.innerHTML = '<option value="">请选择卷</option>';

            volumes.forEach((vol, index) => {
                // console.log(`vol[${index}]:`, vol, 'vol.id:', vol.id, 'typeof:', typeof vol.id);
                const option = document.createElement('option');
                option.value = vol.id;
                option.textContent = `第${vol.volume_number}卷: ${vol.title}`;
                select.appendChild(option);
            });

            if (volumes.length > 0 && !currentVolumeId) {
                // console.log('auto-selecting first volume, volumes[0].id:', volumes[0].id, 'typeof:', typeof volumes[0].id);
                select.value = volumes[0].id;
                currentVolumeId = volumes[0].id;
                // console.log('currentVolumeId after auto-select:', currentVolumeId);
                document.getElementById('generate-chapters-btn').disabled = false;
                await loadChaptersByVolume(currentVolumeId);
            }
        }
        hideLoading();
    } catch (e) {
        console.error('加载卷列表失败:', e);
        hideLoading();
    }
}

async function loadChaptersByVolume(volumeId) {
    if (!volumeId) return;

    showLoading('加载章节列表...', 0.3);
    try {
        const data = await api.get(`/api/chapter/volume/${volumeId}/load/`);
        if (data.success) {
            allChapters = data.chapters || [];
            renderChapterList();
        } else {
            clearChapterList();
            if (data && data.message) {
                showToast(data.message, 'error');
            }
        }
        hideLoading();
    } catch (e) {
        console.error('加载章节列表失败:', e);
        hideLoading();
    }
}

function renderChapterList() {
    if (!allChapters || allChapters.length === 0) {
        dom.chapterList.innerHTML = `
            <div class="empty-state py-4 px-3 text-center">
                <i class="fas fa-file-alt text-muted mb-2" style="font-size: 2rem;"></i>
                <p class="text-muted mb-0" style="font-size: 0.85rem;">暂无章节，请先生成</p>
            </div>
        `;
        dom.totalChaptersCount.textContent = '-章';
        return;
    }

    // 按章节号排序
    allChapters.sort((a, b) => a.chapter_number - b.chapter_number);

    // 按状态筛选
    const statusFilter = dom.statusFilterSelect?.value || '';
    let filteredChapters = allChapters;
    if (statusFilter === 'locked') {
        filteredChapters = allChapters.filter(c => c.state === 'locked');
    } else if (statusFilter === 'deleted') {
        filteredChapters = allChapters.filter(c => c.state === 'deleted');
    } else if (statusFilter) {
        filteredChapters = allChapters.filter(c => c.status === statusFilter && c.state !== 'locked' && c.state !== 'deleted');
    }

    if (filteredChapters.length === 0) {
        dom.chapterList.innerHTML = `
            <div class="empty-state py-4 px-3 text-center">
                <i class="fas fa-filter text-muted mb-2" style="font-size: 1.5rem;"></i>
                <p class="text-muted mb-0" style="font-size: 0.85rem;">无匹配的章节</p>
            </div>
        `;
        dom.totalChaptersCount.textContent = `${allChapters.length}章`;
        return;
    }

    dom.chapterList.innerHTML = filteredChapters.map(chap => buildChapterItemHTML(chap)).join('');

    dom.totalChaptersCount.textContent = `${allChapters.length}章`;

    // 自动滚动到当前选中的章节
    if (currentChapterId) {
        const activeItem = dom.chapterList.querySelector(`[data-chapter-id="${currentChapterId}"]`);
        if (activeItem) {
            activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
}

function clearChapterList() {
    dom.chapterList.innerHTML = `
        <div class="empty-state py-4 px-3 text-center">
            <i class="fas fa-file-alt text-muted mb-2" style="font-size: 2rem;"></i>
            <p class="text-muted mb-0" style="font-size: 0.85rem;">请先生成章节</p>
        </div>
    `;
    dom.totalChaptersCount.textContent = '-章';
    allChapters = [];
    currentChapterId = null;
}

// 构建单个章节项的HTML（复用 renderChapterList 的渲染逻辑）
function buildChapterItemHTML(chap) {
    const isDeleted = chap.state === 'deleted';
    const isLocked = chap.state === 'locked';
    const badgeClass = isDeleted ? 'badge-deleted' : (isLocked ? 'badge-locked' : (chap.status === 'published' ? 'badge-published' : getStatusBadgeClass(chap.status)));
    const badgeText = isDeleted ? '已删除' : (isLocked ? '已锁定' : (chap.status === 'published' ? '已发布' : getStatusLabel(chap.status)));
    return `
        <div class="chapter-item ${currentChapterId === chap.id ? 'active' : ''} ${isDeleted ? 'chapter-item-deleted' : ''}"
             onclick="selectChapter(${chap.id})" data-chapter-id="${chap.id}">
            <div class="chapter-top">
                <span class="chapter-number">第${chap.chapter_number}章</span>
                <span class="badge ${badgeClass}">${badgeText}</span>
            </div>
            <div class="chapter-title">${escapeHtml(chap.title)}</div>
            <div class="chapter-meta">
                <span>${chap.word_count || 0}字</span>
                ${chap.updated_at ? `<span>${new Date(chap.updated_at).toLocaleString()}</span>` : ''}
            </div>
        </div>
    `;
}

// 局部更新单个章节项（避免全量重渲染）
function refreshSingleChapterItem(chapterId) {
    if (!dom.chapterList) return;
    const chapter = allChapters.find(c => c.id === chapterId);
    if (!chapter) return;

    const existingEl = dom.chapterList.querySelector(`[data-chapter-id="${chapterId}"]`);
    if (existingEl) {
        existingEl.outerHTML = buildChapterItemHTML(chapter);
    }
    dom.totalChaptersCount.textContent = `${allChapters.length}章`;
}

// 仅更新章节高亮（不重建DOM）
function highlightChapterItem(chapterId) {
    dom.chapterList.querySelectorAll('.chapter-item').forEach(item => {
        item.classList.toggle('active', parseInt(item.dataset.chapterId) === chapterId);
    });
}

// 标签切换
function switchEditorTab(tab) {
    currentEditorTab = tab;

    if (tab === 'content') {
        dom.tabContent.classList.add('active');
        dom.tabSummary.classList.remove('active');
        dom.editorContentWrapper.style.display = '';
        dom.chapterSummaryInput.style.display = 'none';
    } else {
        dom.tabContent.classList.remove('active');
        dom.tabSummary.classList.add('active');
        dom.editorContentWrapper.style.display = 'none';
        dom.chapterSummaryInput.style.display = '';
    }

    // 更新按钮状态
    updateEditorButtons();
    // 更新空内容占位符
    updateEmptyContentPlaceholder();
}

// 更新空内容占位符显示
function updateEmptyContentPlaceholder() {
    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!dom.emptyContentPlaceholder) return;

    const isDeleted = chapter && chapter.state === 'deleted';

    if (currentEditorTab === 'content' && chapter && !chapter.content && !dom.chapterContentInput.value) {
        dom.emptyContentPlaceholder.style.display = '';
        dom.chapterContentInput.style.visibility = 'hidden';

        if (isDeleted) {
            if (dom.btnGenerateSingle) dom.btnGenerateSingle.style.display = 'none';
            if (dom.deletedChapterActions) dom.deletedChapterActions.style.display = 'flex';
        } else {
            if (dom.btnGenerateSingle) dom.btnGenerateSingle.style.display = '';
            if (dom.deletedChapterActions) dom.deletedChapterActions.style.display = 'none';
        }
    } else if (currentEditorTab === 'content' && isDeleted) {
        dom.emptyContentPlaceholder.style.display = '';
        dom.chapterContentInput.style.visibility = 'hidden';
        if (dom.btnGenerateSingle) dom.btnGenerateSingle.style.display = 'none';
        if (dom.deletedChapterActions) dom.deletedChapterActions.style.display = 'flex';
    } else {
        dom.emptyContentPlaceholder.style.display = 'none';
        dom.chapterContentInput.style.visibility = '';
        if (dom.btnGenerateSingle) dom.btnGenerateSingle.style.display = '';
        if (dom.deletedChapterActions) dom.deletedChapterActions.style.display = 'none';
    }
}

// 根据当前标签和章节状态更新按钮
function updateEditorButtons() {
    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    const isPublished = chapter.status === 'published';
    const isLocked = chapter.state === 'locked';
    const hasContent = !!chapter.content;
    const isSummaryTab = currentEditorTab === 'summary';
    const isDeleted = chapter.state === 'deleted';

    // 已删除章节：隐藏所有修改按钮和操作按钮
    if (isDeleted) {
        dom.btnVerify.style.display = 'none';
        dom.btnSplit.style.display = 'none';
        dom.btnSave.style.display = 'none';
        dom.btnCancel.style.display = 'none';
        dom.btnPublish.style.display = 'none';
        dom.btnLock.style.display = 'none';
        dom.btnDelete.style.display = 'none';
        dom.quickPrompts.style.display = 'none';
        if (dom.aiChatInput) dom.aiChatInput.disabled = true;
        if (dom.btnAiSend) dom.btnAiSend.disabled = true;
        return;
    }

    // 已发布章节：只显示提示文字
    if (isPublished) {
        dom.btnVerify.style.display = 'none';
        dom.btnSplit.style.display = 'none';
        dom.btnSave.style.display = 'none';
        dom.btnCancel.style.display = 'none';
        dom.btnPublish.style.display = 'none';
        dom.btnLock.style.display = 'none';
        dom.btnDelete.style.display = 'none';
        dom.quickPrompts.style.display = 'none';
        if (dom.aiChatInput) dom.aiChatInput.disabled = true;
        if (dom.btnAiSend) dom.btnAiSend.disabled = true;

        // 显示已发布提示
        const toolbar = document.querySelector('.btn-toolbar');
        let publishTip = toolbar.querySelector('.published-tip');
        if (!publishTip) {
            publishTip = document.createElement('span');
            publishTip.className = 'published-tip';
            publishTip.innerHTML = '<i class="fas fa-lock me-1"></i>已发布的章节不再支持修改';
            toolbar.appendChild(publishTip);
        }
        publishTip.style.display = '';
        return;
    }

    // 非已发布/已删除：移除已发布提示
    const existingTip = document.querySelector('.btn-toolbar .published-tip');
    if (existingTip) existingTip.style.display = 'none';

    // 修改类按钮：锁定后隐藏
    dom.btnVerify.style.display = isLocked ? 'none' : '';
    dom.btnSplit.style.display = isLocked ? 'none' : '';
    dom.btnVerify.disabled = isLocked ? true : !hasContent;
    dom.btnSplit.disabled = isLocked ? true : (isSummaryTab || isPublished || (chapter.word_count || 0) < 3000);

    // 保存/取消：仅手动修改后显示
    dom.btnSave.style.display = isDirty ? '' : 'none';
    dom.btnCancel.style.display = isDirty ? '' : 'none';

    // 发布：锁定后才显示
    dom.btnPublish.style.display = isLocked && !isPublished ? '' : 'none';

    // 锁定和删除始终显示
    dom.btnLock.style.display = '';
    dom.btnDelete.style.display = '';
    dom.btnLock.disabled = false;
    dom.btnDelete.disabled = isLocked || isPublished;

    // 概述标签下隐藏快捷提示和禁用AI输入
    dom.quickPrompts.style.display = isSummaryTab || isLocked ? 'none' : '';
    if (dom.aiChatInput) dom.aiChatInput.disabled = isSummaryTab || isLocked;
    if (dom.btnAiSend) dom.btnAiSend.disabled = isSummaryTab || isLocked;
}

// 标记为已修改
function markDirty() {
    if (!isDirty) {
        isDirty = true;
        updateEditorButtons();
    }
}

// 拍快照（用于取消恢复）
function takeSnapshot() {
    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;
    savedSnapshot = {
        title: chapter.title,
        content: chapter.content,
        summary: chapter.summary,
    };
}

// 取消编辑，恢复到快照
function cancelEdit() {
    if (!isDirty) return;

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (chapter && savedSnapshot) {
        chapter.title = savedSnapshot.title;
        chapter.content = savedSnapshot.content;
        chapter.summary = savedSnapshot.summary;
        document.getElementById('current-chapter-label').textContent = `第${chapter.chapter_number}章: ${chapter.title || '未命名章节'}`;
        document.getElementById('chapter-content-input').value = chapter.content || '';
        document.getElementById('chapter-summary-input').value = chapter.summary || '';
    }

    isDirty = false;
    updateEditorButtons();
    repdrrList();Lis
}

async function selectChapter(chapterId) {
    const chapter = allChapters.find(c => c.id === chapterId);
    if (!chapter) return;

    // 未保存修改警告
    if (isDirty && currentChapterId && currentChapterId !== chapterId) {
        if (!confirm('当前章节有未保存的修改，切换后将丢失。确定要切换吗？')) {
            return;
        }
        isDirty = false;
    }

    currentChapterId = chapterId;

    // 显示编辑器内容区，隐藏空状态
    dom.editorEmptyState.style.display = 'none';
    dom.editorContentArea.style.display = '';

    dom.currentChapterLabel.textContent = `第${chapter.chapter_number}章: ${chapter.title || '未命名章节'}`;
    dom.chapterTitleInput.value = chapter.title || '';
    dom.chapterContentInput.value = chapter.content || '';
    dom.chapterSummaryInput.value = chapter.summary || '';

    // 已删除章节：只读模式
    const isDeleted = chapter.state === 'deleted';
    dom.chapterContentInput.readOnly = isDeleted;
    dom.chapterSummaryInput.readOnly = isDeleted;

    // 显示编辑图标（已删除章节不显示）
    dom.chapterTitleEditIcon.style.display = isDeleted ? 'none' : '';

    // 退出标题编辑模式
    cancelEditTitle();

    // 默认显示内容标签
    switchEditorTab('content');

    // 重置修改状态，拍快照
    isDirty = false;
    takeSnapshot();

    aiChatHistory = [];
    dom.aiChatMessages.innerHTML = '';

    // 更新高亮
    highlightChapterItem(chapterId);

    // 更新锁定按钮状态
    updateLockButtonState(chapter);

    // 更新占位符和按钮状态
    updateEmptyContentPlaceholder();
    updateEditorButtons();

    // 按需加载章节正文（列表接口不返回 content）
    if (chapter.content === undefined && chapter.state !== 'deleted') {
        showLoading('加载章节内容...', 0.3);
        try {
            const data = await api.get(`/api/chapter/${chapterId}/detail/`);
            if (data && data.success && data.chapter) {
                chapter.content = data.chapter.content || '';
                chapter.summary = data.chapter.summary || '';
                dom.chapterContentInput.value = chapter.content;
                dom.chapterSummaryInput.value = chapter.summary;
                updateEmptyContentPlaceholder();
                updateEditorButtons();
            }
            hideLoading();
        } catch (e) {
            console.error('加载章节详情失败:', e);
            hideLoading();
        }
    }
}

// 更新锁定按钮状态
function updateLockButtonState(chapter) {
    const isLocked = chapter.state === 'locked';
    if (!dom.btnLock) return;
    if (isLocked) {
        dom.btnLock.classList.add('locked');
        dom.btnLock.innerHTML = '<i class="fas fa-lock"></i> <span>解锁</span>';
    } else {
        dom.btnLock.classList.remove('locked');
        dom.btnLock.innerHTML = '<i class="fas fa-lock-open"></i> <span>锁定</span>';
    }
}

// 标题编辑
function startEditTitle() {
    const label = document.getElementById('current-chapter-label');
    const input = document.getElementById('chapter-title-input');
    const editIcon = document.getElementById('chapter-title-edit-icon');
    const saveBtn = document.getElementById('chapter-title-save-btn');

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    input.value = chapter.title || '';
    label.style.display = 'none';
    editIcon.style.display = 'none';
    input.style.display = '';
    saveBtn.style.display = '';
    input.focus();
}

function finishEditTitle() {
    const label = document.getElementById('current-chapter-label');
    const input = document.getElementById('chapter-title-input');
    const editIcon = document.getElementById('chapter-title-edit-icon');
    const saveBtn = document.getElementById('chapter-title-save-btn');

    const newTitle = input.value.trim();
    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (chapter && newTitle && newTitle !== chapter.title) {
        chapter.title = newTitle;
        label.textContent = `第${chapter.chapter_number}章: ${newTitle}`;
        markDirty();
        refreshSingleChapterItem(currentChapterId);
    }

    label.style.display = '';
    editIcon.style.display = '';
    input.style.display = 'none';
    saveBtn.style.display = 'none';
}

function cancelEditTitle() {
    const label = document.getElementById('current-chapter-label');
    const input = document.getElementById('chapter-title-input');
    const editIcon = document.getElementById('chapter-title-edit-icon');
    const saveBtn = document.getElementById('chapter-title-save-btn');

    label.style.display = '';
    if (currentChapterId) editIcon.style.display = '';
    input.style.display = 'none';
    saveBtn.style.display = 'none';
}

async function generateChapterSummaries() {
    const volumeId = parseInt(currentVolumeId);
    if (!volumeId || isNaN(volumeId)) {
        showToast('请先选择卷', 'error');
        return;
    }

    // 未保存修改警告
    if (!checkUnsavedChanges('当前有未保存的修改，生成新章节后将丢失。确定要继续吗？')) return;

    const btn = document.getElementById('generate-chapters-btn');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="loading-spinner"></span> 生成中...';
    btn.disabled = true;

    // 清空章节列表和编辑器
    allChapters = [];
    currentChapterId = null;
    renderChapterList();
    document.getElementById('chapter-title-input').value = '';
    document.getElementById('chapter-content-input').value = '';
    document.getElementById('chapter-summary-input').value = '';
    document.getElementById('current-chapter-label').textContent = '思考中...';

    // 显示生成遮罩
    showLoading('思考中...', 0.1);

    try {
        let totalWords = 0;
        let completeVolumeId = null;

        await api.streamRequestRaw('/api/chapter/generate/', {
            body: { volume_id: volumeId }
        }, (event) => {
            if (event.done) return;
            const data = event.data;
            if (!data) return;

            try {
                if (data.type === 'progress') {
                    const loadingText = document.querySelector('#global-loading .loading-text');
                    if (loadingText) loadingText.textContent = data.message;
                } else if (data.type === 'outline') {
                    // 阶段1：收到章节概述，添加到列表
                    const chap = data.chapter;
                    chap.id = -(chap.chapter_number); // 临时负数ID
                    chap.status = 'summary';
                    chap.word_count = 0;
                    chap.state = 'normal';
                    chap.content = '';
                    allChapters.push(chap);
                    renderChapterList();

                    // 选中当前章节
                    currentChapterId = chap.id;
                    document.getElementById('current-chapter-label').textContent = `第${chap.chapter_number}章: ${chap.title}`;
                    document.getElementById('chapter-title-input').value = chap.title;
                    document.getElementById('chapter-summary-input').value = chap.summary || '';
                    switchEditorTab('summary');
                    document.querySelectorAll('.chapter-item').forEach(item => {
                        item.classList.remove('active');
                        if (item.dataset.chapterId == chap.id) {
                            item.classList.add('active');
                        }
                    });

                    const completedCount = allChapters.filter(c => c.status === 'summary' || c.status === 'draft').length;
                    const _lt = document.querySelector('#global-loading .loading-text');
                    if (_lt) _lt.textContent = `正在生成章节概述... 第${chap.chapter_number}章\n已完成${completedCount}/${allChapters.length} 章`;

                } else if (data.type === 'chapter') {
                    // 阶段2：收到章节正文，更新列表中的对应章节
                    const chap = data.chapter;
                    const existIdx = allChapters.findIndex(c => c.chapter_number === chap.chapter_number);
                    if (existIdx !== -1) {
                        allChapters[existIdx].content = chap.content;
                        allChapters[existIdx].word_count = chap.word_count;
                        allChapters[existIdx].status = 'draft';
                    } else {
                        chap.id = -(chap.chapter_number);
                        chap.state = 'normal';
                        allChapters.push(chap);
                    }
                    renderChapterList();

                    // 在编辑器中用打字机效果展示
                    totalWords += chap.word_count || 0;
                    currentChapterId = allChapters[existIdx !== -1 ? existIdx : allChapters.length - 1].id;
                    document.getElementById('current-chapter-label').textContent = `第${chap.chapter_number}章: ${chap.title}`;
                    document.getElementById('chapter-title-input').value = chap.title;
                    switchEditorTab('content');

                    // 打字机效果
                    typewriterEffect('chapter-content-input', chap.content || '');

                    const completedCount = allChapters.filter(c => c.status === 'draft').length;
                    const _lt2 = document.querySelector('#global-loading .loading-text');
                    if (_lt2) _lt2.textContent = `正在生成第${chap.chapter_number}章: ${chap.title}\n已完成${completedCount}/${allChapters.length} 章`;

                    // 自动选中
                    document.querySelectorAll('.chapter-item').forEach(item => {
                        item.classList.remove('active');
                        if (item.dataset.chapterId == currentChapterId) {
                            item.classList.add('active');
                        }
                    });

                } else if (data.type === 'chapter_failed') {
                    // 章节生成失败
                    const existIdx = allChapters.findIndex(c => c.chapter_number === data.chapter_number);
                    if (existIdx !== -1) {
                        allChapters[existIdx].status = 'failed';
                    }
                    renderChapterList();
                    const completedCount = allChapters.filter(c => c.status === 'draft').length;
                    const _lt3 = document.querySelector('#global-loading .loading-text');
                    if (_lt3) _lt3.textContent = `第${data.chapter_number}章生成失败\n已完成${completedCount}/${allChapters.length} 章`;

                } else if (data.type === 'complete') {
                    hideLoading();
                    showToast(`章节内容生成完成！共 ${data.chapters_count} 章，总计 ${totalWords} 字`, 'success');
                    document.getElementById('current-chapter-label').textContent = '生成完成';
                    completeVolumeId = data.volume_id;
                } else if (data.type === 'error') {
                    hideLoading();
                    showToast('生成失败: ' + data.message, 'error');
                }
            } catch (e) {
                console.error('处理SSE事件失败:', e);
            }
        });

        // 重新从后端加载真实ID
        if (completeVolumeId) {
            await loadChaptersByVolume(completeVolumeId);
        }
    } catch (e) {
        console.error('生成章节失败:', e);
        showToast('生成失败: ' + e.message, 'error');
        hideLoading();
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = !currentVolumeId;
    }
}

// 打字机效果：逐字填充到输入框（支持中断，自适应速度）
async function typewriterEffect(elementId, text, speed = 5) {
    const el = document.getElementById(elementId);
    if (!el || !text) return;

    const currentVersion = ++typewriterAbortVersion;
    el.value = '';

    // 自适应速度：总时长约2秒
    const totalChars = text.length;
    const targetDuration = 2000;
    const chunkSize = Math.max(1, Math.ceil(totalChars / (targetDuration / speed)));

    for (let i = 0; i < text.length; i += chunkSize) {
        if (typewriterAbortVersion !== currentVersion) return; // 被中断
        const end = Math.min(i + chunkSize, text.length);
        el.value = text.substring(0, end);
        el.scrollTop = el.scrollHeight;
        await new Promise(r => setTimeout(r, speed));
    }
    el.value = text; // 确保完整
}

// 状态筛选
function filterChaptersByStatus() {
    renderChapterList();
}

async function saveChapter() {
    if (!currentChapterId) return;
    if (isSaving) return;
    isSaving = true;

    const saveBtn = document.getElementById('btn-save');
    if (saveBtn) saveBtn.disabled = true;

    showLoading('保存中...', 0.3);

    try {
        const chapter = allChapters.find(c => c.id === currentChapterId);
        const title = document.getElementById('chapter-title-input').style.display !== 'none'
            ? document.getElementById('chapter-title-input').value
            : (chapter ? chapter.title : '');
        const content = document.getElementById('chapter-content-input').value;
        const summary = document.getElementById('chapter-summary-input').value;

        const data = await api.post('/api/chapter/save/', { chapter_id: currentChapterId, title, content, summary });
        if (data && data.success) {
            updateLocalChapter(currentChapterId, { title, content, summary, word_count: data.chapter.word_count });
            isDirty = false;
            takeSnapshot();
            updateEditorButtons();
            showToast('保存成功！', 'success');
            try {
                refreshSingleChapterItem(currentChapterId);
            } catch (e) {
                console.error('refreshSingleChapterItem error:', e);
            }
            clearPendingData('chapter_editor');
        } else {
            showToast('保存失败: ' + ((data && data.message) || ''), 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
        isSaving = false;
        if (saveBtn) saveBtn.disabled = false;
    }
}

function insertPrompt(text) {
    document.getElementById('ai-chat-input').value = text;
    document.getElementById('ai-chat-input').focus();
}

// ========== AI对话对比弹窗相关 ==========

// 对比弹窗会话数据
let compareSession = {
    modifications: {},     // { chapter_number: { original: {title, content}, modified: {title, content} } }
    currentChapterNumber: null, // 当前选中的章节号
    chatHistory: [],       // 弹窗内AI对话历史 [{role, content}]
    isSaving: false,       // 是否正在保存
    isSending: false,      // 是否正在发送消息
};

function openCompareModal() {
    openModal('chat-compare-modal');
}

function closeCompareModal() {
    // 关闭弹窗时清理所有缓存数据
    compareSession = {
        modifications: {},
        currentChapterNumber: null,
        chatHistory: [],
        isSaving: false,
        isSending: false,
    };
    closeModal('chat-compare-modal');
}

function renderCompareChapterList() {
    const container = document.getElementById('compare-chapter-list-body');
    const numbers = Object.keys(compareSession.modifications)
        .map(Number)
        .sort((a, b) => a - b)
        // 过滤：只有 title 或 content 发生变化才展示
        .filter(chapterNumber => {
            const mod = compareSession.modifications[chapterNumber];
            if (!mod) return false;
            return mod.original.title !== mod.modified.title ||
                   mod.original.content !== mod.modified.content;
        });

    if (numbers.length === 0) {
        container.innerHTML = '<div class="empty-state py-4 px-3 text-center"><p class="text-muted mb-0" style="font-size:0.82rem;">暂无修改</p></div>';
        document.getElementById('compare-status-badge').textContent = '已修改 0 章';
        return;
    }

    container.innerHTML = numbers.map(chapterNumber => {
        const isActive = chapterNumber === compareSession.currentChapterNumber;
        const mod = compareSession.modifications[chapterNumber];
        return `
            <div class="compare-chapter-item ${isActive ? 'active' : ''}"
                 onclick="selectCompareChapter(${chapterNumber})" data-chapter-number="${chapterNumber}">
                <span class="chapter-modified-dot"></span>
                <span>第${chapterNumber}章${mod ? ': ' + escapeHtml(mod.modified.title) : ''}</span>
            </div>
        `;
    }).join('');

    const modifiedCount = numbers.length;
    document.getElementById('compare-status-badge').textContent = `已修改 ${modifiedCount} 章`;
}

// 行级diff：返回对齐的 (left, right) 配对数组，保证左右行数一致
// 每个配对: { left: {line, type}, right: {line, type} }
// type: 'same' | 'deleted' | 'added' | 'empty'
// 超过 MAX_DIFF_LINES 行时使用简单全文对比避免性能问题
const MAX_DIFF_LINES = 500;

function computeDiff(originalText, modifiedText) {
    const origLines = (originalText || '').split('\n');
    const modLines = (modifiedText || '').split('\n');

    // 超长文本降级为简单对比：左侧全文删除 + 右侧全文新增
    if (origLines.length > MAX_DIFF_LINES || modLines.length > MAX_DIFF_LINES) {
        const pairs = [];
        const maxLen = Math.max(origLines.length, modLines.length);
        for (let i = 0; i < maxLen; i++) {
            const origLine = i < origLines.length ? origLines[i] : '';
            const modLine = i < modLines.length ? modLines[i] : '';
            if (origLine === modLine) {
                pairs.push({
                    left: { line: origLine, type: 'same' },
                    right: { line: modLine, type: 'same' },
                });
            } else {
                pairs.push({
                    left: { line: origLine || '', type: origLine ? 'deleted' : 'empty' },
                    right: { line: modLine || '', type: modLine ? 'added' : 'empty' },
                });
            }
        }
        return pairs;
    }

    const m = origLines.length;
    const n = modLines.length;
    const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

    for (let i = 1; i <= m; i++) {
        for (let j = 1; j <= n; j++) {
            if (origLines[i - 1] === modLines[j - 1]) {
                dp[i][j] = dp[i - 1][j - 1] + 1;
            } else {
                dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
            }
        }
    }

    // 回溯产生对齐的配对结果，左右始终一一对应
    const pairs = [];
    let i = m, j = n;

    while (i > 0 || j > 0) {
        if (i > 0 && j > 0 && origLines[i - 1] === modLines[j - 1]) {
            pairs.unshift({
                left: { line: origLines[i - 1], type: 'same' },
                right: { line: modLines[j - 1], type: 'same' },
            });
            i--; j--;
        } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
            pairs.unshift({
                left: { line: '', type: 'empty' },
                right: { line: modLines[j - 1], type: 'added' },
            });
            j--;
        } else if (i > 0) {
            pairs.unshift({
                left: { line: origLines[i - 1], type: 'deleted' },
                right: { line: '', type: 'empty' },
            });
            i--;
        }
    }

    return pairs;
}

function renderDiffContent(originalContent, modifiedContent) {
    const pairs = computeDiff(originalContent, modifiedContent);
    const rowsContainer = document.getElementById('compare-rows');

    // 构建行头：修改前 | 修改后
    let html = '<div class="diff-row-header"><div class="diff-row-header-col">修改前</div><div class="diff-row-header-divider"></div><div class="diff-row-header-col">修改后</div></div>';

    // 每行一个 pair，左右各一个 cell，浏览器自然对齐（支持换行）
    for (let rowIdx = 0; rowIdx < pairs.length; rowIdx++) {
        const p = pairs[rowIdx];
        const isLeftEmpty = p.left.type === 'empty';
        const isRightEmpty = p.right.type === 'empty';
        const isDeleted = p.left.type === 'deleted';
        const isAdded = p.right.type === 'added';
        const rowNum = rowIdx + 1;

        const leftCls = isDeleted ? ' diff-row-cell-del' : '';
        const rightCls = isAdded ? ' diff-row-cell-add' : '';
        const leftPrefix = isDeleted ? '-' : (isLeftEmpty ? ' ' : ' ');
        const rightPrefix = isAdded ? '+' : (isRightEmpty ? ' ' : ' ');

        html += '<div class="diff-row">';
        html += `<div class="diff-row-cell${leftCls}"><span class="diff-line-num">${rowNum}</span><span class="diff-line-prefix">${leftPrefix}</span><span class="diff-line-content">${escapeHtml(p.left.line) || '&nbsp;'}</span></div>`;
        html += '<div class="diff-row-divider"></div>';
        html += `<div class="diff-row-cell${rightCls}"><span class="diff-line-num">${rowNum}</span><span class="diff-line-prefix">${rightPrefix}</span><span class="diff-line-content">${escapeHtml(p.right.line) || '&nbsp;'}</span></div>`;
        html += '</div>';
    }

    rowsContainer.innerHTML = html;
}

// 流式输出期间：左侧原文 + 右侧流式输出 textarea 布局
// 首次调用创建DOM，后续调用仅更新 value 避免 DOM 重绘
function showStreamingLayout(originalContent, streamingText) {
    const rowsContainer = document.getElementById('compare-rows');
    if (!rowsContainer) return;

    const isFirstCall = !rowsContainer.dataset.streaming;
    if (isFirstCall) {
        rowsContainer.dataset.streaming = 'true';
        rowsContainer.innerHTML = `
            <div class="compare-streaming">
                <div class="compare-streaming-col">
                    <div class="compare-streaming-label">修改前</div>
                    <textarea class="compare-streaming-textarea" id="streaming-textarea-original" readonly>${escapeHtml(originalContent)}</textarea>
                </div>
                <div class="compare-streaming-divider"></div>
                <div class="compare-streaming-col">
                    <div class="compare-streaming-label">修改后 <span style="color:#6b7280;font-weight:400;text-transform:none;letter-spacing:0;font-size:0.72rem;">（生成中...）</span></div>
                    <textarea class="compare-streaming-textarea" id="streaming-textarea-modified" readonly>${escapeHtml(streamingText)}</textarea>
                </div>
            </div>
        `;
    } else {
        // 仅更新右侧 textarea 的 value，避免 innerHTML 重建DOM
        const textarea = document.getElementById('streaming-textarea-modified');
        if (textarea) {
            textarea.value = streamingText;
            textarea.scrollTop = textarea.scrollHeight;
        }
    }
}
function selectCompareChapter(chapterNumber) {
    compareSession.currentChapterNumber = chapterNumber;

    // 高亮更新
    document.querySelectorAll('#compare-chapter-list-body .compare-chapter-item').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.chapterNumber) === chapterNumber);
    });

    const mod = compareSession.modifications[chapterNumber];
    if (!mod) return;

    const originalContent = mod.original.content || '';
    const modifiedContent = mod.modified.content || '';
    const originalTitle = mod.original.title || '';
    const modifiedTitle = mod.modified.title || '';
    const titleChanged = originalTitle !== modifiedTitle;

    document.getElementById('compare-title-original').textContent =
        `第${chapterNumber}章: ${originalTitle}`;
    document.getElementById('compare-title-original').style.display = titleChanged ? '' : 'none';
    document.getElementById('compare-title-arrow').style.display = titleChanged ? '' : 'none';
    document.getElementById('compare-title-modified').textContent =
        `第${chapterNumber}章: ${modifiedTitle}`;
    document.getElementById('compare-title-modified').className = titleChanged ? 'title-modified title-changed' : 'title-modified';

    // 使用diff渲染（清除流式输出标记）
    const rowsContainer = document.getElementById('compare-rows');
    if (rowsContainer) delete rowsContainer.dataset.streaming;
    renderDiffContent(originalContent, modifiedContent);
}

function addCompareChatMessage(role, content) {
    const container = document.getElementById('compare-chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `ai-message ${role}`;
    msgDiv.innerHTML = `
        <div class="ai-message-avatar">${role === 'user' ? '我' : 'AI'}</div>
        <div class="ai-message-bubble">${escapeHtml(content)}</div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

async function sendCompareChatMessage() {
    const input = document.getElementById('compare-chat-input');
    const message = input.value.trim();
    if (!message) return;

    const chapterNumber = compareSession.currentChapterNumber;
    if (!chapterNumber) {
        showToast('请先选择章节', 'error');
        return;
    }

    const mod = compareSession.modifications[chapterNumber];
    if (!mod) return;

    // 新章节没有 chapter_id，使用当前选中的章节 ID 作为上下文
    const chapterId = mod.chapter_id || currentChapterId;

    if (compareSession.isSending) return;
    compareSession.isSending = true;

    input.value = '';
    input.style.height = 'auto';

    const sendBtn = document.getElementById('btn-compare-chat-send');
    sendBtn.disabled = true;

    addCompareChatMessage('user', message);
    compareSession.chatHistory.push({ role: 'user', content: message });

    // 获取当前修改后的内容作为上下文
    const currentContent = mod.modified.content || '';
    const currentTitle = mod.modified.title || '';

    try {
        let fullResponse = '';
        let hasReceivedContent = false;

        const container = document.getElementById('compare-chat-messages');
        const msgDiv = document.createElement('div');
        msgDiv.className = 'ai-message assistant';
        msgDiv.innerHTML = `
            <div class="ai-message-avatar">AI</div>
            <div class="ai-message-bubble"><i class="fas fa-spinner fa-spin me-1"></i>思考中...</div>
        `;
        container.appendChild(msgDiv);
        const aiMsgBubble = msgDiv.querySelector('.ai-message-bubble');
        container.scrollTop = container.scrollHeight;

        await api.streamRequestRaw('/api/chapter/chat/', {
            body: {
                chapter_id: chapterId,
                message,
                history: compareSession.chatHistory,
                current_content: currentContent,
                current_title: currentTitle,
            }
        }, (event) => {
            if (event.done) return;
            const parsed = event.data;
            if (parsed && parsed.type === 'chunk' && parsed.content) {
                fullResponse += parsed.content;
                // 流式输出期间：左侧原文 + 右侧流式 textarea
                showStreamingLayout(currentContent, fullResponse);
                if (!hasReceivedContent) {
                    hasReceivedContent = true;
                    if (aiMsgBubble) {
                        aiMsgBubble.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>输出中...';
                    }
                }
            } else if (parsed && parsed.type === 'complete') {
                const responseData = parsed;
                const finalResponse = responseData.response || fullResponse;
                if (aiMsgBubble) {
                    aiMsgBubble.textContent = finalResponse;
                }
                compareSession.chatHistory.push({ role: 'assistant', content: finalResponse });

                // 更新修改数据 - 保留原始内容，仅更新修改后内容
                const newContent = responseData.content || currentContent;
                const newTitle = responseData.title || currentTitle;
                const respChapterNumber = responseData.chapter_number || chapterNumber;

                if (!compareSession.modifications[respChapterNumber]) {
                    // 首次创建：记录原始内容（数据库中的）和修改后内容
                    const origContent = responseData.original_content || currentContent;
                    const origTitle = responseData.original_title || currentTitle;
                    compareSession.modifications[respChapterNumber] = {
                        chapter_id: responseData.chapter_id || chapterId,
                        original: { title: origTitle, content: origContent },
                        modified: { title: newTitle, content: newContent },
                    };
                } else {
                    // 后续对话：只更新修改后内容，保留原始内容不变
                    compareSession.modifications[respChapterNumber].modified = {
                        title: newTitle,
                        content: newContent,
                    };
                }

                // 更新对比显示（完整diff渲染）
                selectCompareChapter(respChapterNumber);
                renderCompareChapterList();
            } else if (parsed && parsed.type === 'error') {
                if (aiMsgBubble) {
                    aiMsgBubble.textContent = '抱歉，创作失败：' + (parsed.message || '未知错误');
                }
            }
        });
    } catch (e) {
        addCompareChatMessage('assistant', '网络错误，请重试');
    } finally {
        compareSession.isSending = false;
        sendBtn.disabled = false;
    }
}

async function saveCompareChanges() {
    if (compareSession.isSaving) return;
    compareSession.isSaving = true;

    // 只保存有实际修改的章节
    const modifiedNumbers = Object.keys(compareSession.modifications)
        .map(Number)
        .filter(chapterNumber => {
            const mod = compareSession.modifications[chapterNumber];
            if (!mod) return false;
            return mod.original.title !== mod.modified.title ||
                   mod.original.content !== mod.modified.content;
        });
    if (modifiedNumbers.length === 0) {
        showToast('没有需要保存的修改', 'warning');
        closeCompareModal();
        return;
    }

    showLoading('保存中...', 0.3);

    try {
        let successCount = 0;
        for (const chapterNumber of modifiedNumbers) {
            const mod = compareSession.modifications[chapterNumber];
            if (!mod) continue;

            let data;
            if (mod.chapter_id) {
                // 现有章节：更新
                data = await api.post('/api/chapter/save/', {
                    chapter_id: mod.chapter_id,
                    title: mod.modified.title,
                    content: mod.modified.content,
                });
            } else {
                // 新章节（拆分产生）：创建
                data = await api.post('/api/chapter/save/', {
                    chapter_id: 0,
                    volume_id: parseInt(currentVolumeId),
                    chapter_number: chapterNumber,
                    title: mod.modified.title,
                    content: mod.modified.content,
                });
            }

            if (data && data.success) {
                if (mod.chapter_id) {
                    updateLocalChapter(mod.chapter_id, {
                        title: mod.modified.title,
                        content: mod.modified.content,
                        word_count: mod.modified.content.length,
                    });
                }
                successCount++;
            } else {
                showToast(`第${chapterNumber}章保存失败: ${(data && data.message) || ''}`, 'error');
            }
        }

        if (successCount > 0) {
            showToast(`成功保存 ${successCount} 章修改！`, 'success');
            // 重新加载章节列表
            if (currentVolumeId) {
                await loadChaptersByVolume(currentVolumeId);
            }
            if (compareSession.currentChapterNumber) {
                const mod = compareSession.modifications[compareSession.currentChapterNumber];
                if (mod && mod.chapter_id) {
                    selectChapter(mod.chapter_id);
                }
            }
        }

        compareSession = {
            modifications: {},
            currentChapterNumber: null,
            chatHistory: [],
            isSaving: false,
            isSending: false,
        };
        closeCompareModal();
    } catch (e) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
        compareSession.isSaving = false;
    }
}

function cancelCompareChanges() {
    if (Object.keys(compareSession.modifications).length > 0) {
        if (!confirm('确定要取消所有修改吗？未保存的修改将丢失。')) return;
    }

    compareSession = {
        modifications: {},
        currentChapterId: null,
        chatHistory: [],
        isSaving: false,
        isSending: false,
    };
    closeCompareModal();
}

// ========== 原始AI对话发送（已修改为打开对比弹窗） ==========

async function sendAiMessage() {
    const input = document.getElementById('ai-chat-input');
    const message = input.value.trim();
    if (!message) return;

    if (!currentChapterId) {
        showToast('请先选择章节', 'error');
        return;
    }

    if (currentEditorTab === 'summary') {
        showToast('概述模式下无法使用AI对话', 'error');
        return;
    }

    // 未保存修改警告
    if (isDirty) {
        if (!confirm('当前有未保存的修改，AI创作后将丢失。确定要继续吗？')) {
            return;
        }
        isDirty = false;
    }

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    // 记录原始内容用于对比
    const originalContent = chapter.content || '';
    const originalTitle = chapter.title || '';

    input.value = '';
    input.style.height = 'auto';

    const sendBtn = document.getElementById('btn-ai-send');
    sendBtn.disabled = true;

    // 重置对话session
    compareSession = {
        modifications: {},
        currentChapterNumber: null,
        chatHistory: [],
        isSaving: false,
        isSending: false,
    };

    addAiMessage('user', message);
    aiChatHistory.push({ role: 'user', content: message });

    showLoading('AI创作中...', 0.3);

    try {
        let fullResponse = '';
        let aiMsgBubble = null;
        let modalOpened = false;
        let modifiedChapterNumber = null;
        let modalBubble = null; // 弹窗中的AI消息气泡

        // 主聊天区的AI气泡 - 初始显示"思考中..."
        const container = document.getElementById('ai-chat-messages');
        const msgDiv = document.createElement('div');
        msgDiv.className = 'ai-message assistant';
        msgDiv.innerHTML = `
            <div class="ai-message-avatar">AI</div>
            <div class="ai-message-bubble"><i class="fas fa-spinner fa-spin me-1"></i>思考中...</div>
        `;
        container.appendChild(msgDiv);
        aiMsgBubble = msgDiv.querySelector('.ai-message-bubble');

        await api.streamRequestRaw('/api/chapter/chat/', {
            body: { chapter_id: currentChapterId, message, history: aiChatHistory }
        }, (event) => {
            if (event.done) return;
            const parsed = event.data;
            if (parsed && parsed.type === 'chunk' && parsed.content) {
                fullResponse += parsed.content;
                // 主聊天区气泡显示"输出中..."
                if (aiMsgBubble) {
                    aiMsgBubble.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>输出中...';
                }
                container.scrollTop = container.scrollHeight;

                // 收到第一个chunk时打开对比弹窗
                if (!modalOpened && fullResponse.length > 10) {
                    modalOpened = true;
                    hideLoading();

                    modifiedChapterNumber = chapter.chapter_number;

                    // 初始化session
                    compareSession.currentChapterNumber = modifiedChapterNumber;
                    compareSession.chatHistory = [...aiChatHistory];

                    // 预先创建修改记录（将在complete时填充）
                    compareSession.modifications[modifiedChapterNumber] = {
                        chapter_id: currentChapterId,
                        original: { title: originalTitle, content: originalContent },
                        modified: { title: chapter.title, content: chapter.content },
                    };

                    // 渲染章节列表
                    renderCompareChapterList();

                    // 选中当前章节（渲染diff）
                    selectCompareChapter(modifiedChapterNumber);

                    // 同步主聊天区的消息到弹窗
                    document.getElementById('compare-chat-messages').innerHTML = '';
                    aiChatHistory.forEach(msg => {
                        addCompareChatMessage(msg.role, msg.content);
                    });
                    // 添加当前正在生成的AI消息 - 显示"输出中..."
                    const assistantMsgDiv = document.createElement('div');
                    assistantMsgDiv.className = 'ai-message assistant';
                    assistantMsgDiv.innerHTML = `
                        <div class="ai-message-avatar">AI</div>
                        <div class="ai-message-bubble"><i class="fas fa-spinner fa-spin me-1"></i>输出中...</div>
                    `;
                    document.getElementById('compare-chat-messages').appendChild(assistantMsgDiv);
                    modalBubble = assistantMsgDiv.querySelector('.ai-message-bubble');

                    // 打开弹窗
                    openCompareModal();
                }

                // 弹窗打开后：左侧原文 + 右侧流式 textarea
                if (modalOpened) {
                    showStreamingLayout(originalContent, fullResponse);
                }
            } else if (parsed && parsed.type === 'complete') {
                const responseData = parsed;
                const finalResponse = responseData.response || fullResponse;

                // 更新主聊天区
                if (aiMsgBubble) {
                    aiMsgBubble.textContent = finalResponse;
                }
                aiChatHistory.push({ role: 'assistant', content: finalResponse });

                // 处理完整响应数据
                const newContent = responseData.content || '';
                const newTitle = responseData.title || '';
                const respChapterNumber = responseData.chapter_number || chapter.chapter_number;

                // 保存到修改记录（使用chapter_number为key）
                if (newContent || newTitle) {
                    compareSession.modifications[respChapterNumber] = {
                        chapter_id: responseData.chapter_id || currentChapterId,
                        original: { title: responseData.original_title || originalTitle, content: responseData.original_content || originalContent },
                        modified: {
                            title: newTitle || chapter.title,
                            content: newContent || chapter.content,
                        },
                    };
                }

                // 更新弹窗内容
                if (modalOpened) {
                    // 更新弹窗chat中的AI气泡
                    const chatContainer = document.getElementById('compare-chat-messages');
                    const assistantBubbles = chatContainer.querySelectorAll('.ai-message.assistant .ai-message-bubble');
                    if (assistantBubbles.length > 0) {
                        assistantBubbles[assistantBubbles.length - 1].textContent = finalResponse;
                    }

                    // 使用diff更新对比显示
                    if (respChapterNumber) {
                        selectCompareChapter(respChapterNumber);
                    }
                    renderCompareChapterList();
                    showToast('AI 创作完成，请在弹窗中查看对比并确认修改', 'success');
                } else {
                    // 未打开弹窗（内容较少等），直接写入编辑器
                    if (newContent) {
                        document.getElementById('chapter-content-input').value = newContent;
                        updateLocalChapter(currentChapterId, { content: newContent, word_count: newContent.length });
                    }
                    if (newTitle) {
                        document.getElementById('chapter-title-input').value = newTitle;
                        updateLocalChapter(currentChapterId, { title: newTitle });
                    }
                    refreshSingleChapterItem(currentChapterId);
                    showToast('AI 创作完成！', 'success');
                }
            } else if (parsed && parsed.type === 'error') {
                addAiMessage('assistant', '抱歉，创作失败：' + (parsed.message || '未知错误'));
                // 移除空的AI气泡
                if (aiMsgBubble && !aiMsgBubble.textContent) {
                    msgDiv.remove();
                }
            }
        });
    } catch (e) {
        addAiMessage('assistant', '网络错误，请重试');
    } finally {
        hideLoading();
        sendBtn.disabled = false;
    }
}

function addAiMessage(role, content) {
    const container = document.getElementById('ai-chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `ai-message ${role}`;
    msgDiv.innerHTML = `
        <div class="ai-message-avatar">${role === 'user' ? '我' : 'AI'}</div>
        <div class="ai-message-bubble">${escapeHtml(content)}</div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

async function publishChapter() {
    if (!currentChapterId) return;

    showConfirm('发布章节', '确定要发布此章节吗？发布后将无法编辑。', async () => {
        showLoading('发布中...', 0.3);

        try {
            const data = await api.post('/api/chapter/status/', { chapter_id: currentChapterId, action: 'publish' });
            if (data.success) {
                showToast('发布成功！', 'success');
                updateLocalChapter(currentChapterId, { status: 'published' });
                refreshSingleChapterItem(currentChapterId);
                selectChapter(currentChapterId);
            } else {
                showToast('发布失败', 'error');
            }
        } catch (e) {
            showToast('网络错误', 'error');
        } finally {
            hideLoading();
        }
    });
}

async function toggleLock() {
    if (!currentChapterId) return;

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    const isLocked = chapter.state === 'locked';
    const action = isLocked ? 'unlock' : 'lock';

    showLoading('操作中...', 0.3);

    try {
        const data = await api.post('/api/chapter/status/', { chapter_id: currentChapterId, action: action });
        if (data.success) {
            const newState = data.state;
            updateLocalChapter(currentChapterId, { state: newState });
            repdrrList();Lis
            selectChapter(currentChapterId);
            showToast(newState === 'locked' ? '章节已锁定' : '章节已解锁', 'success');
        } else {
            showToast(data.message || '操作失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

async function deleteChapter() {
    if (!currentChapterId) return;

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    showConfirm('删除章节', `确定要删除"${chapter.title}"吗？删除后章节将标记为已删除，您可以随时恢复。`, async () => {
        showLoading('删除中...', 0.3);

        try {
            const data = await api.post('/api/chapter/status/', { chapter_id: currentChapterId, action: 'soft_delete' });
            if (data.success) {
                showToast('章节已删除', 'success');
                // 更新本地数据为已删除状态
                updateLocalChapter(currentChapterId, { state: 'deleted' });
                refreshSingleChapterItem(currentChapterId);
                selectChapter(currentChapterId);
            } else {
                showToast(data.message || '删除失败', 'error');
            }
        } catch (e) {
            showToast('网络错误', 'error');
        } finally {
            hideLoading();
        }
    });
}

function updateLocalChapter(id, fields) {
    const idx = allChapters.findIndex(c => c.id === id);
    if (idx >= 0) {
        allChapters[idx] = { ...allChapters[idx], ...fields };
    }
}

function getStatusLabel(status) {
    if (status === 'summary') return '已生成概述';
    if (status === 'failed') return '生成失败';
    if (status === 'published') return '已发布';
    if (status === 'archived') return '已归档';
    return '草稿';
}

function getStatusBadgeClass(status) {
    if (status === 'summary') return 'badge-summary';
    if (status === 'failed') return 'badge-failed';
    if (status === 'published') return 'badge-published';
    if (status === 'archived') return 'badge-archived';
    return 'badge-draft';
}

function openModal(id) {
    document.getElementById(id).classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}

function showConfirm(title, message, callback) {
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').textContent = message;
    confirmCallback = callback;
    openModal('confirm-modal');
}

async function executeConfirm() {
    closeModal('confirm-modal');
    const callback = confirmCallback;
    confirmCallback = null;
    if (callback) {
        await callback();
    }
}

function showToast(message, type) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>${escapeHtml(message)}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ========== 相邻已删除章节检查 ==========

function checkAdjacentDeleted(chapterId) {
    const chapter = allChapters.find(c => c.id === chapterId);
    if (!chapter) return { prevDeleted: false, nextDeleted: false, prevChapter: null, nextChapter: null };

    const prevChapter = allChapters.find(c => c.chapter_number === chapter.chapter_number - 1 && c.state === 'deleted');
    const nextChapter = allChapters.find(c => c.chapter_number === chapter.chapter_number + 1 && c.state === 'deleted');

    return {
        prevDeleted: !!prevChapter,
        nextDeleted: !!nextChapter,
        prevChapter: prevChapter,
        nextChapter: nextChapter
    };
}

// 检查未保存修改，返回 true 表示可以继续
function checkUnsavedChanges(warningMsg) {
    if (!isDirty) return true;
    if (!confirm(warningMsg || '当前有未保存的修改，操作后将丢失。确定要继续吗？')) {
        return false;
    }
    isDirty = false;
    return true;
}

// 检查相邻已删除章节并弹窗提示，如果无需提示则直接执行 onContinue
function checkAdjacentDeletedAndPrompt(onContinue, actionLabel) {
    const adj = checkAdjacentDeleted(currentChapterId);
    const messages = [];
    if (adj.prevDeleted) messages.push(`上一章内容已经被删除，将不参与本次${actionLabel || '操作'}，是否继续？`);
    if (adj.nextDeleted) messages.push(`下一章内容已经被删除，将不参与本次${actionLabel || '操作'}，是否继续？`);

    if (messages.length > 0) {
        showDeletedWarning(messages, onContinue, () => {
            const target = adj.prevDeleted ? adj.prevChapter : adj.nextChapter;
            if (target) selectChapter(target.id);
        });
    } else {
        onContinue();
    }
}

// 显示相邻已删除章节警告模态框
function showDeletedWarning(messages, onConfirm, onGoRestore) {
    const messagesDiv = document.getElementById('deleted-warning-messages');
    messagesDiv.innerHTML = messages.map(msg => `<p style="margin-bottom:0.5rem; color:#fbbf24; font-weight:500;">${msg}</p>`).join('');

    const confirmBtn = document.getElementById('deleted-warning-confirm-btn');
    const goRestoreBtn = document.getElementById('deleted-warning-go-restore-btn');

    // 移除旧事件
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
    const newGoRestoreBtn = goRestoreBtn.cloneNode(true);
    goRestoreBtn.parentNode.replaceChild(newGoRestoreBtn, goRestoreBtn);

    newConfirmBtn.addEventListener('click', function() {
        closeModal('deleted-warning-modal');
        if (onConfirm) onConfirm();
    });
    newGoRestoreBtn.addEventListener('click', function() {
        closeModal('deleted-warning-modal');
        if (onGoRestore) onGoRestore();
    });

    openModal('deleted-warning-modal');
}

// ========== 恢复章节 ==========

async function restoreChapter() {
    if (!currentChapterId) return;

    showLoading('恢复中...', 0.3);

    try {
        const data = await api.post('/api/chapter/status/', { chapter_id: currentChapterId, action: 'restore' });
        if (data.success) {
            showToast('章节已恢复', 'success');
            updateLocalChapter(currentChapterId, { state: 'normal', status: data.status || 'draft' });
            refreshSingleChapterItem(currentChapterId);
        } else {
            showToast(data.message || '恢复失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// ========== 彻底删除章节 ==========

let hardDeleteChapterId = null;

function showHardDeleteModal() {
    if (!currentChapterId) return;

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    hardDeleteChapterId = currentChapterId;
    document.getElementById('hard-delete-message').textContent =
        `本次删除将彻底删除，且无法恢复。请输入章节名「${chapter.title}」确认删除：`;
    document.getElementById('hard-delete-input').value = '';
    document.getElementById('hard-delete-confirm-btn').disabled = true;

    openModal('hard-delete-modal');
}

function checkHardDeleteInput() {
    const chapter = allChapters.find(c => c.id === hardDeleteChapterId);
    if (!chapter) return;

    const inputValue = document.getElementById('hard-delete-input').value;
    document.getElementById('hard-delete-confirm-btn').disabled = inputValue !== chapter.title;
}

async function executeHardDelete() {
    if (!hardDeleteChapterId) return;

    closeModal('hard-delete-modal');
    showLoading('彻底删除中...', 0.3);

    try {
        const chapter = allChapters.find(c => c.id === hardDeleteChapterId);
        const confirmTitle = chapter ? chapter.title : '';
        const data = await api.post('/api/chapter/hard-delete/', { chapter_id: hardDeleteChapterId, confirm_title: confirmTitle });
        if (data.success) {
            showToast('章节已彻底删除', 'success');
            // 从本地列表移除
            allChapters = allChapters.filter(c => c.id !== hardDeleteChapterId);
            hardDeleteChapterId = null;
            currentChapterId = null;
            document.getElementById('chapter-title-input').value = '';
            document.getElementById('chapter-content-input').value = '';
            document.getElementById('chapter-summary-input').value = '';
            document.getElementById('current-chapter-label').textContent = '请选择章节';
            document.getElementById('editor-empty-state').style.display = '';
            document.getElementById('editor-content-area').style.display = 'none';
            renderChapterList();

            // 显示调整序号提示
            openModal('reorder-modal');
        } else {
            showToast(data.message || '彻底删除失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

async function executeReorder() {
    closeModal('reorder-modal');

    if (!currentVolumeId) {
        showToast('缺少卷信息', 'error');
        return;
    }

    showLoading('正在调整章节序号', 0.3);

    try {
        const data = await api.post('/api/chapter/reorder/', { volume_id: currentVolumeId });
        if (data.success) {
            showToast('章节序号已调整', 'success');
            await loadChaptersByVolume(currentVolumeId);
        } else {
            showToast(data.message || '调整序号失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    } finally {
        hideLoading();
    }
}

// ========== 拆分章节（弹窗对比模式） ==========

function updateSplitDesc() {
    const splitModeEl = document.querySelector('input[name="split-mode"]:checked');
    const splitMode = splitModeEl?.value;

    const modeDesc = document.getElementById('split-mode-desc');
    if (!splitMode) {
        modeDesc.textContent = '请选择拆分模式';
    } else if (splitMode === 'by_word_count') {
        modeDesc.textContent = '保留约前3000-3200字，剩余内容成为新章节';
    } else {
        modeDesc.textContent = '根据剧情自然断点拆分章节';
    }

    const handlingDesc = document.getElementById('split-handling-desc');
    const contentHandlingEl = document.querySelector('input[name="content-handling"]:checked');
    const contentHandling = contentHandlingEl?.value;
    if (!contentHandling) {
        handlingDesc.textContent = '请选择内容处理方式';
    } else if (contentHandling === 'insert_next') {
        handlingDesc.textContent = '将拆分内容插入下一章开头（如无下一章则新建）';
    } else {
        handlingDesc.textContent = '拆分内容作为新章节，自动调整序号';
    }

    const confirmBtn = document.querySelector('#split-modal .btn-gradient-primary');
    if (confirmBtn) {
        confirmBtn.disabled = !splitMode || !contentHandling;
    }
}

async function splitChapter() {
    if (!currentChapterId) return;
    if (currentEditorTab === 'summary') {
        showToast('概述模式下无法拆分', 'error');
        return;
    }

    checkAdjacentDeletedAndPrompt(openSplitModal, '拆分');
}

function openSplitModal() {
    // 重置选项：不默认选中
    document.querySelectorAll('input[name="split-mode"]').forEach(r => r.checked = false);
    document.querySelectorAll('input[name="content-handling"]').forEach(r => r.checked = false);
    updateSplitDesc();
    openModal('split-modal');
}

async function executeSplit() {
    const splitMode = document.querySelector('input[name="split-mode"]:checked')?.value || 'by_word_count';
    const contentHandling = document.querySelector('input[name="content-handling"]:checked')?.value || 'create_new';

    closeModal('split-modal');
    showLoading('拆分中...', 0.3);

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    const originalContent = chapter.content || '';
    const originalTitle = chapter.title || '';

    // 查找下一章（insert_next 模式需要）
    const nextChapter = contentHandling === 'insert_next' ?
        allChapters.find(c => c.chapter_number === chapter.chapter_number + 1 && c.state !== 'deleted') : null;

    // 重置对话session
    compareSession = {
        modifications: {},
        currentChapterNumber: null,
        chatHistory: [],
        isSaving: false,
        isSending: false,
    };

    try {
        let splitChapters = [];
        let modalOpened = false;
        let typingBuffer = '';  // 当前流式文本（未解析的 JSON）

        await api.streamRequestRaw('/api/chapter/split/', {
            body: { chapter_id: currentChapterId, split_mode: splitMode }
        }, (event) => {
            if (event.done) return;
            const parsed = event.data;
            if (parsed && parsed.type === 'chunk') {
                typingBuffer += parsed.content || '';

                // 首次收到 chunk 时打开弹窗
                if (!modalOpened) {
                    modalOpened = true;
                    hideLoading();
                    compareSession.currentChapterNumber = 1; // 临时值
                    compareSession.chatHistory = [];
                    document.getElementById('compare-chat-messages').innerHTML = '';
                    addCompareChatMessage('assistant', '章节拆分中，请稍候...');
                    // 禁用按钮
                    const saveBtn = document.getElementById('btn-compare-save');
                    const sendBtn = document.getElementById('btn-compare-chat-send');
                    if (saveBtn) saveBtn.disabled = true;
                    if (sendBtn) sendBtn.disabled = true;
                    openCompareModal();
                }

                // textarea 打字机效果
                const rowsContainer = document.getElementById('compare-rows');
                if (rowsContainer && rowsContainer.dataset.streaming !== 'true') {
                    rowsContainer.innerHTML = `
                        <div class="streaming-layout">
                            <div class="streaming-col">
                                <div class="streaming-header">生成中...</div>
                                <textarea class="streaming-textarea" readonly id="split-streaming-textarea"></textarea>
                            </div>
                        </div>
                    `;
                    rowsContainer.dataset.streaming = 'true';
                }
                const textarea = document.getElementById('split-streaming-textarea');
                if (textarea) {
                    textarea.value = typingBuffer;
                    textarea.scrollTop = textarea.scrollHeight;
                }
            } else if (parsed && parsed.type === 'split_chapter') {
                splitChapters.push(parsed);

                const chapNum = parsed.chapter_number || splitChapters.length;
                const chapTitle = parsed.title || '';
                const chapContent = parsed.content || '';

                // 确定原文和修改后内容
                let origContent = '';
                let origTitle = '';
                let chapId = null;
                let finalContent = chapContent; // 右侧显示的修改后内容

                if (chapNum === chapter.chapter_number) {
                    origContent = originalContent;
                    origTitle = originalTitle;
                    chapId = chapter.id;
                } else if (contentHandling === 'insert_next' && nextChapter) {
                    origContent = nextChapter.content || '';
                    origTitle = nextChapter.title || '';
                    chapId = nextChapter.id;
                    // insert_next: 拆分内容拼接在下一章开头
                    finalContent = chapContent + origContent;
                } else {
                    origContent = '';
                    origTitle = '';
                    chapId = null;
                }

                // 最终更新
                compareSession.modifications[chapNum] = {
                    chapter_id: chapId,
                    original: { title: origTitle, content: origContent },
                    modified: { title: chapTitle, content: finalContent },
                };

                // 清除 streaming 标记
                const rowsContainer = document.getElementById('compare-rows');
                if (rowsContainer) {
                    delete rowsContainer.dataset.streaming;
                }

                if (!modalOpened) {
                    modalOpened = true;
                    hideLoading();
                    compareSession.currentChapterNumber = chapNum;
                    compareSession.chatHistory = [];
                    document.getElementById('compare-chat-messages').innerHTML = '';
                    addCompareChatMessage('assistant', '章节拆分中，请稍候...');
                    openCompareModal();
                }

                typingBuffer = ''; // 重置，准备下一章
                compareSession.currentChapterNumber = chapNum;
                renderCompareChapterList();
                selectCompareChapter(chapNum);
            } else if (parsed && parsed.type === 'complete') {
                // 最终完成 - 启用按钮
                const saveBtn = document.getElementById('btn-compare-save');
                const sendBtn = document.getElementById('btn-compare-chat-send');
                if (saveBtn) saveBtn.disabled = false;
                if (sendBtn) sendBtn.disabled = false;

                if (compareSession.currentChapterNumber) {
                    selectCompareChapter(compareSession.currentChapterNumber);
                }
                const chatContainer = document.getElementById('compare-chat-messages');
                const bubbles = chatContainer.querySelectorAll('.ai-message.assistant .ai-message-bubble');
                if (bubbles.length > 0) {
                    bubbles[bubbles.length - 1].textContent = `章节已拆分为 ${splitChapters.length} 部分，请在对比区查看结果。您可以继续对话进行调整，然后点击保存。`;
                }
                renderCompareChapterList();
            } else if (parsed && parsed.type === 'error') {
                // 启用按钮
                const saveBtn = document.getElementById('btn-compare-save');
                const sendBtn = document.getElementById('btn-compare-chat-send');
                if (saveBtn) saveBtn.disabled = false;
                if (sendBtn) sendBtn.disabled = false;

                hideLoading();
                showToast(parsed.message || '拆分失败', 'error');
            }
        });
    } catch (e) {
        hideLoading();
        showToast('网络错误', 'error');
    }
}

// ========== 章节校验（check-modal 风格，支持勾选+意见+AI修复） ==========

let verifyResultIssues = [];  // 存储校验结果 issues

async function verifyChapter() {
    if (!currentChapterId) return;
    checkAdjacentDeletedAndPrompt(doVerifyChapter, '校验');
}

async function doVerifyChapter() {
    showLoading('校验中...', 0.3);
    verifyResultIssues = [];

    try {
        let fullVerification = '';
        await api.streamRequestRaw('/api/chapter/verify/', {
            body: { chapter_id: currentChapterId }
        }, (event) => {
            if (event.done) return;
            const data = event.data;
            if (!data) return;

            if (data.type === 'chunk' && data.content) {
                fullVerification += data.content;
            } else if (data.type === 'complete') {
                hideLoading();
                parseAndRenderVerifyResult(fullVerification);
            } else if (data.type === 'error') {
                hideLoading();
                showToast(data.message || '校验失败', 'error');
            }
        });
    } catch (e) {
        console.error('校验失败:', e);
        showToast('网络错误', 'error');
        hideLoading();
    }
}

function parseAndRenderVerifyResult(rawText) {
    const ITEM_START = '════ITEM_START════';
    const ITEM_END = '════ITEM_END════';
    const issues = [];

    let searchIdx = 0;
    while (true) {
        const startIdx = rawText.indexOf(ITEM_START, searchIdx);
        if (startIdx === -1) break;
        const endIdx = rawText.indexOf(ITEM_END, startIdx);
        if (endIdx === -1) break;

        const jsonStr = rawText.substring(startIdx + ITEM_START.length, endIdx).trim();
        try {
            const parsed = JSON.parse(jsonStr);
            if (parsed) issues.push(parsed);
        } catch (e) {
            console.warn('解析校验问题失败:', jsonStr);
        }
        searchIdx = endIdx + ITEM_END.length;
    }

    renderVerifyIssues(issues);
}

function renderVerifyIssues(issues) {
    const container = document.getElementById('verify-result');
    const emptyDiv = document.getElementById('verify-empty');
    const introDiv = document.getElementById('verify-intro');
    const fixBtn = document.getElementById('btn-verify-fix');

    container.innerHTML = '';

    if (!issues || issues.length === 0) {
        verifyResultIssues = [];
        introDiv.style.display = 'none';
        emptyDiv.style.display = 'block';
        fixBtn.style.display = 'none';
        openModal('verify-modal');
        return;
    }

    // 检查是否全部为 pass 类型
    const hasPass = issues.some(i => i.type === 'pass');
    if (hasPass && issues.length === 1) {
        verifyResultIssues = [];
        introDiv.style.display = 'none';
        emptyDiv.style.display = 'block';
        emptyDiv.innerHTML = '<i class="fa-solid fa-circle-check"></i><p>校验完成，未发现问题</p>';
        fixBtn.style.display = 'none';
        openModal('verify-modal');
        return;
    }

    // 过滤掉 pass 类型，只保留有问题的
    const realIssues = issues.filter(i => i.type !== 'pass');
    verifyResultIssues = realIssues;

    if (realIssues.length === 0) {
        introDiv.style.display = 'none';
        emptyDiv.style.display = 'block';
        emptyDiv.innerHTML = '<i class="fa-solid fa-circle-check"></i><p>校验完成，未发现问题</p>';
        fixBtn.style.display = 'none';
        openModal('verify-modal');
        return;
    }

    introDiv.style.display = '';
    emptyDiv.style.display = 'none';
    fixBtn.style.display = 'inline-block';

    const typeMap = {
        continuity: { label: '连贯性问题', cls: 'check-type-continuity-badge' },
        logic: { label: '逻辑问题', cls: 'check-type-logic-badge' },
        character: { label: '人物设定问题', cls: 'check-type-character-badge' },
        plot: { label: '情节问题', cls: 'check-type-plot-badge' },
        consistency: { label: '一致性问题', cls: 'check-type-consistency-badge' },
    };

    const htmlParts = realIssues.map((issue, idx) => {
        const typeInfo = typeMap[issue.type] || { label: issue.type || '其他问题', cls: '' };
        const suggestion = issue.suggestion || '';
        return `
            <div class="check-issue" data-issue-idx="${idx}">
                <div class="check-issue-type-row">
                    <label class="check-issue-checkbox-label">
                        <input type="checkbox" class="check-issue-checkbox" data-issue-idx="${idx}" checked>
                        <span class="check-issue-type-badge ${typeInfo.cls}">${typeInfo.label}</span>
                    </label>
                </div>
                <div class="check-issue-desc-row">
                    <span class="check-issue-desc-label">问题</span>
                    <span class="check-issue-desc-text">${escapeHtml(issue.description || typeInfo.label)}</span>
                </div>
                ${suggestion ? `
                <div class="check-issue-suggestion-row">
                    <span class="check-issue-suggestion-label">建议</span>
                    <span class="check-issue-suggestion-text">${escapeHtml(suggestion)}</span>
                </div>` : ''}
                <div class="check-issue-input-row">
                    <div class="check-issue-input-cell">
                        <textarea placeholder="输入修改意见（选填，留空则按 AI 建议修复）..." class="check-issue-user-input"></textarea>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = htmlParts.join('');
    openModal('verify-modal');
}

function closeVerifyModal() {
    closeModal('verify-modal');
    verifyResultIssues = [];
}

async function fixVerifyIssues() {
    const issueCards = document.querySelectorAll('#verify-result .check-issue');
    const selectedIssues = [];

    issueCards.forEach((card, idx) => {
        const checkbox = card.querySelector('.check-issue-checkbox');
        if (checkbox && checkbox.checked) {
            const userInput = card.querySelector('.check-issue-user-input');
            const userComment = userInput ? userInput.value.trim() : '';
            const issue = verifyResultIssues[idx];
            if (issue) {
                // 如果用户没填想法，用 LLM 的建议
                const finalComment = userComment || (issue.suggestion || '');
                selectedIssues.push({
                    type: issue.type,
                    description: issue.description,
                    suggestion: issue.suggestion,
                    user_comment: finalComment,
                });
            }
        }
    });

    if (selectedIssues.length === 0) {
        showToast('请至少选择一个需要修复的问题', 'warning');
        return;
    }

    // 构建 issues_text 传给后端
    const issuesText = selectedIssues.map((item, i) => {
        let text = `问题${i + 1}[${item.type}]: ${item.description}`;
        if (item.user_comment) text += `\n用户意见: ${item.user_comment}`;
        return text;
    }).join('\n\n');

    closeModal('verify-modal');

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    showLoading('AI修复中...', 0.3);

    try {
        let fullContent = '';
        await api.streamRequestRaw('/api/chapter/verify-fix/', {
            body: {
                chapter_id: currentChapterId,
                issues_text: issuesText,
            }
        }, (event) => {
            if (event.done) return;
            const data = event.data;
            if (!data) return;

            if (data.type === 'chunk' && data.content) {
                fullContent += data.content;
                document.getElementById('chapter-content-input').value = fullContent;
            } else if (data.type === 'complete') {
                hideLoading();
                document.getElementById('chapter-content-input').value = fullContent;
                updateLocalChapter(currentChapterId, {
                    content: fullContent,
                    word_count: fullContent.length,
                    status: 'draft',
                });
                refreshSingleChapterItem(currentChapterId);
                updateEmptyContentPlaceholder();
                updateEditorButtons();
                showToast('AI修复完成！', 'success');
            } else if (data.type === 'error') {
                hideLoading();
                showToast(data.message || '修复失败', 'error');
            }
        });
    } catch (e) {
        console.error('修复失败:', e);
        showToast('网络错误', 'error');
        hideLoading();
    }
}
async function generateSingleChapterContent() {
    if (!currentChapterId) return;

    if (!checkUnsavedChanges('当前有未保存的修改，生成新内容后将丢失。确定要继续吗？')) return;

    const chapter = allChapters.find(c => c.id === currentChapterId);
    if (!chapter) return;

    checkAdjacentDeletedAndPrompt(() => doGenerateSingleChapterContent(chapter), '生成/调整/校验');
}

async function doGenerateSingleChapterContent(chapter) {
    showLoading(`正在生成第${chapter.chapter_number}章: ${chapter.title}\n已完成0/1 章`, 0.1);

    try {
        let fullContent = '';
        await api.streamRequestRaw('/api/chapter/content/', {
            body: { chapter_id: currentChapterId }
        }, (event) => {
            if (event.done) return;
            const data = event.data;
            if (!data) return;

            if (data.type === 'chunk' && data.content) {
                fullContent += data.content;
                document.getElementById('chapter-content-input').value = fullContent;
            } else if (data.type === 'complete') {
                hideLoading();
                document.getElementById('chapter-content-input').value = fullContent;
                updateLocalChapter(currentChapterId, { content: fullContent, word_count: fullContent.length, status: 'draft' });
                refreshSingleChapterItem(currentChapterId);
                updateEmptyContentPlaceholder();
                updateEditorButtons();
                showToast('内容生成成功！', 'success');
            } else if (data.type === 'error') {
                hideLoading();
                showToast('生成失败: ' + data.message, 'error');
            }
        });
    } catch (e) {
        console.error('生成内容失败:', e);
        showToast('生成失败: ' + e.message, 'error');
        hideLoading();
    }
}
