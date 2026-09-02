/**
 * 知识图谱可视化 - Cytoscape.js
 */
(function () {
    'use strict';

    var cy = null;
    var graphData = null;
    var projectId = null;

    var EDGE_COLORS = {
        '\u670b\u53cb': '#22c55e', '\u604b\u4eba': '#ec4899', '\u914d\u5076': '#f43f5e',
        '\u7236\u6bcd': '#f59e0b', '\u5b50\u5973': '#f59e0b', '\u5144\u5f1f\u59d0\u59b9': '#eab308',
        '\u5e08\u7236': '#a855f7', '\u5f92\u5f1f': '#c084fc', '\u654c\u4eba': '#ef4444',
        '\u5bf9\u624b': '#f97316', '\u5bfc\u5e08': '#8b5cf6', '\u95e8\u751f': '#a78bfa',
        '\u76df\u53cb': '#06b6d4', '\u4eb2\u5c5e': '#fbbf24', '\u541b\u4e3b': '#7c3aed',
        '\u81e3\u5b50': '#8b5cf6', '\u5176\u4ed6': '#6b7280', '\u6240\u5c5e': '#475569',
    };
    var EDGE_HIGHLIGHT = '#22d3ee';

    function $(id) { return document.getElementById(id); }

    document.addEventListener('DOMContentLoaded', function () {
        projectId = getProjectId();
        if (!projectId) { showToast('\u65e0\u6cd5\u83b7\u53d6\u9879\u76ee ID', 'error'); return; }
        bindEvents();
        loadData();
    });

    function getProjectId() {
        var m = window.location.pathname.match(/\/(\d+)\/graph/);
        if (m) return m[1];
        return new URLSearchParams(window.location.search).get('project_id');
    }

    // ========== 事件绑定 ==========
    function bindEvents() {
        var backBtn = $('backBtn');
        var rebuildBtn = $('rebuildBtn');
        var emptyRebuildBtn = $('emptyRebuildBtn');
        var fullscreenBtn = $('fullscreenBtn');
        var detailCloseBtn = $('detailCloseBtn');
        var searchInput = $('searchInput');
        var searchClear = $('searchClear');

        if (backBtn) backBtn.onclick = function () { window.location.href = '/' + projectId + '/'; };
        if (rebuildBtn) rebuildBtn.onclick = doRebuild;
        if (emptyRebuildBtn) emptyRebuildBtn.onclick = doRebuild;
        if (fullscreenBtn) fullscreenBtn.onclick = toggleFullscreen;
        if (detailCloseBtn) detailCloseBtn.onclick = function () { hideDetail(); clearHL(); };

        var timer = null;
        if (searchInput) searchInput.oninput = function () {
            var v = this.value.trim();
            if (searchClear) searchClear.style.display = v ? 'block' : 'none';
            clearTimeout(timer);
            timer = setTimeout(function () { doSearch(v); }, 200);
        };
        if (searchClear) searchClear.onclick = function () {
            if (searchInput) searchInput.value = '';
            this.style.display = 'none';
            clearHL();
        };

        document.querySelectorAll('.node-type-filter').forEach(function (cb) {
            cb.onchange = applyFilters;
        });
    }

    // ========== 数据加载 ==========
    function loadData() {
        showEl('loadingOverlay', true);
        api.get('/api/projects/' + projectId + '/graph/').then(function (gr) {
            if (!gr || !gr.success) { showToast(gr && gr.error || '\u52a0\u8f7d\u5931\u8d25', 'error'); showEl('emptyState', true); showEl('loadingOverlay', false); return; }
            graphData = gr.data;
            if (gr.data.stats) { renderFilters(gr.data.stats.edges_by_type); updateStats(gr.data.stats); }
            if (!graphData.nodes.length) { showEl('emptyState', true); showEl('loadingOverlay', false); return; }
            initGraph();
            showEl('emptyState', false);
            showEl('loadingOverlay', false);
        }).catch(function (e) {
            console.error(e);
            showToast('\u52a0\u8f7d\u5931\u8d25: ' + e.message, 'error');
            showEl('emptyState', true);
            showEl('loadingOverlay', false);
        });
    }

    // ========== Cytoscape 初始化 ==========
    function initGraph() {
        if (cy) { cy.destroy(); cy = null; }
        var container = $('cy');
        if (!container) return;
        container.innerHTML = '';

        var degMap = {};
        graphData.edges.forEach(function (e) {
            degMap[e.source_id] = (degMap[e.source_id] || 0) + 1;
            degMap[e.target_id] = (degMap[e.target_id] || 0) + 1;
        });

        var elems = [];
        graphData.nodes.forEach(function (n) {
            elems.push({ group: 'nodes', data: { id: 'n' + n.id, label: n.name, ntype: n.node_type, desc: n.description, props: n.properties, deg: degMap[n.id] || 0, dbId: n.id } });
        });
        graphData.edges.forEach(function (e) {
            elems.push({ group: 'edges', data: { id: 'e' + e.id, source: 'n' + e.source_id, target: 'n' + e.target_id, etype: e.edge_type, desc: e.description, bidir: e.is_bidirectional } });
        });

        cy = cytoscape({
            container: container,
            elements: elems,
            style: getStyle(),
            layout: {
                name: 'cose', animate: false,
                nodeRepulsion: function () { return 6000; },
                idealEdgeLength: function (e) { return e.data('etype') === '\u6240\u5c5e' ? 80 : 140; },
                edgeElasticity: function () { return 100; },
                gravity: 0.25, numIter: 300, padding: 50,
                nodeDimensionsIncludeLabels: true,
                initialTemp: 300, coolingFactor: 0.95,
            },
            minZoom: 0.05, maxZoom: 5,
            boxSelectionEnabled: false,
            wheelSensitivity: 0.2,
        });

        window._cy = cy;
        cy.on('tap', 'node', function (evt) { var nd = evt.target; highlight(nd); showDetail(nd); });
        cy.on('tap', function (evt) { if (evt.target === cy) { clearHL(); hideDetail(); } });
        cy.on('mouseover', 'node', function () { container.style.cursor = 'pointer'; });
        cy.on('mouseout', 'node', function () { container.style.cursor = 'default'; });

        // 平滑缩放：拦截滚轮事件，用更小的缩放因子
        container.addEventListener('wheel', function (e) {
            e.preventDefault();
            var factor = e.deltaY > 0 ? 0.9 : 1.1;
            var pt = { x: e.offsetX, y: e.offsetY };
            var newZoom = cy.zoom() * factor;
            newZoom = Math.max(cy.minZoom(), Math.min(cy.maxZoom(), newZoom));
            cy.zoom({ level: newZoom, renderedPosition: pt });
        }, { passive: false });
    }

    // ========== 样式 ==========
    function getStyle() {
        var s = [
            { selector: 'node[ntype="character"]', style: {
                'background-color': '#6366f1', 'border-color': '#818cf8', 'border-width': 2,
                'label': 'data(label)', 'color': '#e0e7ff', 'font-size': '11px',
                'text-valign': 'bottom', 'text-margin-y': 8, 'text-halign': 'center',
                'text-outline-color': '#0f172a', 'text-outline-width': 2.5,
                'text-wrap': 'ellipsis', 'text-max-width': '80px',
                'width': function (el) { return Math.max(36, Math.min(58, 30 + el.data('deg') * 5)); },
                'height': function (el) { return Math.max(36, Math.min(58, 30 + el.data('deg') * 5)); },
            }},
            { selector: 'node[ntype="faction"]', style: {
                'background-color': '#ef4444', 'border-color': '#f87171', 'border-width': 2.5,
                'shape': 'hexagon', 'label': 'data(label)', 'color': '#fecaca',
                'font-size': '12px', 'font-weight': 'bold',
                'text-valign': 'bottom', 'text-margin-y': 10, 'text-halign': 'center',
                'text-outline-color': '#0f172a', 'text-outline-width': 2.5,
                'width': 48, 'height': 48,
            }},
            { selector: 'edge', style: {
                'width': 1.5, 'line-color': '#475569', 'target-arrow-color': '#475569',
                'target-arrow-shape': 'triangle', 'arrow-scale': 0.6,
                'curve-style': 'bezier', 'label': '', 'opacity': 0.6,
                'font-size': '9px', 'color': '#94a3b8', 'text-rotation': 'autorotate',
                'text-margin-y': -10, 'text-outline-color': '#0f172a', 'text-outline-width': 2,
            }},
        ];
        Object.keys(EDGE_COLORS).forEach(function (t) {
            s.push({ selector: 'edge[etype="' + t + '"]', style: { 'line-color': EDGE_COLORS[t], 'target-arrow-color': EDGE_COLORS[t] } });
        });
        s.push({ selector: 'edge[?bidir]', style: { 'source-arrow-shape': 'triangle', 'source-arrow-color': '#475569' } });
        s.push({ selector: 'edge[etype="\u6240\u5c5e"]', style: { 'line-style': 'dashed', 'line-dash-pattern': [5, 3], 'opacity': 0.35, 'width': 1 } });
        s.push({ selector: 'node.highlighted', style: { 'border-width': 4, 'border-color': EDGE_HIGHLIGHT, 'z-index': 10 } });
        s.push({ selector: 'edge.highlighted', style: { 'line-color': EDGE_HIGHLIGHT, 'target-arrow-color': EDGE_HIGHLIGHT, 'source-arrow-color': EDGE_HIGHLIGHT, 'width': 2.5, 'opacity': 1, 'z-index': 10, 'label': 'data(etype)', 'font-size': '10px' } });
        s.push({ selector: '.faded', style: { 'opacity': 0.1 } });
        s.push({ selector: 'node.search-match', style: { 'border-width': 4, 'border-color': '#fbbf24', 'z-index': 20 } });
        return s;
    }

    // ========== 高亮 ==========
    function highlight(node) {
        cy.elements().removeClass('highlighted faded');
        var nb = node.closedNeighborhood();
        cy.elements().addClass('faded');
        nb.removeClass('faded').addClass('highlighted');
    }
    function clearHL() { if (cy) cy.elements().removeClass('highlighted faded search-match'); }

    // ========== 搜索 ==========
    function doSearch(q) {
        if (!cy) return;
        cy.elements().removeClass('search-match highlighted faded');
        if (!q) return;
        var ms = cy.nodes().filter(function (n) { return n.data('label').indexOf(q) >= 0; });
        if (ms.length) {
            cy.elements().addClass('faded');
            ms.removeClass('faded').addClass('search-match');
            cy.animate({ fit: { eles: ms, padding: 80 }, duration: 400 });
        }
    }

    // ========== 右侧详情面板 ==========
    function showDetail(node) {
        var d = node.data();
        var panel = $('nodeDetail');
        if (!panel) return;
        panel.classList.add('open');

        if ($('detailName')) $('detailName').textContent = d.label;
        if ($('detailType')) {
            $('detailType').textContent = d.ntype === 'character' ? '\u89d2\u8272' : '\u52bf\u529b';
            $('detailType').className = 'detail-type type-' + d.ntype;
        }
        if ($('detailDesc')) $('detailDesc').textContent = d.desc || '';

        var propsEl = $('detailProps');
        if (propsEl) {
            propsEl.innerHTML = '';
            if (d.props) {
                var labels = { role_type: '\u5b9a\u4f4d', gender: '\u6027\u522b', age: '\u5e74\u9f84', identity: '\u8eab\u4efd', faction: '\u52bf\u529b' };
                Object.keys(labels).forEach(function (k) {
                    var v = d.props[k];
                    if (v !== undefined && v !== null && v !== '') {
                        propsEl.innerHTML += '<div class="prop-row"><span class="prop-key">' + labels[k] + ':</span><span>' + v + '</span></div>';
                    }
                });
            }
        }

        var relEl = $('detailRelations');
        if (relEl) {
            relEl.innerHTML = '';
            var edges = node.connectedEdges();
            if (edges.length) {
                relEl.innerHTML = '<div style="font-size:12px;color:#64748b;margin-bottom:6px;font-weight:600;">\u5173\u7cfb (' + edges.length + ')</div>';
                edges.forEach(function (edge) {
                    var isSrc = edge.data('source') === d.id;
                    var otherId = isSrc ? edge.data('target') : edge.data('source');
                    var other = cy.getElementById(otherId);
                    var arrow = isSrc ? '\u2192' : '\u2190';
                    var div = document.createElement('div');
                    div.className = 'rel-item';
                    div.innerHTML = arrow + ' <span class="rel-type">' + edge.data('etype') + '</span> ' + other.data('label');
                    div.onclick = function () { highlight(other); showDetail(other); cy.animate({ center: { eles: other }, duration: 300 }); };
                    relEl.appendChild(div);
                });
            }
        }

        var fb = $('detailFocusBtn');
        if (fb) { fb.style.display = 'inline-flex'; fb.onclick = function () { cy.animate({ fit: { eles: node.closedNeighborhood(), padding: 80 }, duration: 400 }); }; }
    }
    function hideDetail() { var p = $('nodeDetail'); if (p) p.classList.remove('open'); }

    // ========== 筛选 ==========
    function renderFilters(byType) {
        var c = $('edgeTypeFilters');
        if (!c) return;
        c.innerHTML = '';
        var colors = { '\u670b\u53cb': '#22c55e', '\u604b\u4eba': '#ec4899', '\u914d\u5076': '#f43f5e', '\u7236\u6bcd': '#f59e0b', '\u5b50\u5973': '#f59e0b', '\u5144\u5f1f\u59d0\u59b9': '#eab308', '\u5e08\u7236': '#8b5cf6', '\u5f92\u5f1f': '#8b5cf6', '\u5bfc\u5e08': '#8b5cf6', '\u95e8\u751f': '#8b5cf6', '\u654c\u4eba': '#ef4444', '\u5bf9\u624b': '#f97316', '\u76df\u53cb': '#06b6d4', '\u4eb2\u5c5e': '#f59e0b', '\u541b\u4e3b': '#a855f7', '\u81e3\u5b50': '#a855f7', '\u6240\u5c5e': '#6b7280', '\u5176\u4ed6': '#6b7280' };
        Object.keys(byType).forEach(function (t) {
            var lb = document.createElement('label');
            lb.className = 'filter-checkbox';
            var col = colors[t] || '#6b7280';
            lb.innerHTML = '<input type="checkbox" class="edge-type-filter" value="' + t + '" checked><span class="filter-dot" style="background:' + col + ';"></span> ' + t + ' <span style="color:#475569;font-size:11px;">(' + byType[t] + ')</span>';
            c.appendChild(lb);
        });
        c.querySelectorAll('.edge-type-filter').forEach(function (cb) { cb.onchange = applyFilters; });
    }

    function applyFilters() {
        if (!cy) return;
        var ntypes = [];
        document.querySelectorAll('.node-type-filter:checked').forEach(function (cb) { ntypes.push(cb.value); });
        var etypes = [];
        document.querySelectorAll('.edge-type-filter:checked').forEach(function (cb) { etypes.push(cb.value); });
        cy.nodes().forEach(function (n) { n.style('display', ntypes.indexOf(n.data('ntype')) >= 0 ? 'element' : 'none'); });
        cy.edges().forEach(function (e) {
            var src = cy.getElementById(e.data('source'));
            var tgt = cy.getElementById(e.data('target'));
            var vis = src.style('display') !== 'none' && tgt.style('display') !== 'none' && etypes.indexOf(e.data('etype')) >= 0;
            e.style('display', vis ? 'element' : 'none');
        });
    }

    // ========== 重建 ==========
    function doRebuild() {
        showConfirmModal({
            title: '\u91cd\u5efa\u56fe\u8c31',
            message: '\u786e\u5b9a\u8981\u91cd\u5efa\u56fe\u8c31\u5417\uff1f\u8fd9\u5c06\u4ece\u6240\u6709\u89d2\u8272\u6570\u636e\u91cd\u65b0\u751f\u6210\u56fe\u8c31\u3002',
            onConfirm: function (close) {
                close();
                var btn = $('rebuildBtn');
                if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> \u91cd\u5efa\u4e2d...'; }
                api.post('/api/projects/' + projectId + '/graph/rebuild/').then(function (r) {
                    if (r && r.success) { showToast('\u56fe\u8c31\u91cd\u5efa\u6210\u529f', 'success'); setTimeout(loadData, 1000); }
                    else showToast(r && r.error || '\u91cd\u5efa\u5931\u8d25', 'error');
                    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-sync-alt"></i> \u91cd\u5efa'; }
                }).catch(function (e) {
                    showToast('\u91cd\u5efa\u5931\u8d25: ' + e.message, 'error');
                    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-sync-alt"></i> \u91cd\u5efa'; }
                });
            }
        });
    }

    // ========== 统计 ==========
    function updateStats(st) {
        if ($('statsNodes')) $('statsNodes').textContent = '\u8282\u70b9: ' + st.total_nodes;
        if ($('statsEdges')) $('statsEdges').textContent = '\u5173\u7cfb: ' + st.total_edges;
        if ($('statsFactions')) $('statsFactions').textContent = '\u52bf\u529b: ' + (st.nodes_by_type.faction || 0);
    }

    // ========== 全屏 ==========
    function toggleFullscreen() {
        var body = document.querySelector('.page-full-height');
        if (body) body.classList.toggle('graph-fullscreen');
        if (cy) setTimeout(function () { cy.resize(); }, 100);
    }

    // ========== 工具 ==========
    function showEl(id, show) { var el = $(id); if (el) el.style.display = show ? 'flex' : 'none'; }
})();
