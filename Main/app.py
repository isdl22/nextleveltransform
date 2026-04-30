from flask import Flask, jsonify, request, render_template_string
import pymysql
from datetime import datetime

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

DB_CONFIG = {
    'host': 'bubble-db.c3qewqwk0mog.ap-northeast-2.rds.amazonaws.com',
    'user': 'admin',
    'password': 'theway4123',
    'database': 'bubble_db',
    'port': 3306,
    'connect_timeout': 10,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_conn():
    return pymysql.connect(**DB_CONFIG)

HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bubble DB 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; background: #f0f2f5; color: #1a1a2e; }

  header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: white; padding: 20px 32px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
  }
  header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
  header .subtitle { font-size: 12px; color: #a0aec0; margin-top: 2px; }
  .live-badge { background: #48bb78; color: white; font-size: 11px; padding: 3px 10px; border-radius: 20px; }

  .container { max-width: 1400px; margin: 0 auto; padding: 24px 20px; }

  /* 카드 그리드 */
  .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .card {
    background: white; border-radius: 12px; padding: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }
  .card .label { font-size: 12px; color: #718096; font-weight: 500; margin-bottom: 8px; }
  .card .value { font-size: 32px; font-weight: 700; color: #1a1a2e; }
  .card .sub { font-size: 12px; color: #a0aec0; margin-top: 4px; }
  .card.blue .value { color: #3182ce; }
  .card.green .value { color: #38a169; }
  .card.purple .value { color: #805ad5; }
  .card.orange .value { color: #dd6b20; }

  /* 섹션 공통 */
  .section { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 24px; }
  .section h2 { font-size: 16px; font-weight: 700; margin-bottom: 20px; color: #2d3748; border-left: 4px solid #3182ce; padding-left: 12px; }

  /* 2열 그리드 */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }

  /* 차트 */
  .chart-wrap { position: relative; height: 280px; }

  /* 분포 바 */
  .dist-item { display: flex; align-items: center; margin-bottom: 12px; }
  .dist-label { width: 130px; font-size: 13px; color: #4a5568; flex-shrink: 0; }
  .dist-bar-wrap { flex: 1; background: #edf2f7; border-radius: 4px; height: 22px; overflow: hidden; }
  .dist-bar { height: 100%; background: linear-gradient(90deg, #3182ce, #63b3ed); border-radius: 4px; transition: width 0.6s ease; display: flex; align-items: center; padding-left: 8px; }
  .dist-bar span { font-size: 11px; color: white; font-weight: 600; white-space: nowrap; }
  .dist-count { width: 50px; text-align: right; font-size: 13px; color: #718096; margin-left: 10px; }

  /* 검색 섹션 */
  .search-box { display: flex; gap: 10px; margin-bottom: 20px; }
  .search-box input {
    flex: 1; padding: 11px 16px; border: 1.5px solid #e2e8f0;
    border-radius: 8px; font-size: 14px; outline: none;
    transition: border 0.2s;
  }
  .search-box input:focus { border-color: #3182ce; }
  .search-box button {
    padding: 11px 24px; background: #3182ce; color: white;
    border: none; border-radius: 8px; font-size: 14px; cursor: pointer;
    font-weight: 600; transition: background 0.2s;
  }
  .search-box button:hover { background: #2c5282; }

  /* 검색 결과 */
  .result-card {
    border: 1.5px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 12px;
    background: #f7fafc; transition: box-shadow 0.2s;
  }
  .result-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
  .result-name { font-size: 18px; font-weight: 700; color: #2d3748; }
  .result-email { font-size: 13px; color: #718096; margin: 2px 0 12px; }
  .result-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  .tag {
    padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600;
  }
  .tag.blue { background: #ebf8ff; color: #2c5282; }
  .tag.green { background: #f0fff4; color: #276749; }
  .tag.purple { background: #faf5ff; color: #553c9a; }
  .tag.orange { background: #fffaf0; color: #c05621; }
  .tag.gray { background: #f7fafc; color: #4a5568; border: 1px solid #e2e8f0; }

  .score-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 10px; }
  .score-block { background: white; border-radius: 8px; padding: 10px 12px; border: 1px solid #e2e8f0; }
  .score-block .slabel { font-size: 11px; color: #a0aec0; margin-bottom: 6px; }
  .score-dots { display: flex; gap: 4px; flex-wrap: wrap; }
  .dot {
    width: 22px; height: 22px; border-radius: 50%; font-size: 10px;
    display: flex; align-items: center; justify-content: center; font-weight: 700; color: white;
  }
  .dot.filled { background: #3182ce; }
  .dot.empty { background: #e2e8f0; color: #a0aec0; }

  .no-result { text-align: center; color: #a0aec0; padding: 40px; font-size: 14px; }
  .loading { text-align: center; color: #718096; padding: 20px; }

  /* 탭 */
  .tabs { display: flex; gap: 4px; margin-bottom: 24px; border-bottom: 2px solid #e2e8f0; }
  .tab-btn {
    padding: 10px 20px; font-size: 14px; font-weight: 600; cursor: pointer;
    border: none; background: none; color: #718096; border-bottom: 3px solid transparent;
    margin-bottom: -2px; transition: all 0.2s;
  }
  .tab-btn.active { color: #3182ce; border-bottom-color: #3182ce; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* 테이블 */
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #f7fafc; color: #4a5568; padding: 10px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e2e8f0; }
  td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; color: #2d3748; }
  tr:hover td { background: #f7fafc; }

  /* 등급 뱃지 */
  .badge { display:inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; }
  .badge-run { background: #fff5f5; color: #c53030; border: 1px solid #feb2b2; }
  .badge-emergency { background: #fffaf0; color: #c05621; border: 1px solid #fbd38d; }
  .badge-warning { background: #fefcbf; color: #744210; border: 1px solid #f6e05e; }
  .badge-stay { background: #f0fff4; color: #276749; border: 1px solid #9ae6b4; }

  /* 채점 요약 카드 */
  .score-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
  .ss-card { border-radius: 10px; padding: 16px; text-align: center; }
  .ss-card .ss-label { font-size: 12px; font-weight: 600; margin-bottom: 6px; }
  .ss-card .ss-val { font-size: 28px; font-weight: 700; }

  @media (max-width: 900px) {
    .cards { grid-template-columns: repeat(2, 1fr); }
    .grid-2 { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<header>
  <div>
    <h1>Bubble DB 대시보드</h1>
    <div class="subtitle">bubble_db · import_raw_data 기반</div>
  </div>
  <span class="live-badge">● LIVE</span>
</header>

<div class="container">

  <!-- 탭 네비게이션 -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('overview')">개요</button>
    <button class="tab-btn" onclick="switchTab('scoring')">채점 결과</button>
    <button class="tab-btn" onclick="switchTab('search')">고객 검색</button>
  </div>

  <!-- 탭: 개요 -->
  <div class="tab-content active" id="tab-overview">

  <!-- 요약 카드 -->
  <div class="cards">
    <div class="card blue">
      <div class="label">총 응답 수</div>
      <div class="value" id="total">-</div>
      <div class="sub">import_raw_data</div>
    </div>
    <div class="card green">
      <div class="label">고유 인원 수</div>
      <div class="value" id="unique">-</div>
      <div class="sub">중복 제외</div>
    </div>
    <div class="card purple">
      <div class="label">오늘 신규 유입</div>
      <div class="value" id="today">-</div>
      <div class="sub" id="today-date">-</div>
    </div>
    <div class="card orange">
      <div class="label">최근 7일 평균</div>
      <div class="value" id="weekly">-</div>
      <div class="sub">일평균 유입</div>
    </div>
  </div>

  <!-- 추이 차트 -->
  <div class="section">
    <h2>일자별 유입 추이</h2>
    <div style="display:flex;gap:8px;margin-bottom:16px;">
      <button onclick="loadTrend(30)" id="btn30" class="trend-btn active-btn">30일</button>
      <button onclick="loadTrend(60)" id="btn60" class="trend-btn">60일</button>
      <button onclick="loadTrend(90)" id="btn90" class="trend-btn">90일</button>
    </div>
    <div class="chart-wrap"><canvas id="trendChart"></canvas></div>
  </div>

  <!-- 분포 차트 -->
  <div class="grid-2">
    <div class="section">
      <h2>재직직무 분포</h2>
      <div id="job-dist"></div>
    </div>
    <div class="section">
      <h2>재직산업 분포</h2>
      <div id="industry-dist"></div>
    </div>
  </div>
  <div class="grid-2">
    <div class="section">
      <h2>회사규모 분포</h2>
      <div class="chart-wrap"><canvas id="sizeChart"></canvas></div>
    </div>
    <div class="section">
      <h2>직책 분포</h2>
      <div class="chart-wrap"><canvas id="posChart"></canvas></div>
    </div>
  </div>

  <!-- 연차 분포 -->
  <div class="section">
    <h2>연차 분포</h2>
    <div class="chart-wrap"><canvas id="yearChart"></canvas></div>
  </div>

  </div><!-- /tab-overview -->

  <!-- 탭: 채점 결과 -->
  <div class="tab-content" id="tab-scoring">
    <div class="section">
      <h2>채점 결과 — 이직 활성도 / 퇴사 진단</h2>
      <div id="scoring-summary-wrap">
        <div style="color:#718096;font-size:13px;padding:12px 0;">채점 계산 중... (최초 1회 약 10초 소요)</div>
      </div>

      <div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
        <input type="text" id="scoreSearchInput" placeholder="이름 또는 이메일 검색..." style="flex:1;min-width:200px;padding:9px 14px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;">
        <select id="scoreStageFilter" style="padding:9px 14px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:13px;background:white;">
          <option value="">전체 단계</option>
          <option value="Run">💀 Run</option>
          <option value="Emergency">⚠️ Emergency</option>
          <option value="Warning">△ Warning</option>
          <option value="Stay">◎ Stay</option>
        </select>
        <select id="scoreDaeFilter" style="padding:9px 14px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:13px;background:white;">
          <option value="">전체 대분류</option>
          <option value="이직 활성도">이직 활성도</option>
          <option value="퇴사 진단">퇴사 진단</option>
        </select>
        <button onclick="loadScoring(1)" style="padding:9px 20px;background:#3182ce;color:white;border:none;border-radius:8px;font-size:13px;cursor:pointer;font-weight:600;">검색</button>
      </div>

      <div id="scoring-table-wrap"><div class="loading">로딩 중...</div></div>
      <div id="scoring-pagination" style="margin-top:16px;display:flex;gap:8px;justify-content:center;"></div>
    </div>
  </div><!-- /tab-scoring -->

  <!-- 탭: 고객 검색 -->
  <div class="tab-content" id="tab-search">
    <div class="section">
      <h2>고객 검색</h2>
      <div class="search-box">
        <input type="text" id="searchInput" placeholder="이름 또는 이메일로 검색..." onkeydown="if(event.key==='Enter')search()">
        <button onclick="search()">검색</button>
      </div>
      <div id="searchResult"></div>
    </div>
  </div><!-- /tab-search -->

</div>

<style>
.trend-btn {
  padding: 6px 14px; border: 1.5px solid #e2e8f0; background: white;
  border-radius: 6px; font-size: 13px; cursor: pointer; color: #4a5568;
}
.active-btn { background: #3182ce; color: white; border-color: #3182ce; }
</style>

<script>
let trendChart, sizeChart, posChart, yearChart;

async function fetchJSON(url) {
  const r = await fetch(url);
  return r.json();
}

// 요약 카드
async function loadSummary() {
  const d = await fetchJSON('/api/summary');
  document.getElementById('total').textContent = d.total.toLocaleString();
  document.getElementById('unique').textContent = d.unique.toLocaleString();
  document.getElementById('today').textContent = d.today.toLocaleString();
  document.getElementById('today-date').textContent = d.today_date;
  document.getElementById('weekly').textContent = d.weekly_avg.toFixed(1) + '명';
}

// 추이 차트
async function loadTrend(days=30) {
  document.querySelectorAll('.trend-btn').forEach(b => b.classList.remove('active-btn'));
  document.getElementById('btn'+days).classList.add('active-btn');

  const d = await fetchJSON('/api/trend?days='+days);
  const ctx = document.getElementById('trendChart').getContext('2d');
  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: d.map(r => r.date),
      datasets: [{
        label: '일별 유입',
        data: d.map(r => r.count),
        backgroundColor: 'rgba(49,130,206,0.7)',
        borderColor: '#3182ce',
        borderWidth: 1,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 11 }, maxRotation: 45 } },
        y: { beginAtZero: true, grid: { color: '#f0f0f0' }, ticks: { stepSize: 1 } }
      }
    }
  });
}

// 분포 바
function renderDist(containerId, items, total, color) {
  const el = document.getElementById(containerId);
  el.innerHTML = items.map(item => {
    const pct = Math.round(item.count / total * 100);
    return `
      <div class="dist-item">
        <div class="dist-label">${item.label || '미입력'}</div>
        <div class="dist-bar-wrap">
          <div class="dist-bar" style="width:${pct}%;background:linear-gradient(90deg,${color},${color}aa)">
            <span>${pct}%</span>
          </div>
        </div>
        <div class="dist-count">${item.count.toLocaleString()}</div>
      </div>`;
  }).join('');
}

// 분포 차트들
async function loadDists() {
  const d = await fetchJSON('/api/distributions');

  renderDist('job-dist', d.job.slice(0,10), d.total, '#3182ce');
  renderDist('industry-dist', d.industry.slice(0,10), d.total, '#38a169');

  // 회사규모 도넛
  const ctx2 = document.getElementById('sizeChart').getContext('2d');
  if (sizeChart) sizeChart.destroy();
  sizeChart = new Chart(ctx2, {
    type: 'doughnut',
    data: {
      labels: d.size.map(x => x.label || '미입력'),
      datasets: [{ data: d.size.map(x => x.count),
        backgroundColor: ['#3182ce','#48bb78','#ed8936','#9f7aea','#fc8181','#4fd1c5'] }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { font: { size: 12 } } } } }
  });

  // 직책 도넛
  const ctx3 = document.getElementById('posChart').getContext('2d');
  if (posChart) posChart.destroy();
  posChart = new Chart(ctx3, {
    type: 'doughnut',
    data: {
      labels: d.position.map(x => x.label || '미입력'),
      datasets: [{ data: d.position.map(x => x.count),
        backgroundColor: ['#3182ce','#48bb78','#ed8936','#9f7aea','#fc8181','#4fd1c5','#f6e05e'] }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { font: { size: 12 } } } } }
  });

  // 연차 바차트
  const ctx4 = document.getElementById('yearChart').getContext('2d');
  if (yearChart) yearChart.destroy();
  yearChart = new Chart(ctx4, {
    type: 'bar',
    data: {
      labels: d.year.map(x => x.label + '년차'),
      datasets: [{
        label: '인원',
        data: d.year.map(x => x.count),
        backgroundColor: '#9f7aea',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: '#f0f0f0' } }
      }
    }
  });
}

// 점수 시각화
function renderDots(scores, max) {
  return scores.map((s, i) => {
    const filled = Math.round(s);
    return `<div style="margin-bottom:4px;font-size:11px;color:#718096;">Q${i+1}: ${
      Array.from({length: max}, (_, j) =>
        `<span style="display:inline-block;width:16px;height:16px;border-radius:50%;background:${j < filled ? '#3182ce' : '#e2e8f0'};margin:1px;vertical-align:middle;"></span>`
      ).join('')
    } <b style="color:#2d3748">${s}</b></div>`;
  }).join('');
}

// 검색
async function search() {
  const q = document.getElementById('searchInput').value.trim();
  if (!q) return;
  const el = document.getElementById('searchResult');
  el.innerHTML = '<div class="loading">검색 중...</div>';
  const d = await fetchJSON('/api/search?q=' + encodeURIComponent(q));

  if (!d.length) {
    el.innerHTML = '<div class="no-result">검색 결과가 없습니다.</div>';
    return;
  }

  el.innerHTML = `<div style="font-size:13px;color:#718096;margin-bottom:12px;">${d.length}명 검색됨</div>` +
    d.map(p => {
      const q1scores = [p.Q1_1, p.Q1_2, p.Q1_3, p.Q1_4, p.Q1_5].filter(x => x != null);
      const q2scores = [p.Q2_1, p.Q2_2, p.Q2_3, p.Q2_4, p.Q2_5, p.Q2_6, p.Q2_7, p.Q2_8, p.Q2_9, p.Q2_10, p.Q2_11].filter(x => x != null);

      return `
      <div class="result-card">
        <div class="result-name">${p.이름 || '-'}</div>
        <div class="result-email">✉ ${p.이메일 || '-'} &nbsp;|&nbsp; 📞 ${p.연락처 || '-'}</div>
        <div class="result-tags">
          <span class="tag blue">🏢 ${p.회사명 || '미입력'}</span>
          <span class="tag green">💼 ${p.재직직무 || '미입력'}</span>
          <span class="tag purple">🏭 ${p.재직산업 || '미입력'}</span>
          <span class="tag orange">📊 ${p.회사규모 || '미입력'}</span>
          <span class="tag gray">👤 ${p.직책 || '미입력'}</span>
          <span class="tag gray">📅 ${p.연차 != null ? p.연차 + '년차' : '미입력'}</span>
          <span class="tag gray">🎂 ${p.생년월일 || '미입력'}</span>
        </div>
        ${q1scores.length ? `
        <div style="margin-top:10px;">
          <div style="font-size:12px;font-weight:600;color:#4a5568;margin-bottom:6px;">설문 응답 (경력기술서 카테고리)</div>
          <div style="font-size:11px;color:#718096;margin-bottom:4px;">Q1 (5문항): ${renderQ1Bars(q1scores)}</div>
          ${q2scores.length ? `<div style="font-size:11px;color:#718096;">Q2 (11문항): ${renderQ2Bars(q2scores)}</div>` : ''}
        </div>` : ''}
        ${p.timestamp ? `<div style="font-size:11px;color:#a0aec0;margin-top:10px;">등록일: ${p.timestamp}</div>` : ''}
      </div>`;
    }).join('');
}

function renderQ1Bars(scores) {
  return scores.map((s, i) => `<span style="display:inline-block;margin-right:8px;">Q1_${i+1}: <b style="color:#3182ce">${s}</b>/7</span>`).join('');
}
function renderQ2Bars(scores) {
  return scores.map((s, i) => `<span style="display:inline-block;margin-right:8px;">Q2_${i+1}: <b style="color:#805ad5">${s}</b></span>`).join('');
}

// 탭 전환
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach((b,i) => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
  if (name === 'scoring' && !_scoringLoaded) {
    _scoringLoaded = true;
    loadScoringSummary();
    loadScoring(1);
  }
}
let _scoringLoaded = false;
let _scoringPage = 1;

// 채점 요약
async function loadScoringSummary() {
  const d = await fetchJSON('/api/scoring/summary');
  const stageColors = {
    Run: { bg:'#fff5f5', color:'#c53030', label:'💀 Run' },
    Emergency: { bg:'#fffaf0', color:'#c05621', label:'⚠️ Emergency' },
    Warning: { bg:'#fefcbf', color:'#744210', label:'△ Warning' },
    Stay: { bg:'#f0fff4', color:'#276749', label:'◎ Stay' },
  };
  let html = '';
  for (const [dae, stages] of Object.entries(d)) {
    html += `<div style="margin-bottom:16px;"><div style="font-size:14px;font-weight:700;color:#2d3748;margin-bottom:10px;">${dae}</div>`;
    html += `<div class="score-summary">`;
    for (const [stage, cfg] of Object.entries(stageColors)) {
      html += `<div class="ss-card" style="background:${cfg.bg};border:1px solid;">
        <div class="ss-label" style="color:${cfg.color}">${cfg.label}</div>
        <div class="ss-val" style="color:${cfg.color}">${(stages[stage]||0).toLocaleString()}</div>
        <div style="font-size:11px;color:#a0aec0;">명</div>
      </div>`;
    }
    html += `</div></div>`;
  }
  document.getElementById('scoring-summary-wrap').innerHTML = html;
}

// 채점 테이블
async function loadScoring(page) {
  _scoringPage = page;
  const q = document.getElementById('scoreSearchInput').value.trim();
  const stage = document.getElementById('scoreStageFilter').value;
  const dae = document.getElementById('scoreDaeFilter').value;
  const wrap = document.getElementById('scoring-table-wrap');
  wrap.innerHTML = '<div class="loading">로딩 중...</div>';

  const params = new URLSearchParams({ page, q, stage, dae });
  const d = await fetchJSON('/api/scoring?' + params);

  if (!d.data.length) {
    wrap.innerHTML = '<div class="no-result">검색 결과가 없습니다.</div>';
    document.getElementById('scoring-pagination').innerHTML = '';
    return;
  }

  const stageBadge = (s, g) => {
    const cls = {Run:'badge-run',Emergency:'badge-emergency',Warning:'badge-warning',Stay:'badge-stay'}[s]||'';
    return `<span class="badge ${cls}">${g} ${s}</span>`;
  };
  const newBadge = n => n ? '<span style="background:#ebf8ff;color:#2c5282;font-size:11px;padding:2px 7px;border-radius:10px;font-weight:700;">NEW</span>' : '';

  let rows = d.data.map(r => `
    <tr>
      <td>${r.이름||'-'} ${newBadge(r.NEW)}</td>
      <td style="color:#718096;font-size:12px;">${r.이메일||'-'}</td>
      <td><span style="font-size:13px;color:#4a5568;">${r.대분류}</span></td>
      <td>${stageBadge(r.최종단계, r.대분류등급)}</td>
      <td>
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="flex:1;background:#edf2f7;border-radius:4px;height:8px;overflow:hidden;">
            <div style="width:${Math.min(r.score/r.avg_score*50,100)}%;height:100%;background:${r.최종단계==='Stay'?'#48bb78':r.최종단계==='Warning'?'#ed8936':r.최종단계==='Emergency'?'#fc8181':'#fc4242'};border-radius:4px;"></div>
          </div>
          <span style="font-size:12px;color:#718096;white-space:nowrap;">${(r.score*100).toFixed(1)}%</span>
        </div>
      </td>
      <td style="font-size:12px;color:#a0aec0;">${(r.avg_score*100).toFixed(1)}%</td>
    </tr>`).join('');

  wrap.innerHTML = `
    <div style="font-size:13px;color:#718096;margin-bottom:10px;">총 ${d.total.toLocaleString()}건</div>
    <table>
      <thead><tr>
        <th>이름</th><th>이메일</th><th>대분류</th><th>최종 단계</th><th>점수</th><th>평균 점수</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;

  // 페이지네이션
  const totalPages = Math.ceil(d.total / 50);
  let paginationHtml = '';
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, page + 2);
  if (page > 1) paginationHtml += `<button onclick="loadScoring(${page-1})" class="trend-btn">이전</button>`;
  for (let p = start; p <= end; p++) {
    paginationHtml += `<button onclick="loadScoring(${p})" class="trend-btn ${p===page?'active-btn':''}">${p}</button>`;
  }
  if (page < totalPages) paginationHtml += `<button onclick="loadScoring(${page+1})" class="trend-btn">다음</button>`;
  document.getElementById('scoring-pagination').innerHTML = paginationHtml;
}

// 초기화
loadSummary();
loadTrend(30);
loadDists();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/summary')
def api_summary():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) as total, COUNT(DISTINCT 이름) as unique_count FROM import_raw_data")
            row = c.fetchone()

            today = datetime.now().strftime('%Y-%m-%d')
            c.execute("SELECT COUNT(*) as cnt FROM import_raw_data WHERE DATE(timestamp) = %s", (today,))
            today_row = c.fetchone()

            c.execute("""SELECT AVG(cnt) as avg FROM (
                SELECT DATE(timestamp) as d, COUNT(*) as cnt FROM import_raw_data
                WHERE timestamp IS NOT NULL AND timestamp != '0000-00-00 00:00:00'
                AND DATE(timestamp) >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY DATE(timestamp)) t""")
            weekly = c.fetchone()

        return jsonify({
            'total': row['total'],
            'unique': row['unique_count'],
            'today': today_row['cnt'],
            'today_date': today,
            'weekly_avg': float(weekly['avg'] or 0)
        })
    finally:
        conn.close()

@app.route('/api/trend')
def api_trend():
    days = request.args.get('days', 30, type=int)
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM import_raw_data
                WHERE timestamp IS NOT NULL AND timestamp != '0000-00-00 00:00:00'
                AND DATE(timestamp) >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp)
            """, (days,))
            rows = c.fetchall()
        return jsonify([{'date': str(r['date']), 'count': r['count']} for r in rows])
    finally:
        conn.close()

@app.route('/api/distributions')
def api_distributions():
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) as total FROM import_raw_data")
            total = c.fetchone()['total']

            # 직무 (단순 값만)
            c.execute("""SELECT 재직직무 as label, COUNT(*) as count FROM import_raw_data
                WHERE 재직직무 IS NOT NULL AND 재직직무 NOT LIKE '%,%'
                AND 재직직무 != '' GROUP BY 재직직무 ORDER BY count DESC LIMIT 10""")
            job = c.fetchall()

            # 산업
            c.execute("""SELECT 재직산업 as label, COUNT(*) as count FROM import_raw_data
                WHERE 재직산업 IS NOT NULL AND 재직산업 NOT LIKE '%,%'
                AND 재직산업 != '' GROUP BY 재직산업 ORDER BY count DESC LIMIT 10""")
            industry = c.fetchall()

            # 회사규모
            c.execute("""SELECT 회사규모 as label, COUNT(*) as count FROM import_raw_data
                WHERE 회사규모 IN ('대기업','중견기업','중소기업','스타트업','공공기관','기타')
                GROUP BY 회사규모 ORDER BY count DESC""")
            size = c.fetchall()

            # 직책
            c.execute("""SELECT 직책 as label, COUNT(*) as count FROM import_raw_data
                WHERE 직책 IN ('사원','대리','과장이상','기타','인턴','프리랜서','개인사업자')
                GROUP BY 직책 ORDER BY count DESC""")
            position = c.fetchall()

            # 연차
            c.execute("""SELECT 연차 as label, COUNT(*) as count FROM import_raw_data
                WHERE 연차 IS NOT NULL AND 연차 BETWEEN 0 AND 20
                GROUP BY 연차 ORDER BY 연차""")
            year = c.fetchall()

        return jsonify({
            'total': total,
            'job': list(job),
            'industry': list(industry),
            'size': list(size),
            'position': list(position),
            'year': list(year),
        })
    finally:
        conn.close()

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    conn = get_conn()
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT i.이름, i.이메일, i.연락처, i.생년월일, i.회사명,
                       i.재직직무, i.재직산업, i.직책, i.연차, i.회사규모,
                       i.timestamp,
                       d.Q1_1, d.Q1_2, d.Q1_3, d.Q1_4, d.Q1_5,
                       d.Q2_1, d.Q2_2, d.Q2_3, d.Q2_4, d.Q2_5, d.Q2_6,
                       d.Q2_7, d.Q2_8, d.Q2_9, d.Q2_10, d.Q2_11
                FROM import_raw_data i
                LEFT JOIN resume_data_detail d ON i.이메일 = d.email
                WHERE i.이름 LIKE %s OR i.이메일 LIKE %s
                ORDER BY i.timestamp DESC
                LIMIT 20
            """, (f'%{q}%', f'%{q}%'))
            rows = c.fetchall()

        result = []
        for r in rows:
            row = dict(r)
            if row.get('생년월일'):
                row['생년월일'] = str(row['생년월일'])
            if row.get('timestamp'):
                row['timestamp'] = str(row['timestamp'])
            result.append(row)
        return jsonify(result)
    finally:
        conn.close()

_scoring_cache = None

def compute_scoring():
    global _scoring_cache
    conn = get_conn()
    try:
        with conn.cursor() as c:
            # 가중치 테이블
            c.execute("SELECT * FROM qa_portion ORDER BY id")
            weights = c.fetchall()

            # 질문 컬럼 목록
            q_cols = [w['질문카테고리'] for w in weights]

            # 전체 데이터 (이름, 이메일, 질문컬럼들)
            cols_sql = ', '.join([f'`{col}`' for col in q_cols])
            c.execute(f"SELECT REPLACE(이름, ',', '') as 이름, 이메일, {cols_sql} FROM import_raw_data WHERE 이름 IS NOT NULL AND 이름 != ''")
            rows = c.fetchall()

        if not rows:
            return []

        # 컬럼별 min/max/avg 계산 (숫자 변환)
        col_stats = {}
        for col in q_cols:
            vals = []
            for r in rows:
                try:
                    v = float(r[col]) if r[col] is not None and str(r[col]).strip() != '' else None
                    if v is not None:
                        vals.append(v)
                except:
                    pass
            if vals:
                mn, mx = min(vals), max(vals)
                rng = mx - mn if mx != mn else 1
                norm_vals = [(v - mn) / rng for v in vals]
                col_stats[col] = {'min': mn, 'max': mx, 'range': rng, 'norm_avg': sum(norm_vals) / len(norm_vals)}
            else:
                col_stats[col] = {'min': 0, 'max': 0, 'range': 1, 'norm_avg': 0}

        # 가중치 맵
        w_map = {w['질문카테고리']: w for w in weights}

        # 사람별 채점
        # 중복 이름+이메일 처리: 마지막 레코드 사용
        person_map = {}
        for r in rows:
            key = (r['이름'], r['이메일'] or '')
            person_map[key] = r

        results = []
        for (name, email), r in person_map.items():
            # 대분류별 집계
            daebun = {}  # 대분류 → {val, avg_val, q1_val}

            # 소분류 집계
            sobun = {}  # (대분류, 중분류, 소분류) → {val, avg, q1}
            for col in q_cols:
                if col not in w_map:
                    continue
                w = w_map[col]
                stat = col_stats[col]
                try:
                    raw = float(r[col]) if r[col] is not None and str(r[col]).strip() != '' else None
                except:
                    raw = None

                norm = (raw - stat['min']) / stat['range'] if raw is not None else 0
                norm_avg = stat['norm_avg']
                norm_q1 = norm_avg * 0.70

                q_w = float(w['질문비중']) / 100
                sob_w = float(w['소분류비중']) / 100
                jung_w = float(w['중분류비중']) / 100

                sk = (w['대분류'], w['중분류'], w['소분류'])
                if sk not in sobun:
                    sobun[sk] = {'val': 0, 'avg': 0, 'q1': 0, '소분류비중': sob_w, '중분류비중': jung_w}
                sobun[sk]['val'] += norm * q_w
                sobun[sk]['avg'] += norm_avg * q_w
                sobun[sk]['q1'] += norm_q1 * q_w

            # 중분류 집계
            jungbun = {}
            for (dae, jung, _), sv in sobun.items():
                jk = (dae, jung)
                if jk not in jungbun:
                    jungbun[jk] = {'val': 0, 'avg': 0, 'q1': 0, '중분류비중': sv['중분류비중']}
                jungbun[jk]['val'] += sv['val'] * sv['소분류비중']
                jungbun[jk]['avg'] += sv['avg'] * sv['소분류비중']
                jungbun[jk]['q1'] += sv['q1'] * sv['소분류비중']

            # 대분류 집계
            for (dae, jung), jv in jungbun.items():
                if dae not in daebun:
                    daebun[dae] = {'val': 0, 'avg': 0, 'q1': 0}
                daebun[dae]['val'] += jv['val'] * jv['중분류비중']
                daebun[dae]['avg'] += jv['avg'] * jv['중분류비중']
                daebun[dae]['q1'] += jv['q1'] * jv['중분류비중']

            # 등급 계산
            def get_grade(val, avg, q1):
                if val < q1:
                    return '💀', 'Run'
                elif val < avg - avg * 0.15:
                    return 'X', 'Emergency'
                elif val < avg:
                    return '▽', 'Emergency'
                elif val < avg + avg * 0.15:
                    return '△', 'Warning'
                elif val < 0.9:
                    return '○', 'Warning'
                else:
                    return '◎', 'Stay'

            is_new = 0 if (name or '').startswith(('A', 'B')) else 1

            for dae, dv in daebun.items():
                grade, stage = get_grade(dv['val'], dv['avg'], dv['q1'])
                results.append({
                    '이름': name,
                    '이메일': email,
                    '대분류': dae,
                    '대분류등급': grade,
                    '최종단계': stage,
                    'NEW': is_new,
                    'score': round(dv['val'], 4),
                    'avg_score': round(dv['avg'], 4),
                })

        _scoring_cache = results
        return results
    finally:
        conn.close()

@app.route('/api/scoring')
def api_scoring():
    refresh = request.args.get('refresh', '0')
    global _scoring_cache
    if _scoring_cache is None or refresh == '1':
        compute_scoring()
    data = _scoring_cache or []

    # 필터
    q = request.args.get('q', '').strip()
    stage = request.args.get('stage', '').strip()
    dae = request.args.get('dae', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50

    filtered = data
    if q:
        filtered = [r for r in filtered if q in (r['이름'] or '') or q in (r['이메일'] or '')]
    if stage:
        filtered = [r for r in filtered if r['최종단계'] == stage]
    if dae:
        filtered = [r for r in filtered if r['대분류'] == dae]

    total = len(filtered)
    paged = filtered[(page-1)*per_page: page*per_page]
    return jsonify({'total': total, 'page': page, 'data': paged})

@app.route('/api/scoring/summary')
def api_scoring_summary():
    global _scoring_cache
    if _scoring_cache is None:
        compute_scoring()
    data = _scoring_cache or []

    summary = {}
    for r in data:
        dae = r['대분류']
        stage = r['최종단계']
        if dae not in summary:
            summary[dae] = {'Run': 0, 'Emergency': 0, 'Warning': 0, 'Stay': 0}
        if stage in summary[dae]:
            summary[dae][stage] += 1
    return jsonify(summary)

if __name__ == '__main__':
    print("대시보드 시작: http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
