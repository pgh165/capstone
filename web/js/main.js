/**
 * AIoT 졸음 방지 시스템 - 대시보드 메인 로직
 */

const API_BASE = 'api';
const REFRESH_INTERVAL = 10000; // 10초

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
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

// ─── 일간 리포트 (카드 업데이트) ───
async function updateDailyReport() {
    try {
        const res = await fetch(`${API_BASE}/daily_report.php`);
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
function escapeHtml(str) {
    if (str === null || str === undefined) return '--';
    const text = String(str);
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function createCell(text) {
    const td = document.createElement('td');
    td.textContent = (text === null || text === undefined) ? '--' : String(text);
    return td;
}

function createBadgeCell(level) {
    const td = document.createElement('td');
    const span = document.createElement('span');
    const map = {
        0: { cls: 'badge badge-normal', label: '정상' },
        1: { cls: 'badge badge-caution', label: '주의' },
        2: { cls: 'badge badge-warning', label: '경고' },
        3: { cls: 'badge badge-danger', label: '위험' }
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
        const res = await fetch(`${API_BASE}/logs.php?page=1&limit=20`);
        const json = await res.json();
        const tbody = document.getElementById('logs-body');

        if (!json.success || !json.data || json.data.length === 0) {
            tbody.textContent = '';
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 9;
            td.textContent = '데이터가 없습니다.';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        // 최신 환경/피로 데이터 업데이트 (첫 번째 항목에서)
        const latest = json.data[0];
        document.getElementById('env-co2').textContent =
            `${latest.co2_ppm ?? '--'} ppm`;
        document.getElementById('env-temp-humid').textContent =
            `${latest.temperature ?? '--'}°C / ${latest.humidity ?? '--'}%`;

        tbody.textContent = '';
        for (const row of json.data) {
            const tr = document.createElement('tr');
            tr.appendChild(createCell(formatTime(row.detected_at)));
            tr.appendChild(createCell(parseFloat(row.ear_value).toFixed(3)));
            tr.appendChild(createCell(parseFloat(row.mar_value).toFixed(3)));
            tr.appendChild(createCell(row.drowsiness_score));
            tr.appendChild(createBadgeCell(row.alert_level));
            tr.appendChild(createCell(`${row.co2_ppm} ppm`));
            tr.appendChild(createCell(`${row.temperature}°C`));
            tr.appendChild(createCell(`${row.humidity}%`));
            tr.appendChild(createCell(row.env_score));
            tbody.appendChild(tr);
        }
    } catch (e) {
        console.error('감지 이력 오류:', e);
    }
}

// ─── 피로 해소 기록 테이블 ───
async function updateRecovery() {
    try {
        const res = await fetch(`${API_BASE}/recovery.php`);
        const json = await res.json();
        const tbody = document.getElementById('recovery-body');

        if (!json.success || !json.data || json.data.length === 0) {
            tbody.textContent = '';
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 6;
            td.textContent = '데이터가 없습니다.';
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
        // 피로도 데이터
        const fatRes = await fetch(`${API_BASE}/fatigue.php?period=today`);
        const fatJson = await fatRes.json();

        if (fatJson.success && fatJson.data && fatJson.data.length > 0) {
            const latest = fatJson.data[0];
            document.getElementById('fatigue-score').textContent =
                latest.fatigue_score ?? '--';
            document.getElementById('fatigue-level').textContent =
                getFatigueLevelLabel(latest.fatigue_level);

            if (window.fatigueChart) {
                const labels = fatJson.data.reverse().map(d => formatTime(d.logged_at));
                const scores = fatJson.data.map(d => d.fatigue_score);
                window.fatigueChart.data.labels = labels;
                window.fatigueChart.data.datasets[0].data = scores;
                window.fatigueChart.update();
            }
        }

        // 환경 데이터
        const envRes = await fetch(`${API_BASE}/environment.php?hours=24`);
        const envJson = await envRes.json();

        if (envJson.success && envJson.data && window.environmentChart) {
            const labels = envJson.data.map(d => formatTime(d.detected_at));
            const co2 = envJson.data.map(d => d.co2_ppm);
            const temp = envJson.data.map(d => d.temperature);
            const humid = envJson.data.map(d => d.humidity);

            window.environmentChart.data.labels = labels;
            window.environmentChart.data.datasets[0].data = co2;
            window.environmentChart.data.datasets[1].data = temp;
            window.environmentChart.data.datasets[2].data = humid;
            window.environmentChart.update();
        }

        // 졸음 점수 데이터
        const logRes = await fetch(`${API_BASE}/logs.php?page=1&limit=100`);
        const logJson = await logRes.json();

        if (logJson.success && logJson.data && window.drowsinessChart) {
            const reversed = logJson.data.reverse();
            const labels = reversed.map(d => formatTime(d.detected_at));
            const scores = reversed.map(d => d.drowsiness_score);

            window.drowsinessChart.data.labels = labels;
            window.drowsinessChart.data.datasets[0].data = scores;
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
        'good': '양호',
        'caution': '주의',
        'warning': '경고',
        'danger': '위험'
    };
    return map[level] ?? level ?? '대기중';
}

function getGuideTypeLabel(type) {
    const map = {
        'eye_rest': '눈 피로 해소',
        'stretching': '스트레칭',
        'breathing': '호흡법',
        'ventilation': '환기 권고',
        'rest_break': '휴식 권고'
    };
    return map[type] ?? type;
}
