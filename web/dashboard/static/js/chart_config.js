/**
 * AIoT 졸음 방지 시스템 - Chart.js 설정
 */

const CHART_COLORS = {
    primary: 'rgba(83, 74, 183, 1)',
    primaryFill: 'rgba(83, 74, 183, 0.15)',
    danger: 'rgba(163, 45, 45, 1)',
    dangerFill: 'rgba(163, 45, 45, 0.15)',
    success: 'rgba(15, 110, 86, 1)',
    successFill: 'rgba(15, 110, 86, 0.15)',
    warning: 'rgba(133, 79, 11, 1)',
    warningFill: 'rgba(133, 79, 11, 0.15)',
    info: 'rgba(24, 95, 165, 1)',
    infoFill: 'rgba(24, 95, 165, 0.15)',
};

// 공통 차트 옵션
const commonOptions = {
    responsive: true,
    maintainAspectRatio: true,
    interaction: {
        intersect: false,
        mode: 'index'
    },
    plugins: {
        legend: {
            labels: {
                font: { family: "'Noto Sans KR', sans-serif", size: 12 },
                usePointStyle: true
            }
        }
    },
    scales: {
        x: {
            ticks: {
                font: { size: 10 },
                maxTicksLimit: 12,
                maxRotation: 0
            },
            grid: { display: false }
        },
        y: {
            beginAtZero: true,
            ticks: { font: { size: 11 } },
            grid: { color: 'rgba(0,0,0,0.05)' }
        }
    }
};

// 졸음 점수 차트
function createDrowsinessChart(canvasId) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '졸음 점수',
                data: [],
                borderColor: CHART_COLORS.danger,
                backgroundColor: CHART_COLORS.dangerFill,
                fill: true,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5,
                borderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    max: 100,
                    title: { display: true, text: '점수' }
                }
            },
            plugins: {
                ...commonOptions.plugins,
                annotation: {
                    annotations: {
                        cautionLine: {
                            type: 'line',
                            yMin: 30,
                            yMax: 30,
                            borderColor: 'rgba(133,79,11,0.5)',
                            borderDash: [5, 5],
                            borderWidth: 1
                        },
                        warningLine: {
                            type: 'line',
                            yMin: 60,
                            yMax: 60,
                            borderColor: 'rgba(153,60,29,0.5)',
                            borderDash: [5, 5],
                            borderWidth: 1
                        },
                        dangerLine: {
                            type: 'line',
                            yMin: 85,
                            yMax: 85,
                            borderColor: 'rgba(163,45,45,0.5)',
                            borderDash: [5, 5],
                            borderWidth: 1
                        }
                    }
                }
            }
        }
    });
}

// 피로도 차트
function createFatigueChart(canvasId) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '피로도 점수',
                data: [],
                borderColor: CHART_COLORS.primary,
                backgroundColor: CHART_COLORS.primaryFill,
                fill: true,
                tension: 0.3,
                pointRadius: 2,
                pointHoverRadius: 5,
                borderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    max: 100,
                    title: { display: true, text: '피로도' }
                }
            }
        }
    });
}

// 환경 센서 차트 (다축)
function createEnvironmentChart(canvasId) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'CO₂ (ppm)',
                    data: [],
                    borderColor: CHART_COLORS.warning,
                    backgroundColor: 'transparent',
                    yAxisID: 'y-co2',
                    tension: 0.3,
                    pointRadius: 1,
                    borderWidth: 2
                },
                {
                    label: '온도 (°C)',
                    data: [],
                    borderColor: CHART_COLORS.danger,
                    backgroundColor: 'transparent',
                    yAxisID: 'y-temp',
                    tension: 0.3,
                    pointRadius: 1,
                    borderWidth: 2
                },
                {
                    label: '습도 (%)',
                    data: [],
                    borderColor: CHART_COLORS.info,
                    backgroundColor: 'transparent',
                    yAxisID: 'y-temp',
                    tension: 0.3,
                    pointRadius: 1,
                    borderWidth: 2
                }
            ]
        },
        options: {
            ...commonOptions,
            scales: {
                x: commonOptions.scales.x,
                'y-co2': {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: false,
                    title: { display: true, text: 'CO₂ (ppm)' },
                    ticks: { font: { size: 11 } },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                },
                'y-temp': {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: false,
                    title: { display: true, text: '온도(°C) / 습도(%)' },
                    ticks: { font: { size: 11 } },
                    grid: { display: false }
                }
            }
        }
    });
}

// 차트 초기화
function initCharts() {
    window.drowsinessChart = createDrowsinessChart('drowsinessChart');
    window.fatigueChart = createFatigueChart('fatigueChart');
    window.environmentChart = createEnvironmentChart('environmentChart');
}
