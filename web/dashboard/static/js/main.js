/**
 * AI 개인 맞춤형 포모도로 타이머 - 대시보드 메인 로직
 */

const API_BASE = '/api';
const REFRESH_INTERVAL = 10000; // 10초

// ─── 페이지 상태 ───
let logsPage = 1;
const LOGS_LIMIT = 20;

document.addEventListener('DOMContentLoaded', () => {
    // 날짜 선택기 기본값: 오늘
    const picker = document.getElementById('date-picker');
    if (picker) {
        picker.value = new Date().toISOString().slice(0, 10);
        picker.addEventListener('change', () => {
            logsPage = 1;
            updateLogs();
            updateDailyReport();
            updateCharts();
        });
    }
    initDashboard();
    setInterval(refreshDashboard, REFRESH_INTERVAL);
});

async function initDashboard() {
    await refreshDashboard();
    initCharts();
}

async function refreshDashboard() {
    try {
        await Promise.all([
            updateDailyReport(),
            updateLogs(),
            updateRecovery(),
            updateCharts()
        ]);
    } catch (error) {
        console.error('대시보드 갱신 오류:', error);
    }
}

function getSelectedDate() {
    const picker = document.getElementById('date-picker');
    return picker ? picker.value : new Date().toISOString().slice(0, 10);
}

// ─── 일간 리포트 (카드 업데이트) ───
async function updateDailyReport() {
    try {
        const res = await fetch(`${API_BASE}/daily_report/?date=${getSelectedDate()}`);
        const json = await res.json();

        if (json.success && json.data) {
            const d = json.data;
            document.getElementById('detection-count').textContent =
                d.total_detections ?? '--';

            const alertCount =
                (parseInt(d.alert_count_level1) || 0) +
                (parseInt(d.alert_count_level2) || 0) +
                (parseInt(d.alert_count_level3) || 0);
            document.getElementById('alert-count').textContent = alertCount;
        }
    } catch (e) {
        console.error('일간 리포트 오류:', e);
    }
}

// ─── 안전한 DOM 생성 헬퍼 ───
function createCell(text) {
    const td = document.createElement('td');
    td.textContent = (text === null || text === undefined) ? '--' : String(text);
    return td;
}

function createBadgeCell(level) {
    const td = document.createElement('td');
    const span = document.createElement('span');
    const map = {
        0: { cls: 'badge badge-normal',   label: '정상' },
        1: { cls: 'badge badge-caution',  label: '주의' },
        2: { cls: 'badge badge-warning',  label: '경고' },
        3: { cls: 'badge badge-danger',   label: '위험' }
    };
    const info = map[level] ?? { cls: 'badge', label: String(level) };
    span.className = info.cls;
    span.textContent = info.label;
    td.appendChild(span);
    return td;
}

// ─── 감지 이력 테이블 ───
async function updateLogs() {
    try {
        const date = getSelectedDate();
        const res = await fetch(`${API_BASE}/logs/?page=${logsPage}&limit=${LOGS_LIMIT}&date=${date}`);
        const json = await res.json();
        const tbody = document.getElementById('logs-body');

        if (!json.success || !json.data || json.data.length === 0) {
            tbody.textContent = '';
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 5;
            td.style.cssText = 'text-align:center;padding:2rem;color:#9ca3af';
            td.textContent = '해당 날짜에 감지된 데이터가 없습니다. main.py를 실행하면 수집이 시작됩니다.';
            tr.appendChild(td);
            tbody.appendChild(tr);
            renderPagination(0, 0);
            return;
        }

        tbody.textContent = '';
        for (const row of json.data) {
            const tr = document.createElement('tr');
            tr.appendChild(createCell(formatTime(row.detected_at)));
            tr.appendChild(createCell(parseFloat(row.ear_value).toFixed(3)));
            tr.appendChild(createCell(parseFloat(row.mar_value).toFixed(3)));
            tr.appendChild(createCell(row.drowsiness_score));
            tr.appendChild(createBadgeCell(row.alert_level));
            tbody.appendChild(tr);
        }
        renderPagination(json.page, json.total_pages);
    } catch (e) {
        console.error('감지 이력 오류:', e);
    }
}

