/**
 * 高考志愿推荐系统 - 前端主逻辑
 */

function getAppBasePath() {
    const path = window.location.pathname;
    if (!path || path === '/') return '';
    if (path.endsWith('/')) return path.replace(/\/$/, '');
    return path.slice(0, path.lastIndexOf('/'));
}

const API_BASE = `${getAppBasePath()}/api`;

// ============ DOM Elements ============
const $  = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

const DOM = {
    scoreInput:     $('scoreInput'),
    rankInput:      $('rankInput'),
    btnSearch:      $('btnSearch'),
    sortBy:         $('sortBy'),
    loading:        $('loadingOverlay'),
    errorBanner:    $('errorBanner'),
    errorMsg:       $('errorMsg'),
    errorClose:     $('errorClose'),
    welcomeSection: $('welcomeSection'),
    resultSection:  $('resultSection'),
    // stats
    statScore:   $('statScore'),
    statRank:    $('statRank'),
    statTotal:   $('statTotal'),
    statInProv:  $('statInProv'),
    statOutProv: $('statOutProv'),
    statReach:   $('statReach'),
    statMatch:   $('statMatch'),
    statSafety:  $('statSafety'),
    statBatchLine:  $('statBatchLine'),
    statSpecialLine: $('statSpecialLine'),
    // tab counts
    tabReachCount:  $('tabReachCount'),
    tabMatchCount:  $('tabMatchCount'),
    tabSafetyCount: $('tabSafetyCount'),
    // lists
    listReach:  $('listReach'),
    listMatch:  $('listMatch'),
    listSafety: $('listSafety'),
};

// ============ State ============
let currentData = null;   // 最近一次推荐结果
let scoreLinesData = null; // 批次线数据缓存
let conversionTimer = null;
let conversionSeq = 0;
let syncingInputs = false;
let lastInputSource = null;

// ============ API Functions ============

async function apiFetch(url) {
    const res = await fetch(API_BASE + url);
    if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `请求失败 (${res.status})`);
    }
    const json = await res.json();
    if (!json.success) {
        throw new Error(json.error?.message || '接口返回错误');
    }
    return json.data;
}

function fetchRecommendations(params) {
    const qs = new URLSearchParams();
    if (params.score)      qs.set('score', params.score);
    if (params.rank)       qs.set('rank', params.rank);
    if (params.school_type) qs.set('school_type', params.school_type);
    if (params.province)   qs.set('province', params.province);
    if (params.sort_by)    qs.set('sort_by', params.sort_by);
    return apiFetch('/recommend?' + qs.toString());
}

function fetchConversion(params) {
    const qs = new URLSearchParams();
    if (params.score) qs.set('score', params.score);
    if (params.rank) qs.set('rank', params.rank);
    return apiFetch('/convert?' + qs.toString());
}

function fetchSchoolDetail(schoolId) {
    return apiFetch(`/school/${schoolId}`);
}

function fetchSchoolMajors(schoolId) {
    return apiFetch(`/school/${schoolId}/majors`);
}

function fetchScoreLines() {
    return apiFetch('/score-lines');
}

function fetchHotMajors() {
    return apiFetch('/hot-majors?top_n=10');
}

// ============ UI Helpers ============

function showLoading() { DOM.loading.classList.add('show'); }
function hideLoading() { DOM.loading.classList.remove('show'); }

function showError(msg) {
    DOM.errorMsg.textContent = msg;
    DOM.errorBanner.style.display = 'flex';
}
function hideError() { DOM.errorBanner.style.display = 'none'; }

function getSchoolTypeFilter() {
    const checked = [...$$('input[name="schoolType"]:checked')].map(el => el.value).filter(Boolean);
    // 如果选了"全部"或者什么都没选，返回空
    const allCheckbox = document.querySelector('input[name="schoolType"][value=""]');
    if (allCheckbox && allCheckbox.checked) return '';
    return checked.join(',');
}

function getProvinceFilter() {
    const el = document.querySelector('input[name="province"]:checked');
    return el ? el.value : '';
}

