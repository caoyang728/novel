document.addEventListener('DOMContentLoaded', function() {
    showLoading('加载中...');
    Promise.all([loadUserInfo(), loadStats('today')]).finally(() => hideLoading());
});

async function loadStats(range, btnElement) {
    if (btnElement) {
        document.querySelectorAll('.btn-outline-primary').forEach(el => el.classList.remove('active'));
        btnElement.classList.add('active');
    }

    try {
        const data = await api.get(`/api/token-usage/stats/?range=${range}`);
        if (!data || !data.success) {
            showError('加载统计数据失败，请重试');
            return;
        }
        const usage = data.usage;
        const currentUsage = usage[range] || usage.all || {};
        const isEstimated = currentUsage.input_cache_hit_tokens === 0 && currentUsage.input_cache_miss_tokens === 0;

        document.getElementById('stat-input').textContent = formatTokenCount(currentUsage.input_tokens);
        document.getElementById('stat-output').textContent = formatTokenCount(currentUsage.output_tokens);
        document.getElementById('stat-cache-hit').textContent = isEstimated ? '-' : formatTokenCount(currentUsage.input_cache_hit_tokens);
        document.getElementById('stat-cache-miss').textContent = isEstimated ? '-' : formatTokenCount(currentUsage.input_cache_miss_tokens);
        document.getElementById('stat-cost').textContent = currentUsage.cost > 0 ? '¥' + currentUsage.cost.toFixed(4) : '-';

        renderLogsTable(data.usage.logs || []);
        renderProjectStats(data.usage.project_stats || []);
    } catch (error) {
        console.error('Failed to load stats:', error);
        showError('加载统计数据失败，请重试');
    }
}

function renderLogsTable(logs) {
    const tbody = document.getElementById('logs-table-body');
    if (!tbody) return;

    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">暂无数据</td></tr>';
        return;
    }

    tbody.innerHTML = logs.map(log => {
        const dateStr = escapeHtml(log.created_at || '-');
        const project = escapeHtml(log.project || '-');
        const taskType = escapeHtml(getTaskTypeText(log.task_type));
        const inputTokens = formatTokenCount(log.input_tokens);
        const outputTokens = formatTokenCount(log.output_tokens);
        const isEstimated = log.input_cache_hit_tokens === 0 && log.input_cache_miss_tokens === 0;
        const cacheHit = isEstimated ? '<span class="token-estimated">预估</span>' : formatTokenCount(log.input_cache_hit_tokens);
        const cacheMiss = isEstimated ? '<span class="token-estimated">预估</span>' : formatTokenCount(log.input_cache_miss_tokens);
        const cost = parseFloat(log.cost || 0) > 0 ? '¥' + parseFloat(log.cost).toFixed(4) : '-';
        return `<tr>
            <td>${dateStr}</td>
            <td>${project}</td>
            <td>${taskType}</td>
            <td>${inputTokens}</td>
            <td>${outputTokens}</td>
            <td>${cacheHit}</td>
            <td>${cacheMiss}</td>
            <td>${cost}</td>
        </tr>`;
    }).join('');
}

function renderProjectStats(stats) {
    const container = document.getElementById('project-stats');
    if (!container) return;

    if (stats.length === 0) {
        container.innerHTML = '<div class="text-center text-muted">暂无数据</div>';
        return;
    }

    container.innerHTML = stats.map(stat => {
        const title = escapeHtml(stat.project_title || '-');
        const totalTokens = formatTokenCount(stat.total_tokens);
        const inputTokens = formatTokenCount(stat.input_tokens);
        const outputTokens = formatTokenCount(stat.output_tokens);
        const isEstimated = stat.input_cache_hit_tokens === 0 && stat.input_cache_miss_tokens === 0;
        const cacheHit = isEstimated ? '预估' : formatTokenCount(stat.input_cache_hit_tokens);
        const cacheMiss = isEstimated ? '预估' : formatTokenCount(stat.input_cache_miss_tokens);
        const cost = stat.cost > 0 ? '¥' + stat.cost.toFixed(4) : '-';
        const maxTokens = stats[0].total_tokens || 1;
        const percent = Math.min((stat.total_tokens / maxTokens) * 100, 100);
        return `<div class="project-stat-card">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="mb-0">${title}</h6>
                <span class="badge badge-info">${totalTokens} tokens · ${cost}</span>
            </div>
            <div class="progress" style="height: 6px;">
                <div class="progress-bar" style="width: ${percent}%"></div>
            </div>
            <div class="d-flex justify-content-between mt-2 small text-muted">
                <span>输入: ${inputTokens}</span>
                <span>输出: ${outputTokens}</span>
                <span>命中: ${cacheHit}</span>
                <span>未命中: ${cacheMiss}</span>
            </div>
        </div>`;
    }).join('');
}

function getTaskTypeText(taskType) {
    const texts = {
        'outline': '大纲-大纲生成',
        'volume_analysis': '卷-大纲分析',
        'volume_generate': '卷-批量生成',
        'volume_optimize': '卷-批量优化',
        'volume_chat': '卷-聊天',
        'volume_chat_merge': '卷-跨卷合并',
        'volume_single_optimize': '卷-单卷优化',
        'volume_single_generate': '卷-单卷生成',
        'chapter_outline': '章节-概要生成',
        'chapter_content': '章节-内容生成',
        'chapter_verify': '章节-校验',
        'chapter_verify_fix': '章节-校验修复',
        'chapter_split': '章节-拆分',
        'chapter_chat': '章节-对话写作',
        'character_generate': '角色-角色生成',
        'character_polish': '角色-角色润色',
        'character_check': '角色-角色检测',
        'character_optimize': '角色-角色优化',
        'timeline_generate': '时间线-生成',
        'timeline_chat': '时间线-聊天',
        'timeline_single_optimize': '时间线-单项优化',
        'timeline_generate_fields': '时间线-字段生成',
        'timeline_merge': '时间线-合并',
        'timeline_check': '时间线-一致性检查',
        'timeline_check_optimize': '时间线-一致性修复',
        'worldview_deepen': '世界观-宏观缺口检测',
        'worldview_deepen_integrate': '世界观-缺口检测整合',
        'worldview_consistency': '世界观-宏观一致性检查',
        'worldview_consistency_fix': '世界观-宏观一致性修复',
        'faction_design': '世界观-阵营生成',
        'location_design': '世界观-地点生成',
        'relation_generate': '世界观-关系生成',
        'worldview_foundation': '世界观-世界基础生成',
        'worldview_power': '世界观-力量体系生成',
        'worldview_races': '世界观-种族族群生成',
        'worldview_society': '世界观-组织势力生成',
        'worldview_culture': '世界观-文化习俗生成',
        'worldview_history': '世界观-重要事件生成',
        'worldview_special': '世界观-特殊规则生成',
        'worldview_setting': '世界观-基础设定生成',
        'worldview_init_question': '世界观-引导问题',
        'worldview_chat': '世界观-聊天',
        'project_title_suggest_json': '项目-书名建议',
        'project_description_suggest': '项目-简介建议',
        'project_info_generate': '项目-信息生成',
        'project_title_suggest': '项目-书名建议',
        'project_title_rewrite': '项目-书名改写',
        'project_description_optimize': '项目-简介优化',
        'project_enhance_description': '项目-描述完善',
        'note_polish': '随手记-AI整理',
        'other': '其他任务'
    };
    return texts[taskType] || taskType;
}