function renderPagination(currentPage, totalPages) {
    const container = document.getElementById('logs-pagination');
    if (!container) return;
    container.textContent = '';
    if (totalPages <= 1) return;

    const makeBtn = (label, page, disabled) => {
        const btn = document.createElement('button');
        btn.textContent = label;
        btn.disabled = disabled;
        btn.style.cssText = `padding:4px 10px;border:1px solid #e5e7eb;border-radius:6px;background:${disabled ? '#f3f4f6' : '#fff'};cursor:${disabled ? 'default' : 'pointer'};font-size:0.82rem`;
        if (!disabled) btn.addEventListener('click', () => { logsPage = page; updateLogs(); });
        return btn;
    };

    container.appendChild(makeBtn('‹', currentPage - 1, currentPage <= 1));

    const start = Math.max(1, currentPage - 2);
    const end   = Math.min(totalPages, currentPage + 2);
    for (let p = start; p <= end; p++) {
        const btn = makeBtn(String(p), p, p === currentPage);
        if (p === currentPage) btn.style.background = '#534AB7';
        if (p === currentPage) btn.style.color = '#fff';
        if (p === currentPage) btn.style.borderColor = '#534AB7';
        container.appendChild(btn);
    }

    container.appendChild(makeBtn('›', currentPage + 1, currentPage >= totalPages));
}

// ─── 피로 해소 기록 테이블 ───
async function updateRecovery() {
    try {
        const res = await fetch(`${API_BASE}/recovery/`);
        const json = await res.json();
        const tbody = document.getElementById('recovery-body');

        if (!json.success || !json.data || json.data.length === 0) {
            tbody.textContent = '';
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 6;
            td.style.cssText = 'text-align:center;padding:2rem;color:#9ca3af';
            td.textContent = '기록된 피로 해소 내역이 없습니다. 경고 단계 도달 시 자동으로 기록됩니다.';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        tbody.textContent = '';
        for (const row of json.data) {
            const tr = document.createElement('tr');
            tr.appendChild(createCell(formatTime(row.action_at)));
            tr.appendChild(createCell(getGuideTypeLabel(row.guide_type)));
            tr.appendChild(createCell(row.fatigue_before));
            tr.appendChild(createCell(row.fatigue_after));
            tr.appendChild(createCell(`${row.duration_sec}초`));

            const effectiveTd = document.createElement('td');
            effectiveTd.className = row.effective ? 'effective-yes' : 'effective-no';
            effectiveTd.textContent = row.effective ? '효과 있음' : '효과 없음';
            tr.appendChild(effectiveTd);

            tbody.appendChild(tr);
        }
    } catch (e) {
        console.error('해소 기록 오류:', e);
    }
}

// ─── 차트 업데이트 ───
async function updateCharts() {
    try {
        const fatRes = await fetch(`${API_BASE}/fatigue/?date=${getSelectedDate()}`);
        const fatJson = await fatRes.json();

        if (fatJson.success && fatJson.data && fatJson.data.length > 0) {
            const latest = fatJson.data[0];
            document.getElementById('fatigue-score').textContent =
                latest.fatigue_score ?? '--';
            document.getElementById('fatigue-level').textContent =
                getFatigueLevelLabel(latest.fatigue_level);

            if (window.fatigueChart) {
                const sorted = [...fatJson.data].reverse();
                window.fatigueChart.data.labels = sorted.map(d => formatTime(d.logged_at));
                window.fatigueChart.data.datasets[0].data = sorted.map(d => d.fatigue_score);
                window.fatigueChart.update();
            }
        }

        const logRes = await fetch(`${API_BASE}/logs/?page=1&limit=100&date=${getSelectedDate()}`);
        const logJson = await logRes.json();

        if (logJson.success && logJson.data && window.drowsinessChart) {
            const reversed = [...logJson.data].reverse();
            window.drowsinessChart.data.labels = reversed.map(d => formatTime(d.detected_at));
            window.drowsinessChart.data.datasets[0].data = reversed.map(d => d.drowsiness_score);
            window.drowsinessChart.update();
        }
    } catch (e) {
        console.error('차트 업데이트 오류:', e);
    }
}

// ─── 유틸리티 함수 ───
function formatTime(dateStr) {
    if (!dateStr) return '--';
    const d = new Date(dateStr);
    return d.toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function getFatigueLevelLabel(level) {
    const map = {
        'good':    '양호',
        'caution': '주의',
        'warning': '경고',
        'danger':  '위험'
    };
    return map[level] ?? level ?? '대기중';
}

function getGuideTypeLabel(type) {
    if (!type) return '--';
    // 쉼표 구분 복수 가이드 처리
    return type.split(',').map(t => {
        const map = {
            'eye_rest':   '눈 피로 해소',
            'stretching': '스트레칭',
            'breathing':  '호흡법',
            'rest_break': '휴식',
            'walk':       '산책',
            'hydration':  '수분 보충',
            'face_wash':  '냉수 세안',
            'caffeine':   '카페인',
            'posture':    '자세 교정',
        };
        return map[t.trim()] ?? t.trim();
    }).join(', ');
}