function scheduleInputConversion(source) {
    if (syncingInputs) return;
    lastInputSource = source;
    clearTimeout(conversionTimer);

    conversionTimer = setTimeout(async () => {
        const seq = ++conversionSeq;
        const score = DOM.scoreInput.value.trim();
        const rank = DOM.rankInput.value.trim();

        if (source === 'score') {
            const scoreNum = Number(score);
            if (!score || scoreNum < 0 || scoreNum > 750) return;
            try {
                const data = await fetchConversion({ score });
                if (seq !== conversionSeq || data.rank == null) return;
                syncingInputs = true;
                DOM.rankInput.value = data.rank;
                syncingInputs = false;
                hideError();
            } catch (err) {
                syncingInputs = false;
            }
        } else if (source === 'rank') {
            const rankNum = Number(rank);
            if (!rank || rankNum < 1) return;
            try {
                const data = await fetchConversion({ rank });
                if (seq !== conversionSeq || data.score == null) return;
                syncingInputs = true;
                DOM.scoreInput.value = data.score;
                syncingInputs = false;
                hideError();
            } catch (err) {
                syncingInputs = false;
            }
        }
    }, 350);
}

// ============ "全部"复选框联动 ============
function setupSchoolTypeCheckboxes() {
    const allCb = document.querySelector('input[name="schoolType"][value=""]');
    const otherCbs = [...$$('input[name="schoolType"]')].filter(el => el.value !== '');

    allCb.addEventListener('change', () => {
        if (allCb.checked) {
            otherCbs.forEach(cb => { cb.checked = false; });
        }
    });

    otherCbs.forEach(cb => {
        cb.addEventListener('change', () => {
            if (cb.checked) {
                allCb.checked = false;
            }
            // 如果都取消了，自动勾回全部
            if (!otherCbs.some(c => c.checked)) {
                allCb.checked = true;
            }
        });
    });
}

// ============ 类型标签 ============
function typeTag(type) {
    if (!type) return '';
    const map = {
        '985': '<span class="tag tag-985">985</span>',
        '211': '<span class="tag tag-211">211</span>',
        '双一流': '<span class="tag tag-syl">双一流</span>',
        '高职专科': '<span class="tag tag-normal">高职专科</span>',
    };
    return map[type] || `<span class="tag tag-normal">${type}</span>`;
}

function trendTag(trend) {
    let cls = 'trend-unknown';
    if (trend && (trend.includes('热门') || trend.includes('升温') || trend.includes('上升'))) {
        cls = 'trend-hot';
    } else if (trend && (trend.includes('冷门') || trend.includes('降温') || trend.includes('下降'))) {
        cls = 'trend-cold';
    } else if (trend && trend.includes('平稳')) {
        cls = 'trend-stable';
    }
    return `<span class="trend-tag ${cls}">${trend || '数据不足'}</span>`;
}

function asPercent(value) {
    const num = Number(value) || 0;
    const pct = num <= 1 ? num * 100 : num;
    return Math.max(0, Math.min(100, Math.round(pct)));
}

// ============ Render: Statistics ============
function renderStatistics(data) {
    const { user_input, statistics } = data;
    DOM.statScore.textContent = user_input.score ?? '--';
    DOM.statRank.textContent = `排名 ${user_input.rank ? user_input.rank.toLocaleString() : '--'}`;
    DOM.statTotal.textContent = statistics.total;
    DOM.statInProv.textContent = statistics.in_province;
    DOM.statOutProv.textContent = statistics.out_province;
    DOM.statReach.textContent = statistics.reach_count;
    DOM.statMatch.textContent = statistics.match_count;
    DOM.statSafety.textContent = statistics.safety_count;

    DOM.tabReachCount.textContent = statistics.reach_count;
    DOM.tabMatchCount.textContent = statistics.match_count;
    DOM.tabSafetyCount.textContent = statistics.safety_count;

    // 更新输入框反向值
    if (user_input.score && !DOM.scoreInput.value) DOM.scoreInput.value = user_input.score;
    if (user_input.rank && !DOM.rankInput.value) DOM.rankInput.value = user_input.rank;
}

// ============ Render: Score Lines in Stats ============
function renderBatchLineStats(slData) {
    if (!slData || !slData.years || slData.years.length === 0) return;
    // 取最新年份
    const latest = slData.years[0];
    if (!latest) return;
    const lines = latest.lines || [];
    const yiDuan = lines.find(l => l.batch === '一段线' || l.batch.includes('一段'));
    const special = lines.find(l => l.batch.includes('特殊'));
    if (yiDuan) {
        DOM.statBatchLine.textContent = yiDuan.score;
        const yearLabel = document.querySelector('.stat-line .stat-label');
        if (yearLabel) yearLabel.textContent = `一段线(${latest.year})`;
    }
    if (special) {
        DOM.statSpecialLine.textContent = `特殊类型线 ${special.score}`;
    }
}

