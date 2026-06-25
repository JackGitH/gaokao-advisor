/**
 * 高考志愿推荐系统 - 图表可视化模块
 * 依赖 Chart.js 4.x（通过 CDN 在 HTML 中引入）
 */

const ChartModule = (() => {
    // 存储 chart 实例，更新前先销毁
    let scoreLineChart = null;
    let schoolTrendChart = null;
    let hotMajorsChart = null;

    const COLORS = {
        reach: '#e53e3e',
        match: '#38a169',
        safety: '#3182ce',
        accent: '#ed8936',
        primary: '#1a365d',
        purple: '#805ad5',
        gray: '#a0aec0',
    };

    // 公共默认配置
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { font: { size: 12 }, padding: 12 },
            },
        },
    };

    /**
     * 1. 近3年批次线对比 - 柱状图
     * @param {Object} data - /api/score-lines 返回的 data.years
     */
    function renderScoreLineChart(data) {
        const canvas = document.getElementById('chartScoreLine');
        if (!canvas || !data || !data.years || data.years.length === 0) return;

        if (scoreLineChart) { scoreLineChart.destroy(); scoreLineChart = null; }

        // 整理数据：按年份分组，每个batch是一个dataset
        const years = data.years.map(y => y.year).sort();
        const batchMap = {}; // batch名 → { year: score }

        data.years.forEach(item => {
            (item.lines || []).forEach(line => {
                const batchName = line.batch;
                if (!batchMap[batchName]) batchMap[batchName] = {};
                batchMap[batchName][item.year] = line.score;
            });
        });

        const batchColors = {
            '一段线': COLORS.primary,
            '二段线': COLORS.match,
            '特殊类型招生控制线': COLORS.purple,
            '特殊类型线': COLORS.purple,
        };
        let colorIdx = 0;
        const fallbackColors = [COLORS.accent, COLORS.reach, COLORS.safety, COLORS.gray];

        const datasets = Object.keys(batchMap).map(batch => {
            const color = batchColors[batch] || fallbackColors[colorIdx++ % fallbackColors.length];
            return {
                label: batch,
                data: years.map(y => batchMap[batch][y] || null),
                backgroundColor: color + 'cc',
                borderColor: color,
                borderWidth: 1,
                borderRadius: 4,
            };
        });

        scoreLineChart = new Chart(canvas, {
            type: 'bar',
            data: { labels: years.map(String), datasets },
            options: {
                ...defaultOptions,
                scales: {
                    y: {
                        beginAtZero: false,
                        title: { display: true, text: '分数', font: { size: 11 } },
                        ticks: { font: { size: 11 } },
                    },
                    x: {
                        title: { display: true, text: '年份', font: { size: 11 } },
                        ticks: { font: { size: 11 } },
                    },
                },
                plugins: {
                    ...defaultOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}分`,
                        },
                    },
                },
            },
        });
    }

    /**
     * 2. 学校分数线趋势 - 折线图（双Y轴：分数+位次）
     * @param {string} schoolName
     * @param {Array} history - [{year, min_score, min_rank}]
     */
    function renderSchoolTrendChart(schoolName, history) {
        const canvas = document.getElementById('chartSchoolTrend');
        const hint = document.querySelector('.chart-hint');
        if (!canvas) return;

        if (hint) hint.style.display = 'none';
        canvas.style.display = 'block';

        if (schoolTrendChart) { schoolTrendChart.destroy(); schoolTrendChart = null; }

        if (!history || history.length === 0) {
            canvas.style.display = 'none';
            if (hint) { hint.textContent = '暂无该校历史数据'; hint.style.display = 'block'; }
            return;
        }

        const sorted = [...history].sort((a, b) => a.year - b.year);
        const labels = sorted.map(h => String(h.year));
        const scores = sorted.map(h => h.min_score);
        const ranks = sorted.map(h => h.min_rank);

        schoolTrendChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: '最低分',
                        data: scores,
                        borderColor: COLORS.accent,
                        backgroundColor: COLORS.accent + '33',
                        tension: 0.3,
                        fill: true,
                        yAxisID: 'yScore',
                        pointRadius: 5,
                        pointHoverRadius: 7,
                    },
                    {
                        label: '最低位次',
                        data: ranks,
                        borderColor: COLORS.safety,
                        backgroundColor: COLORS.safety + '33',
                        tension: 0.3,
                        fill: false,
                        yAxisID: 'yRank',
                        pointRadius: 5,
                        pointHoverRadius: 7,
                        borderDash: [5, 3],
                    },
                ],
            },
            options: {
                ...defaultOptions,
                scales: {
                    yScore: {
                        type: 'linear',
                        position: 'left',
                        beginAtZero: false,
                        title: { display: true, text: '分数', font: { size: 11 } },
                        ticks: { font: { size: 11 } },
                    },
                    yRank: {
                        type: 'linear',
                        position: 'right',
                        reverse: true,
                        beginAtZero: false,
                        title: { display: true, text: '位次（低=更好）', font: { size: 11 } },
                        ticks: { font: { size: 11 } },
                        grid: { drawOnChartArea: false },
                    },
                    x: {
                        ticks: { font: { size: 11 } },
                    },
                },
                plugins: {
                    ...defaultOptions.plugins,
                    title: {
                        display: true,
                        text: `${schoolName} 录取趋势`,
                        font: { size: 13 },
                    },
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                if (ctx.dataset.yAxisID === 'yRank') {
                                    return `位次: ${ctx.parsed.y.toLocaleString()}`;
                                }
                                return `分数: ${ctx.parsed.y}`;
                            },
                        },
                    },
                },
            },
        });
    }

    /**
     * 3. 热门专业排行 - 横向条形图
     * @param {Array} hotMajors - [{major_name, heat_score, rank_change_rate}]
     * @param {Array} coldMajors - [{major_name, cold_score, rank_change_rate}]
     */
    function renderHotMajorsChart(hotMajors, coldMajors) {
        const canvas = document.getElementById('chartHotMajors');
        if (!canvas) return;

        if (hotMajorsChart) { hotMajorsChart.destroy(); hotMajorsChart = null; }

        // 取 top10 热门
        const items = (hotMajors || []).slice(0, 10).reverse();

        if (items.length === 0) return;

        const labels = items.map(m => {
            const name = m.major_name || m.name || '';
            return name.length > 10 ? name.slice(0, 10) + '…' : name;
        });

        const changes = items.map(m => m.heat_score ?? Math.abs((m.rank_change_rate || 0) * 100));
        const colors = items.map(() => COLORS.reach);

        hotMajorsChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: '热度变化',
                    data: changes,
                    backgroundColor: colors.map(c => c + 'cc'),
                    borderColor: colors,
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                ...defaultOptions,
                indexAxis: 'y',
                scales: {
                    x: {
                        title: { display: true, text: '位次提升幅度(%)', font: { size: 11 } },
                        ticks: { font: { size: 11 } },
                    },
                    y: {
                        ticks: { font: { size: 11 } },
                    },
                },
                plugins: {
                    ...defaultOptions.plugins,
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => `热度 ${ctx.parsed.x}%`,
                        },
                    },
                },
            },
        });
    }

    // 公开 API
    return {
        renderScoreLineChart,
        renderSchoolTrendChart,
        renderHotMajorsChart,
    };
})();