// ============ Render: School Cards ============
function renderSchoolCards(schools, category, container) {
    if (!schools || schools.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>该档位暂无匹配学校</p></div>';
        return;
    }

    const cardClass = {
        reach: 'reach-card',
        match: 'match-card',
        safety: 'safety-card',
    }[category] || '';

    container.innerHTML = schools.map(s => {
        const matchPct = asPercent(s.match_score);
        const probPct = asPercent(s.probability);
        const stabilityPct = asPercent(s.stability);

        const historyRows = (s.history || []).map(h =>
            `<tr><td>${h.year}</td><td>${h.min_score}</td><td>${h.min_rank ? h.min_rank.toLocaleString() : '-'}</td></tr>`
        ).join('');

        return `
        <div class="school-card ${cardClass}" data-school-id="${s.school_id}">
            <div class="card-header">
                <div class="card-top-row">
                    <span class="school-name">${s.school_name}</span>
                    <span class="school-tags">${typeTag(s.type)}</span>
                </div>
                <span class="school-city">📍 ${s.city || s.province || ''}</span>
            </div>
            <div class="card-metrics">
                <div class="metric">
                    <span class="metric-label">匹配度</span>
                    <span class="metric-value">${matchPct}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">录取概率</span>
                    <span class="metric-value">${probPct}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">稳定性</span>
                    <span class="metric-value">${stabilityPct}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">平均位次</span>
                    <span class="metric-value">${s.avg_rank ? s.avg_rank.toLocaleString() : '-'}</span>
                </div>
            </div>
            <div class="match-bar-wrap">
                <div class="match-bar-bg"><div class="match-bar-fill" style="width:${matchPct}%"></div></div>
                <div class="match-bar-text">匹配度 ${matchPct}%</div>
            </div>
            ${historyRows ? `
            <div class="card-history">
                <table class="history-table">
                    <tr><th>年份</th><th>最低分</th><th>最低位次</th></tr>
                    ${historyRows}
                </table>
            </div>` : ''}
            <div class="card-detail"></div>
        </div>`;
    }).join('');

    // 绑定点击展开
    container.querySelectorAll('.school-card').forEach(card => {
        card.addEventListener('click', e => {
            // 避免重复触发
            if (e.target.closest('.card-detail') && card.classList.contains('expanded')) return;
            toggleSchoolDetail(card);
        });
    });
}

// ============ Toggle School Detail (专业展开) ============
async function toggleSchoolDetail(cardEl) {
    const schoolId = cardEl.dataset.schoolId;
    const detailEl = cardEl.querySelector('.card-detail');

    if (cardEl.classList.contains('expanded')) {
        cardEl.classList.remove('expanded');
        return;
    }

    // 关闭同组其他展开卡片
    cardEl.closest('.school-list').querySelectorAll('.school-card.expanded').forEach(c => {
        c.classList.remove('expanded');
    });

    cardEl.classList.add('expanded');

    // 如果已加载过
    if (detailEl.dataset.loaded === 'true') {
        // 更新趋势图
        updateSchoolTrendChart(cardEl);
        return;
    }

    detailEl.innerHTML = '<div class="detail-loading">加载专业数据中...</div>';

    try {
        const data = await fetchSchoolMajors(schoolId);
        renderMajorList(data.majors || [], detailEl);
        detailEl.dataset.loaded = 'true';
        // 更新学校趋势图
        updateSchoolTrendChart(cardEl);
    } catch (err) {
        detailEl.innerHTML = `<div class="detail-loading">加载失败: ${err.message}</div>`;
    }
}

function updateSchoolTrendChart(cardEl) {
    const nameEl = cardEl.querySelector('.school-name');
    const schoolName = nameEl ? nameEl.textContent : '';

    // 从 currentData 找这个学校的 history
    const schoolId = parseInt(cardEl.dataset.schoolId);
    let history = [];
    if (currentData && currentData.recommendations) {
        const allSchools = [
            ...(currentData.recommendations.reach || []),
            ...(currentData.recommendations.match || []),
            ...(currentData.recommendations.safety || []),
        ];
        const found = allSchools.find(s => s.school_id === schoolId);
        if (found) history = found.history || [];
    }

    ChartModule.renderSchoolTrendChart(schoolName, history);
}

// ============ Render: Major List ============
function renderMajorList(majors, container) {
    if (!majors || majors.length === 0) {
        container.innerHTML = '<div class="detail-loading">暂无专业数据</div>';
        return;
    }

    const html = `<div class="major-list">${majors.map(m => {
        const historyHtml = (m.history || []).map(h =>
            `<span><span class="major-hy">${h.year}</span>: ${h.min_score || '-'}分 / ${h.min_rank ? h.min_rank.toLocaleString() : '-'}位</span>`
        ).join('');

        return `
        <div class="major-item">
            <div class="major-top">
                <span class="major-name">${m.major_name}</span>
                <span class="major-category">${m.category || ''}</span>
                ${trendTag(m.hot_trend)}
            </div>
            <div class="major-history">${historyHtml || '<span>暂无历史数据</span>'}</div>
        </div>`;
    }).join('')}</div>`;

    container.innerHTML = html;
}

// ============ Tab Switching ============
function setupTabs() {
    $$('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            // 更新按钮
            $$('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // 更新面板
            $$('.tab-panel').forEach(p => p.classList.remove('active'));
            const panelId = 'panel' + tab.charAt(0).toUpperCase() + tab.slice(1);
            const panel = $(panelId);
            if (panel) panel.classList.add('active');
        });
    });
}

// ============ Main Search ============
async function doSearch() {
    const score = DOM.scoreInput.value.trim();
    const rank = DOM.rankInput.value.trim();

    if (!score && !rank) {
        showError('请输入高考分数或全省排名');
        return;
    }

    hideError();
    showLoading();

    const params = {};
    if (score && rank) {
        if (lastInputSource === 'rank') {
            params.rank = rank;
        } else {
            params.score = score;
        }
    } else if (score) {
        params.score = score;
    } else if (rank) {
        params.rank = rank;
    }

    const schoolType = getSchoolTypeFilter();
    if (schoolType) params.school_type = schoolType;

    const province = getProvinceFilter();
    if (province) params.province = province;

    params.sort_by = DOM.sortBy.value;

    try {
        // 并行请求
        const promises = [fetchRecommendations(params)];

        // 首次加载时获取批次线和热门专业
        if (!scoreLinesData) {
            promises.push(fetchScoreLines());
            promises.push(fetchHotMajors());
        }

        const results = await Promise.all(promises);
        const recData = results[0];

        if (results[1]) {
            scoreLinesData = results[1];
            ChartModule.renderScoreLineChart(scoreLinesData);
            renderBatchLineStats(scoreLinesData);
        }

        if (results[2]) {
            ChartModule.renderHotMajorsChart(results[2].hot_majors, results[2].cold_majors);
        }

        currentData = recData;

        // 切换视图
        DOM.welcomeSection.style.display = 'none';
        DOM.resultSection.style.display = 'block';

        // 渲染
        renderStatistics(recData);
        renderSchoolCards(recData.recommendations.reach, 'reach', DOM.listReach);
        renderSchoolCards(recData.recommendations.match, 'match', DOM.listMatch);
        renderSchoolCards(recData.recommendations.safety, 'safety', DOM.listSafety);

        // 如果有批次线数据但还没渲染图表
        if (scoreLinesData && !results[1]) {
            renderBatchLineStats(scoreLinesData);
        }

    } catch (err) {
        showError(err.message || '查询失败，请稍后重试');
    } finally {
        hideLoading();
    }
}

// ============ Event Bindings ============
function init() {
    setupTabs();
    setupSchoolTypeCheckboxes();

    // 搜索
    DOM.btnSearch.addEventListener('click', doSearch);

    // 回车搜索
    DOM.scoreInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    DOM.rankInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
    DOM.scoreInput.addEventListener('input', () => scheduleInputConversion('score'));
    DOM.rankInput.addEventListener('input', () => scheduleInputConversion('rank'));

    // 关闭错误
    DOM.errorClose.addEventListener('click', hideError);

    // 排序变更自动刷新
    DOM.sortBy.addEventListener('change', () => {
        if (currentData) doSearch();
    });

    // 筛选条件变更自动刷新
    $$('input[name="schoolType"]').forEach(el => {
        el.addEventListener('change', () => { if (currentData) doSearch(); });
    });
    $$('input[name="province"]').forEach(el => {
        el.addEventListener('change', () => { if (currentData) doSearch(); });
    });

    console.log('高考志愿推荐系统已加载');
}

// 启动
document.addEventListener('DOMContentLoaded', init);
