"""
면접 메이트 대시보드 (interview_mate.py)
=========================================

[ 인터뷰 기반 컨텍스트 문서 | 2026-04-30 ]

## 서비스 개요
- 서비스명: 면접 메이트 (NextLevelTransform)
- 목적: AI 기반 모의면접 서비스의 운영 지표를 실시간 모니터링
- DB 출처: Bubble.io가 AWS RDS PostgreSQL에 자동 생성한 스키마
  - 스키마: basic$1function$1test_live
  - 컬럼명(____text, _____text 등)은 Bubble이 자동 생성한 난독화 네이밍
  - 경고: Bubble 업데이트 시 컬럼명/구조 변경 가능 → 대시보드 장애 위험

## 사용자
- 대상: 운영팀 전체
- 기존 문제: Bubble 내장 뷰의 차트/시각화 부재, 복잡한 필터 조합 불가
- 현재 실행 환경: localhost 로컬 실행만 (외부 서버 미배포)

## 핵심 KPI (매일 확인 우선순위)
1. 결제 성공 건수 및 금액 ← 가장 중요
2. 모의면접 세션 수
3. 로그인 수
4. 유입수 (NLT_169)

## 사업 목표
- 핵심 목표: 결제 전환율 향상 (유입 → 로그인 → 결제 퍼널 최적화)
- Q&A 데이터 활용 방향: 사용자 답변 패턴 분석 → AI 질문 품질 개선

## 데이터 특이사항
- 결제 상태값 비일관성: 'DONE', '결제 완료', '결제완료', 'DONE 완료' 혼재
  → 현재까지 실제 누락은 없음이 확인됨. Bubble 업데이트 시 새 상태값 추가 가능성 존재
- interview_mate_yn_boolean 필드: 의미 불명확, 현재 활용 가치 없음
- UTM 파라미터: 일부 URL에만 존재 → 마케팅 채널별 전환율 추적은 현재 불완전
- 상품 구조: 여러 상품 병행 판매 중 (product_text 필드)

## 성능 이슈
- 탭 전환 시 DB에 최대 5회 동시 접속 → 간헐적 응답 지연 발생 확인
- 개선 방안: psycopg2.pool 또는 SQLAlchemy connection pooling 적용 권장

## 미구현 기능 (우선순위 순)
- [HIGH] 알림 기능: 일별/주별 KPI 요약 → Slack 또는 이메일 발송
- [HIGH] 코호트/퍼널 분석: 유입 → 로그인 → 결제 전환 흐름 추적
- [HIGH] CSV 엑스포트: 결제/세션 데이터 엑셀 다운로드
- [MED]  UTM 파라미터 파싱: URL에서 utm_source/medium/campaign 자동 추출
- [MED]  회원별 헴스맵: 결제 이력 + 세션 이력 통합 뷰
- [LOW]  사용자 인증: 서버 배포 전 로그인 기능 추가

## 보안 주의사항
- DB 접속 정보(DSN)가 코드에 하드코딩 → 서버 배포 전 환경변수 분리 필수
- 이메일/이름 검색 쿼리: SQL 인젝션 취약점 → 파라미터화 처리 완료 (아래 코드 참고)
"""

from flask import Flask, jsonify, request, render_template_string
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

DB_DSN = "postgresql://d230_direct_access:63f111a3140ab33746a0b241fa@d230-postgres-inst1.cxfg4qztxspa.us-west-2.rds.amazonaws.com:5432/postgres"
SCHEMA = 'basic$1function$1test_live'

def get_conn():
    return psycopg2.connect(DB_DSN, cursor_factory=psycopg2.extras.RealDictCursor)

def ts_to_kst(col):
    return f"(TO_TIMESTAMP({col}/1000) AT TIME ZONE 'Asia/Seoul')"

def date_filter(col, start, end):
    return f"{ts_to_kst(col)}::date BETWEEN '{start}' AND '{end}'"

PAY_STATUS_SUCCESS = "(_____text IN ('DONE','결제 완료','결제완료','DONE 완료'))"
PAY_IM_FILTER = "(____text ILIKE '%면접 메이트%')"
PAY_STATUS_CANCEL  = "(_____text IN ('CANCELED','참여취소','PARTIAL_CANCELED','제품회수') OR _____text LIKE '%CANCELED%')"
PAY_STATUS_WAIT    = "(_____text = 'WAITING_FOR_DEPOSIT')"

HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>면접 메이트 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; background: #f0f2f5; color: #1a1a2e; }
header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white; padding: 18px 32px;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 2px 10px rgba(0,0,0,0.3);
}
header h1 { font-size: 20px; font-weight: 700; }
header .sub { font-size: 12px; color: #a0aec0; margin-top: 3px; }
.live-badge { background: #48bb78; color: white; font-size: 11px; padding: 4px 12px; border-radius: 20px; }
.container { max-width: 1500px; margin: 0 auto; padding: 24px 20px; }
.filter-bar {
  background: white; border-radius: 12px; padding: 16px 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 24px;
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
}
.filter-bar label { font-size: 13px; font-weight: 600; color: #4a5568; }
.filter-bar input[type=date] {
  padding: 8px 12px; border: 1.5px solid #e2e8f0; border-radius: 8px;
  font-size: 13px; outline: none;
}
.filter-bar input[type=date]:focus { border-color: #3182ce; }
.filter-bar .sep { color: #a0aec0; }
.btn {
  padding: 8px 20px; background: #3182ce; color: white;
  border: none; border-radius: 8px; font-size: 13px; cursor: pointer; font-weight: 600;
}
.btn:hover { background: #2c5282; }
.btn-sm {
  padding: 4px 12px; background: #3182ce; color: white;
  border: none; border-radius: 6px; font-size: 12px; cursor: pointer; font-weight: 600;
}
.btn-ghost {
  padding: 8px 16px; background: white; color: #4a5568;
  border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 13px; cursor: pointer; font-weight: 600;
}
.btn-ghost:hover { background: #f7fafc; }
.cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 24px; }
.card {
  background: white; border-radius: 12px; padding: 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-top: 4px solid #e2e8f0;
}
.card.blue   { border-top-color: #3182ce; }
.card.green  { border-top-color: #38a169; }
.card.purple { border-top-color: #805ad5; }
.card.orange { border-top-color: #dd6b20; }
.card.teal   { border-top-color: #319795; }
.card .label { font-size: 12px; color: #718096; font-weight: 500; margin-bottom: 8px; }
.card .value { font-size: 30px; font-weight: 700; }
.card.blue   .value { color: #3182ce; }
.card.green  .value { color: #38a169; }
.card.purple .value { color: #805ad5; }
.card.orange .value { color: #dd6b20; }
.card.teal   .value { color: #319795; }
.card .sub   { font-size: 11px; color: #a0aec0; margin-top: 4px; }
.delta.up   { color: #38a169; font-size:12px; font-weight:600; margin-top:6px; }
.delta.down { color: #e53e3e; font-size:12px; font-weight:600; margin-top:6px; }
.delta.same { color: #a0aec0; font-size:12px; margin-top:6px; }
.section {
  background: white; border-radius: 12px; padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 24px;
}
.section h2 {
  font-size: 15px; font-weight: 700; margin-bottom: 20px; color: #2d3748;
  border-left: 4px solid #3182ce; padding-left: 12px;
}
.section h2.green  { border-left-color: #38a169; }
.section h2.purple { border-left-color: #805ad5; }
.section h2.orange { border-left-color: #dd6b20; }
.section h2.teal   { border-left-color: #319795; }
.section h2.pink   { border-left-color: #d53f8c; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
.chart-wrap { position: relative; height: 260px; }
.tabs { display: flex; gap: 4px; margin-bottom: 24px; border-bottom: 2px solid #e2e8f0; flex-wrap: wrap; }
.tab-btn {
  padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer;
  border: none; background: none; color: #718096; border-bottom: 3px solid transparent;
  margin-bottom: -2px;
}
.tab-btn.active { color: #3182ce; border-bottom-color: #3182ce; }
.tab-content { display: none; }
.tab-content.active { display: block; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f7fafc; color: #4a5568; padding: 10px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e2e8f0; white-space: nowrap; }
td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; color: #2d3748; }
tr:hover td { background: #f7fafc; }
.badge { display:inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }
.badge-success { background: #f0fff4; color: #276749; border: 1px solid #9ae6b4; }
.badge-cancel  { background: #fff5f5; color: #c53030; border: 1px solid #feb2b2; }
.badge-wait    { background: #fefcbf; color: #744210; border: 1px solid #f6e05e; }
.badge-other   { background: #f7fafc; color: #4a5568; border: 1px solid #e2e8f0; }
.loading { text-align:center; color:#718096; padding:40px; font-size:14px; }
.no-data { text-align:center; color:#a0aec0; padding:40px; font-size:14px; }
.search-row { display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; align-items:center; }
.search-row input, .search-row select {
  padding: 8px 12px; border: 1.5px solid #e2e8f0; border-radius: 8px; font-size: 13px; outline: none;
}
.search-row input { flex:1; min-width:160px; }
/* 세션 확장 행 */
.qa-expand-row { display: none; background: #f7fafc; }
.qa-expand-row td { padding: 0; }
.qa-inner { padding: 12px 24px; }
.qa-item { border-left: 3px solid #319795; padding: 8px 12px; margin-bottom: 8px; background: white; border-radius: 0 6px 6px 0; }
.qa-item .qi-cat { font-size: 11px; color: #319795; font-weight: 700; margin-bottom: 4px; }
.qa-item .qi-q { font-size: 13px; color: #2d3748; margin-bottom: 4px; }
.qa-item .qi-a { font-size: 12px; color: #718096; }
@media(max-width:1100px){ .cards{grid-template-columns:repeat(3,1fr);} }
@media(max-width:800px){ .cards{grid-template-columns:repeat(2,1fr);} .grid-2{grid-template-columns:1fr;} }
</style>
</head>
<body>

<header>
  <div>
    <h1>면접 메이트 대시보드</h1>
    <div class="sub">basic$1function$1test_live · PostgreSQL</div>
  </div>
  <span class="live-badge">● LIVE</span>
</header>

<div class="container">

  <div class="filter-bar">
    <label>기간 선택</label>
    <input type="date" id="startDate">
    <span class="sep">~</span>
    <input type="date" id="endDate">
    <button class="btn" onclick="applyFilter()">조회</button>
    <button class="btn-ghost" onclick="setPreset(7)">최근 7일</button>
    <button class="btn-ghost" onclick="setPreset(30)">최근 30일</button>
    <button class="btn-ghost" onclick="setPreset(90)">최근 90일</button>
    <span id="filter-info" style="font-size:12px;color:#718096;margin-left:4px;"></span>
  </div>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('overview',this)">📊 개요</button>
    <button class="tab-btn" onclick="switchTab('traffic',this)">🔗 유입 정보</button>
    <button class="tab-btn" onclick="switchTab('login',this)">🔐 로그인</button>
    <button class="tab-btn" onclick="switchTab('payment',this)">💳 결제</button>
    <button class="tab-btn" onclick="switchTab('simulation',this)">🎤 모의면접 세션</button>
  </div>

  <!-- ===== 개요 ===== -->
  <div class="tab-content active" id="tab-overview">
    <div class="cards">
      <div class="card blue">
        <div class="label">로그인 수</div>
        <div class="value" id="ov-login">-</div>
        <div class="sub">NLT_136</div>
        <div id="ov-login-delta"></div>
      </div>
      <div class="card green">
        <div class="label">결제 성공 건수</div>
        <div class="value" id="ov-pay">-</div>
        <div class="sub">면접 메이트 제품</div>
        <div id="ov-pay-delta"></div>
      </div>
      <div class="card purple">
        <div class="label">결제 총액</div>
        <div class="value" id="ov-amount">-</div>
        <div class="sub">면접 메이트 제품 · 원</div>
        <div id="ov-amount-delta"></div>
      </div>
      <div class="card orange">
        <div class="label">모의면접 세션 수</div>
        <div class="value" id="ov-sim">-</div>
        <div class="sub">NLT_159</div>
        <div id="ov-sim-delta"></div>
      </div>
      <div class="card teal">
        <div class="label">모의면접 총 질문 수</div>
        <div class="value" id="ov-qa">-</div>
        <div class="sub">NLT_162</div>
        <div id="ov-qa-delta"></div>
      </div>
    </div>
    <div class="grid-2">
      <div class="section"><h2 class="pink">일별 유입 추이</h2><div class="chart-wrap"><canvas id="trafficTrendChart"></canvas></div></div>
      <div class="section"><h2>일별 로그인 추이</h2><div class="chart-wrap"><canvas id="loginTrendChart"></canvas></div></div>
    </div>
    <div class="grid-2">
      <div class="section"><h2 class="green">일별 결제 추이</h2><div class="chart-wrap"><canvas id="payTrendChart"></canvas></div></div>
      <div class="section"><h2 class="orange">일별 모의면접 진행 추이</h2><div class="chart-wrap"><canvas id="simTrendChart"></canvas></div></div>
    </div>
  </div>

  <!-- ===== 유입 정보 ===== -->
  <div class="tab-content" id="tab-traffic">
    <div class="section">
      <h2 class="pink">유입 정보 목록 (NLT_169)</h2>
      <div id="trafficTableWrap"><div class="loading">조회 중...</div></div>
    </div>
  </div>

  <!-- ===== 로그인 ===== -->
  <div class="tab-content" id="tab-login">
    <div class="section"><h2>일별 로그인 현황</h2><div class="chart-wrap" style="height:300px"><canvas id="loginDetailChart"></canvas></div></div>
    <div class="section">
      <h2>로그인 상세 목록</h2>
      <div class="search-row">
        <input type="text" id="loginSearch" placeholder="이메일 검색...">
        <button class="btn" onclick="loadLoginTable(1)">검색</button>
      </div>
      <div id="loginTableWrap"><div class="loading">조회 중...</div></div>
      <div id="loginPagination" style="display:flex;gap:8px;justify-content:center;margin-top:16px;"></div>
    </div>
  </div>

  <!-- ===== 결제 ===== -->
  <div class="tab-content" id="tab-payment">
    <div class="grid-2">
      <div class="section"><h2>일별 결제 건수 (성공)</h2><div class="chart-wrap"><canvas id="payCountChart"></canvas></div></div>
      <div class="section"><h2 class="green">일별 결제 금액 (성공)</h2><div class="chart-wrap"><canvas id="payAmountChart"></canvas></div></div>
    </div>
    <div class="section">
      <h2>결제 상세 목록</h2>
      <div class="search-row">
        <select id="payProductFilter" style="min-width:200px"><option value="">전체 제품</option></select>
        <select id="payStatusFilter">
          <option value="">전체 상태</option>
          <option value="success">✅ 성공</option>
          <option value="cancel">❌ 취소</option>
          <option value="wait">⏳ 대기</option>
        </select>
        <select id="payRefundFilter">
          <option value="">환불 전체</option>
          <option value="true">환불됨</option>
          <option value="false">환불 아님</option>
        </select>
        <button class="btn" onclick="loadPayTable(1)">조회</button>
      </div>
      <div id="payTableWrap"><div class="loading">조회 중...</div></div>
      <div id="payPagination" style="display:flex;gap:8px;justify-content:center;margin-top:16px;"></div>
    </div>
  </div>

  <!-- ===== 모의면접 세션 (159 + 162 join) ===== -->
  <div class="tab-content" id="tab-simulation">
    <div class="section"><h2>일별 모의면접 세션 추이</h2><div class="chart-wrap" style="height:280px"><canvas id="simDetailChart"></canvas></div></div>
    <div class="grid-2">
      <div class="section"><h2>상품 유형별 분포</h2><div class="chart-wrap"><canvas id="simProductChart"></canvas></div></div>
      <div class="section"><h2 class="orange">직무 분포</h2><div id="simJobDist"></div></div>
    </div>
    <div class="section">
      <h2>모의면접 세션 목록 (Q&A 포함)</h2>
      <div class="search-row">
        <input type="text" id="simSearch" placeholder="이름/이메일 검색...">
        <select id="simProductFilter"><option value="">전체 상품</option></select>
        <button class="btn" onclick="loadSimTable(1)">검색</button>
      </div>
      <div id="simTableWrap"><div class="loading">조회 중...</div></div>
      <div id="simPagination" style="display:flex;gap:8px;justify-content:center;margin-top:16px;"></div>
    </div>
  </div>

</div>

<script>
const CHARTS = {};
let currentStart='', currentEnd='';

function todayKST() { return new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}); }
function daysAgoKST(n) { const d=new Date(); d.setDate(d.getDate()-n); return d.toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}); }
function setPreset(days) {
  document.getElementById('startDate').value=daysAgoKST(days-1);
  document.getElementById('endDate').value=todayKST();
  applyFilter();
}
function applyFilter() {
  currentStart=document.getElementById('startDate').value;
  currentEnd=document.getElementById('endDate').value;
  if(!currentStart||!currentEnd) return;
  document.getElementById('filter-info').textContent=`${currentStart} ~ ${currentEnd}`;
  loadAll();
}
function qs(obj){ return '?'+Object.entries(obj).map(([k,v])=>k+'='+encodeURIComponent(v)).join('&'); }
async function fetchJSON(url){ const r=await fetch(url); return r.json(); }
function mkChart(id,type,labels,datasets,opts={}) {
  if(CHARTS[id]) CHARTS[id].destroy();
  const ctx=document.getElementById(id); if(!ctx) return;
  CHARTS[id]=new Chart(ctx,{type,data:{labels,datasets},options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{display:datasets.length>1}},
    scales:type==='doughnut'||type==='pie'?{}:{
      x:{grid:{display:false},ticks:{font:{size:11},maxRotation:45}},
      y:{beginAtZero:true,grid:{color:'#f0f0f0'}}
    },...opts
  }});
}
function paginator(cid,page,total,per,fn) {
  const tp=Math.ceil(total/per); let h='';
  if(page>1) h+=`<button class="btn-ghost" onclick="${fn}(${page-1})">이전</button>`;
  for(let p=Math.max(1,page-2);p<=Math.min(tp,page+2);p++)
    h+=`<button class="${p===page?'btn':'btn-ghost'}" onclick="${fn}(${p})">${p}</button>`;
  if(page<tp) h+=`<button class="btn-ghost" onclick="${fn}(${page+1})">다음</button>`;
  document.getElementById(cid).innerHTML=h;
}
function delta(v,p) {
  if(!p) return '';
  const d=v-p,pct=(d/p*100).toFixed(1);
  if(d>0) return `<div class="delta up">▲ ${d.toLocaleString()} (+${pct}%)</div>`;
  if(d<0) return `<div class="delta down">▼ ${Math.abs(d).toLocaleString()} (${pct}%)</div>`;
  return `<div class="delta same">- 동일</div>`;
}
function statusBadge(s) {
  if(!s) return '<span class="badge badge-other">-</span>';
  const sc=s.trim();
  if(['DONE','결제 완료','결제완료','DONE 완료'].includes(sc))
    return `<span class="badge badge-success">✅ 성공</span>`;
  if(sc.includes('CANCEL')||['참여취소','PARTIAL_CANCELED','제품회수'].includes(sc))
    return `<span class="badge badge-cancel">❌ ${sc}</span>`;
  if(sc==='WAITING_FOR_DEPOSIT')
    return `<span class="badge badge-wait">⏳ 대기</span>`;
  return `<span class="badge badge-other">${sc}</span>`;
}

// ── 개요 ──
async function loadOverview() {
  const d=await fetchJSON('/api/summary'+qs({start:currentStart,end:currentEnd}));
  document.getElementById('ov-login').textContent=d.login.toLocaleString();
  document.getElementById('ov-pay').textContent=d.pay_count.toLocaleString();
  document.getElementById('ov-amount').textContent=Number(d.pay_amount||0).toLocaleString();
  document.getElementById('ov-sim').textContent=d.sim.toLocaleString();
  document.getElementById('ov-qa').textContent=d.qa.toLocaleString();
  document.getElementById('ov-login-delta').innerHTML=delta(d.login,d.prev_login);
  document.getElementById('ov-pay-delta').innerHTML=delta(d.pay_count,d.prev_pay_count);
  document.getElementById('ov-amount-delta').innerHTML=delta(d.pay_amount,d.prev_pay_amount);
  document.getElementById('ov-sim-delta').innerHTML=delta(d.sim,d.prev_sim);
  document.getElementById('ov-qa-delta').innerHTML=delta(d.qa,d.prev_qa);
  const t=await fetchJSON('/api/trend'+qs({start:currentStart,end:currentEnd}));
  const labels=t.map(r=>r.dt);
  mkChart('loginTrendChart','bar',labels,[{label:'로그인',data:t.map(r=>r.login),backgroundColor:'rgba(49,130,206,0.7)',borderColor:'#3182ce',borderWidth:1,borderRadius:4}]);
  mkChart('payTrendChart','bar',labels,[{label:'결제건수(면접메이트)',data:t.map(r=>r.pay),backgroundColor:'rgba(56,161,105,0.7)',borderColor:'#38a169',borderWidth:1,borderRadius:4}]);
  mkChart('simTrendChart','bar',labels,[{label:'모의면접',data:t.map(r=>r.sim),backgroundColor:'rgba(221,107,32,0.7)',borderColor:'#dd6b20',borderWidth:1,borderRadius:4}]);
  mkChart('trafficTrendChart','bar',labels,[{label:'유입수',data:t.map(r=>r.traffic),backgroundColor:'rgba(213,63,140,0.7)',borderColor:'#d53f8c',borderWidth:1,borderRadius:4}]);
}

// ── 유입 정보 ──
async function loadTrafficDetail() {
  const d=await fetchJSON('/api/traffic/list'+qs({start:currentStart,end:currentEnd}));
  if(!d.data.length){document.getElementById('trafficTableWrap').innerHTML='<div class="no-data">기간 내 유입 데이터 없음 (전체 데이터 표시)</div>';}
  const rows=d.data;
  document.getElementById('trafficTableWrap').innerHTML=`
    <div style="font-size:13px;color:#718096;margin-bottom:10px;">총 ${rows.length}건</div>
    <table><thead><tr><th>생성일시(KST)</th><th>페이지명</th><th>URL</th></tr></thead>
    <tbody>${rows.map(r=>`<tr>
      <td>${r.created||'-'}</td>
      <td><span style="background:#faf5ff;color:#553c9a;border:1px solid #d6bcfa;border-radius:12px;padding:3px 10px;font-size:12px;font-weight:600">${r.page_name||'-'}</span></td>
      <td style="font-size:12px;color:#3182ce;word-break:break-all">${r.url?`<a href="${r.url}" target="_blank" style="color:#3182ce">${r.url}</a>`:'-'}</td>
    </tr>`).join('')}</tbody></table>`;
}

// ── 로그인 ──
async function loadLoginDetail() {
  const t=await fetchJSON('/api/trend'+qs({start:currentStart,end:currentEnd}));
  mkChart('loginDetailChart','bar',t.map(r=>r.dt),[{label:'로그인 수',data:t.map(r=>r.login),backgroundColor:'rgba(49,130,206,0.7)',borderColor:'#3182ce',borderWidth:1,borderRadius:4}]);
  loadLoginTable(1);
}
async function loadLoginTable(page) {
  const q=document.getElementById('loginSearch').value;
  const d=await fetchJSON('/api/login/list'+qs({start:currentStart,end:currentEnd,q,page}));
  if(!d.data.length){document.getElementById('loginTableWrap').innerHTML='<div class="no-data">데이터 없음</div>';return;}
  document.getElementById('loginTableWrap').innerHTML=`
    <div style="font-size:13px;color:#718096;margin-bottom:10px;">총 ${d.total.toLocaleString()}건</div>
    <table><thead><tr><th>이메일</th><th>로그인 일시(KST)</th><th>로그아웃 일시</th><th>IP</th><th>고유코드</th></tr></thead>
    <tbody>${d.data.map(r=>`<tr>
      <td>${r.email||'-'}</td><td>${r.login_dt||'-'}</td><td>${r.logout_dt||'-'}</td>
      <td style="font-size:12px;color:#718096">${r.ip||'-'}</td>
      <td style="font-size:11px;color:#a0aec0">${r.code||'-'}</td>
    </tr>`).join('')}</tbody></table>`;
  paginator('loginPagination',page,d.total,50,'loadLoginTable');
}

// ── 결제 ──
async function loadPayDetail() {
  // 제품 드롭다운 로드
  const pd=await fetchJSON('/api/payment/products'+qs({start:currentStart,end:currentEnd}));
  const sel=document.getElementById('payProductFilter');
  sel.innerHTML='<option value="">전체 제품</option>'+pd.map(p=>`<option value="${p}">${p||'(없음)'}</option>`).join('');
  const t=await fetchJSON('/api/trend'+qs({start:currentStart,end:currentEnd}));
  mkChart('payCountChart','bar',t.map(r=>r.dt),[{label:'결제건수',data:t.map(r=>r.pay),backgroundColor:'rgba(56,161,105,0.7)',borderColor:'#38a169',borderWidth:1,borderRadius:4}]);
  mkChart('payAmountChart','line',t.map(r=>r.dt),[{label:'결제금액(원)',data:t.map(r=>r.pay_amount),borderColor:'#38a169',backgroundColor:'rgba(56,161,105,0.1)',tension:0.3,fill:true}]);
  loadPayTable(1);
}
async function loadPayTable(page) {
  const product=document.getElementById('payProductFilter').value;
  const status=document.getElementById('payStatusFilter').value;
  const refund=document.getElementById('payRefundFilter').value;
  const d=await fetchJSON('/api/payment/list'+qs({start:currentStart,end:currentEnd,product,status,refund,page}));
  if(!d.data.length){document.getElementById('payTableWrap').innerHTML='<div class="no-data">데이터 없음</div>';return;}
  document.getElementById('payTableWrap').innerHTML=`
    <div style="font-size:13px;color:#718096;margin-bottom:10px;">총 ${d.total.toLocaleString()}건 · 합계 ${d.total_amount.toLocaleString()}원</div>
    <table><thead><tr><th>주문일자</th><th>주문번호</th><th>제품명</th><th>주문자명</th><th>연락처</th><th>결제수단</th><th>결제상태</th><th>결제금액</th><th>쿠폰</th><th>환불여부</th></tr></thead>
    <tbody>${d.data.map(r=>`<tr>
      <td style="white-space:nowrap">${r.created||'-'}</td>
      <td style="font-size:11px;color:#a0aec0">${r.order_id||'-'}</td>
      <td><span style="background:#fffaf0;color:#c05621;border:1px solid #fbd38d;border-radius:12px;padding:2px 8px;font-size:11px;font-weight:600">${r.product||'-'}</span></td>
      <td>${r.buyer_name||'-'}</td>
      <td style="font-size:12px;color:#718096">${r.phone||'-'}</td>
      <td>${r.method||'-'}</td>
      <td>${statusBadge(r.status)}</td>
      <td style="font-weight:600;color:#38a169">${r.amount!=null?Number(r.amount).toLocaleString()+'원':'-'}</td>
      <td style="font-size:12px;color:#718096">${r.coupon||'-'}</td>
      <td>${r.refund===true?'<span class="badge badge-cancel">환불</span>':r.refund===false?'<span style="color:#a0aec0;font-size:12px">-</span>':'-'}</td>
    </tr>`).join('')}</tbody></table>`;
  paginator('payPagination',page,d.total,50,'loadPayTable');
}

// ── 모의면접 세션 ──
async function loadSimDetail() {
  const t=await fetchJSON('/api/trend'+qs({start:currentStart,end:currentEnd}));
  mkChart('simDetailChart','bar',t.map(r=>r.dt),[{label:'세션수',data:t.map(r=>r.sim),backgroundColor:'rgba(221,107,32,0.7)',borderColor:'#dd6b20',borderWidth:1,borderRadius:4}]);
  const dist=await fetchJSON('/api/simulation/dist'+qs({start:currentStart,end:currentEnd}));
  mkChart('simProductChart','doughnut',dist.product.map(x=>x.label||'기타'),[{data:dist.product.map(x=>x.cnt),backgroundColor:['#dd6b20','#f6ad55','#fbd38d','#ed8936','#c05621','#9c4221']}],{plugins:{legend:{position:'right'}}});
  const jobEl=document.getElementById('simJobDist');
  const total=dist.job.reduce((s,x)=>s+x.cnt,0)||1;
  jobEl.innerHTML=dist.job.slice(0,10).map(x=>{
    const pct=Math.round(x.cnt/total*100);
    return `<div style="display:flex;align-items:center;margin-bottom:10px;">
      <div style="width:120px;font-size:13px;color:#4a5568;flex-shrink:0">${x.label||'미입력'}</div>
      <div style="flex:1;background:#edf2f7;border-radius:4px;height:20px;overflow:hidden">
        <div style="width:${pct}%;height:100%;background:linear-gradient(90deg,#dd6b20,#f6ad55);display:flex;align-items:center;padding-left:6px">
          <span style="font-size:11px;color:white;font-weight:600">${pct}%</span>
        </div>
      </div>
      <div style="width:40px;text-align:right;font-size:12px;color:#718096;margin-left:8px">${x.cnt}</div>
    </div>`;
  }).join('');
  // 상품 필터 로드
  const psel=document.getElementById('simProductFilter');
  psel.innerHTML='<option value="">전체 상품</option>'+dist.product.map(x=>`<option value="${x.label||''}">${x.label||'(없음)'}</option>`).join('');
  loadSimTable(1);
}
async function loadSimTable(page) {
  const q=document.getElementById('simSearch').value;
  const product=document.getElementById('simProductFilter').value;
  const d=await fetchJSON('/api/simulation/list'+qs({start:currentStart,end:currentEnd,q,product,page}));
  if(!d.data.length){document.getElementById('simTableWrap').innerHTML='<div class="no-data">데이터 없음</div>';return;}
  let rows='';
  d.data.forEach((r,i)=>{
    rows+=`<tr id="sr${i}">
      <td style="white-space:nowrap">${r.created||'-'}</td>
      <td>${r.name||'-'}</td>
      <td style="font-size:12px;color:#718096">${r.email||'-'}</td>
      <td>${r.job||'-'}</td>
      <td>${r.company||'-'}</td>
      <td><span style="background:#fffaf0;color:#c05621;border:1px solid #fbd38d;border-radius:12px;padding:2px 8px;font-size:11px;font-weight:700">${r.product||'-'}</span></td>
      <td>${r.interview_mate?'<span class="badge badge-success">Y</span>':'<span style="color:#a0aec0;font-size:12px">-</span>'}</td>
      <td><span style="background:#ebf8ff;color:#2c5282;border-radius:12px;padding:2px 10px;font-size:12px;font-weight:700">${r.qa_count}개</span></td>
      <td>${r.qa_count>0?`<button class="btn-sm" onclick="toggleQa('${r.session_id}',${i})">▼ Q&A</button>`:'<span style="color:#a0aec0;font-size:12px">-</span>'}</td>
    </tr>
    <tr class="qa-expand-row" id="qr${i}"><td colspan="9">
      <div class="qa-inner" id="qi${i}"><div class="loading">불러오는 중...</div></div>
    </td></tr>`;
  });
  document.getElementById('simTableWrap').innerHTML=`
    <div style="font-size:13px;color:#718096;margin-bottom:10px;">총 ${d.total.toLocaleString()}건</div>
    <table><thead><tr><th>세션 생성일(KST)</th><th>이름</th><th>이메일</th><th>직무</th><th>지원회사</th><th>상품</th><th>면접메이트</th><th>Q&A 수</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>`;
  paginator('simPagination',page,d.total,50,'loadSimTable');
}
const _qaOpen={};
async function toggleQa(sessionId,i) {
  const row=document.getElementById('qr'+i);
  const inner=document.getElementById('qi'+i);
  if(row.style.display==='table-row') { row.style.display='none'; return; }
  row.style.display='table-row';
  if(_qaOpen[sessionId]) { inner.innerHTML=_qaOpen[sessionId]; return; }
  const d=await fetchJSON('/api/session/qa'+qs({session_id:sessionId}));
  if(!d.length){ inner.innerHTML='<div style="color:#a0aec0;padding:12px">Q&A 데이터 없음</div>'; return; }
  const html=d.map(q=>`<div class="qa-item">
    <div class="qi-cat">[${q.no||'-'}번] ${q.category||'카테고리 없음'}</div>
    <div class="qi-q">Q. ${q.question||'-'}</div>
    <div class="qi-a">A. ${q.answer||'-'}</div>
    ${q.feedback?`<div style="font-size:11px;color:#805ad5;margin-top:4px">💬 ${q.feedback}</div>`:''}
  </div>`).join('');
  _qaOpen[sessionId]=html;
  inner.innerHTML=html;
}

// ── 탭 전환 ──
const TAB_LOADERS={overview:loadOverview,traffic:loadTrafficDetail,login:loadLoginDetail,payment:loadPayDetail,simulation:loadSimDetail};
const TAB_NAMES=['overview','traffic','login','payment','simulation'];
function switchTab(name,btn) {
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-'+name).classList.add('active');
  if(currentStart) TAB_LOADERS[name]();
}
function loadAll() {
  const btns=document.querySelectorAll('.tab-btn');
  btns.forEach((b,i)=>{ if(b.classList.contains('active')) TAB_LOADERS[TAB_NAMES[i]](); });
}
setPreset(30);
</script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/api/summary')
def api_summary():
    start = request.args.get('start')
    end   = request.args.get('end')
    conn  = get_conn()
    try:
        cur = conn.cursor()

        def cnt(table, dcol, extra=''):
            flt = date_filter(f'"{dcol}"', start, end)
            cur.execute(f'SELECT COUNT(*) as c FROM "{SCHEMA}"."{table}" WHERE {flt} {extra}')
            return cur.fetchone()['c']

        def prev_cnt(table, dcol, extra=''):
            days = (datetime.strptime(end,'%Y-%m-%d') - datetime.strptime(start,'%Y-%m-%d')).days + 1
            pe = (datetime.strptime(start,'%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
            ps = (datetime.strptime(start,'%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
            flt = date_filter(f'"{dcol}"', ps, pe)
            cur.execute(f'SELECT COUNT(*) as c FROM "{SCHEMA}"."{table}" WHERE {flt} {extra}')
            return cur.fetchone()['c']

        login  = cnt('custom$0_nlt_136_changeup_login_out_info', 'Created Date')
        p_login = prev_cnt('custom$0_nlt_136_changeup_login_out_info', 'Created Date')

        flt = date_filter('"Created Date"', start, end) + f' AND {PAY_STATUS_SUCCESS} AND {PAY_IM_FILTER}'
        cur.execute(f'SELECT COUNT(*) as c, COALESCE(SUM(amount_number),0) as s FROM "{SCHEMA}"."custom$0__4" WHERE {flt}')
        row = cur.fetchone()
        pay_c, pay_a = row['c'], float(row['s'])

        days = (datetime.strptime(end,'%Y-%m-%d') - datetime.strptime(start,'%Y-%m-%d')).days + 1
        pe = (datetime.strptime(start,'%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        ps = (datetime.strptime(start,'%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
        pflt = date_filter('"Created Date"', ps, pe) + f' AND {PAY_STATUS_SUCCESS} AND {PAY_IM_FILTER}'
        cur.execute(f'SELECT COUNT(*) as c, COALESCE(SUM(amount_number),0) as s FROM "{SCHEMA}"."custom$0__4" WHERE {pflt}')
        prow = cur.fetchone()

        sim   = cnt('custom$0_nlt_159_interview_simulation_data', 'Created Date')
        p_sim = prev_cnt('custom$0_nlt_159_interview_simulation_data', 'Created Date')
        qa    = cnt('custom$0_nlt_162_chatgpt_raw', 'Created Date')
        p_qa  = prev_cnt('custom$0_nlt_162_chatgpt_raw', 'Created Date')

        return jsonify({
            'login': login, 'prev_login': p_login,
            'pay_count': pay_c, 'prev_pay_count': prow['c'],
            'pay_amount': pay_a, 'prev_pay_amount': float(prow['s']),
            'sim': sim, 'prev_sim': p_sim,
            'qa': qa, 'prev_qa': p_qa,
        })
    finally:
        conn.close()


@app.route('/api/trend')
def api_trend():
    start = request.args.get('start')
    end   = request.args.get('end')
    conn  = get_conn()
    try:
        cur = conn.cursor()

        def daily(table, dcol, extra=''):
            flt = date_filter(f'"{dcol}"', start, end)
            cur.execute(f"""
                SELECT {ts_to_kst(f'"{dcol}"')}::date AS dt, COUNT(*) as c
                FROM "{SCHEMA}"."{table}" WHERE {flt} {extra} GROUP BY 1 ORDER BY 1
            """)
            return {str(r['dt']): r['c'] for r in cur.fetchall()}

        login_d   = daily('custom$0_nlt_136_changeup_login_out_info', 'Created Date')
        pay_d     = daily('custom$0__4', 'Created Date', f'AND {PAY_STATUS_SUCCESS} AND {PAY_IM_FILTER}')
        sim_d     = daily('custom$0_nlt_159_interview_simulation_data', 'Created Date')
        qa_d      = daily('custom$0_nlt_162_chatgpt_raw', 'Created Date')
        traffic_d = daily('custom$0_nlt_169_nlt_cust_traffic_info', 'Created Date')

        flt = date_filter('"Created Date"', start, end) + f' AND {PAY_STATUS_SUCCESS} AND {PAY_IM_FILTER}'
        cur.execute(f"""
            SELECT {ts_to_kst('"Created Date"')}::date AS dt, COALESCE(SUM(amount_number),0) as s
            FROM "{SCHEMA}"."custom$0__4" WHERE {flt} GROUP BY 1 ORDER BY 1
        """)
        pay_a_d = {str(r['dt']): float(r['s']) for r in cur.fetchall()}

        result = []
        d = datetime.strptime(start, '%Y-%m-%d')
        e = datetime.strptime(end, '%Y-%m-%d')
        while d <= e:
            ds = d.strftime('%Y-%m-%d')
            result.append({'dt': ds, 'login': login_d.get(ds,0), 'pay': pay_d.get(ds,0),
                           'pay_amount': pay_a_d.get(ds,0), 'sim': sim_d.get(ds,0),
                           'qa': qa_d.get(ds,0), 'traffic': traffic_d.get(ds,0)})
            d += timedelta(days=1)
        return jsonify(result)
    finally:
        conn.close()


@app.route('/api/traffic/list')
def api_traffic_list():
    start = request.args.get('start')
    end   = request.args.get('end')
    conn  = get_conn()
    try:
        cur = conn.cursor()
        # 데이터가 적으니 전체 조회 (날짜 필터 적용, 없으면 전체)
        if start and end:
            flt = 'WHERE ' + date_filter('"Created Date"', start, end)
        else:
            flt = ''
        cur.execute(f"""
            SELECT {ts_to_kst('"Created Date"')} AS created,
                   page_name_text AS page_name,
                   url_text AS url
            FROM "{SCHEMA}"."custom$0_nlt_169_nlt_cust_traffic_info"
            {flt}
            ORDER BY "Created Date" DESC
        """)
        rows = []
        for r in cur.fetchall():
            rows.append({'created': str(r['created']) if r['created'] else None,
                         'page_name': r['page_name'], 'url': r['url']})
        return jsonify({'data': rows})
    finally:
        conn.close()


@app.route('/api/login/list')
def api_login_list():
    start = request.args.get('start')
    end   = request.args.get('end')
    q     = request.args.get('q', '')
    page  = int(request.args.get('page', 1))
    per   = 50
    conn  = get_conn()
    try:
        cur = conn.cursor()
        flt = date_filter('"Created Date"', start, end)
        params = []
        if q:
            flt += " AND email_text ILIKE %s"
            params.append(f'%{q}%')
        cur.execute(f'SELECT COUNT(*) as c FROM "{SCHEMA}"."custom$0_nlt_136_changeup_login_out_info" WHERE {flt}', params)
        total = cur.fetchone()['c']
        cur.execute(f"""
            SELECT email_text AS email,
                   {ts_to_kst('"login_date_date"')} AS login_dt,
                   {ts_to_kst('"logout_date_date"')} AS logout_dt,
                   login_ip_text AS ip, unique_code_text AS code
            FROM "{SCHEMA}"."custom$0_nlt_136_changeup_login_out_info"
            WHERE {flt} ORDER BY "Created Date" DESC
            LIMIT {per} OFFSET {(page-1)*per}
        """, params)
        rows = [{'email': r['email'],
                 'login_dt': str(r['login_dt']) if r['login_dt'] else None,
                 'logout_dt': str(r['logout_dt']) if r['logout_dt'] else None,
                 'ip': r['ip'], 'code': r['code']} for r in cur.fetchall()]
        return jsonify({'total': total, 'data': rows})
    finally:
        conn.close()


@app.route('/api/payment/products')
def api_payment_products():
    start = request.args.get('start')
    end   = request.args.get('end')
    conn  = get_conn()
    try:
        cur = conn.cursor()
        flt = (date_filter('"Created Date"', start, end) if start and end else '1=1') + f' AND {PAY_IM_FILTER}'
        cur.execute(f"""
            SELECT DISTINCT ____text AS p FROM "{SCHEMA}"."custom$0__4"
            WHERE {flt} AND ____text IS NOT NULL AND ____text != ''
            ORDER BY p
        """)
        return jsonify([r['p'] for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/payment/list')
def api_payment_list():
    start   = request.args.get('start')
    end     = request.args.get('end')
    product = request.args.get('product', '')
    status  = request.args.get('status', '')
    refund  = request.args.get('refund', '')
    page    = int(request.args.get('page', 1))
    per     = 50
    conn    = get_conn()
    try:
        cur = conn.cursor()
        flt = date_filter('"Created Date"', start, end) + f' AND {PAY_IM_FILTER}'
        params = []
        if product:
            flt += " AND ____text = %s"
            params.append(product)
        if status == 'success':
            flt += f' AND {PAY_STATUS_SUCCESS}'
        elif status == 'cancel':
            flt += f' AND {PAY_STATUS_CANCEL}'
        elif status == 'wait':
            flt += f' AND {PAY_STATUS_WAIT}'
        if refund == 'true':
            flt += ' AND ______1_boolean = true'
        elif refund == 'false':
            flt += ' AND (______1_boolean = false OR ______1_boolean IS NULL)'

        cur.execute(f'SELECT COUNT(*) as c, COALESCE(SUM(CASE WHEN {PAY_STATUS_SUCCESS} THEN amount_number ELSE 0 END),0) as s FROM "{SCHEMA}"."custom$0__4" WHERE {flt}', params)
        agg = cur.fetchone()
        total, total_amount = agg['c'], float(agg['s'])

        cur.execute(f"""
            SELECT orderid_text AS order_id,
                   TO_CHAR({ts_to_kst('"Created Date"')}, 'YYYY-MM-DD HH24:MI:SS') AS created,
                   ____text AS product,
                   __1_text AS buyer_name,
                   ______text AS phone,
                   ____1_text AS method,
                   _____text AS status,
                   ____3_text AS amount,
                   code_string_text AS coupon,
                   ______1_boolean AS refund
            FROM "{SCHEMA}"."custom$0__4"
            WHERE {flt}
            ORDER BY "Created Date" DESC
            LIMIT {per} OFFSET {(page-1)*per}
        """, params)
        rows = []
        for r in cur.fetchall():
            amt = r['amount']
            try:
                amt_val = float(amt) if amt else None
            except Exception:
                amt_val = None
            rows.append({
                'order_id':   r['order_id'],
                'created':    r['created'],
                'product':    r['product'],
                'buyer_name': r['buyer_name'],
                'phone':      r['phone'],
                'method':     r['method'],
                'status':     r['status'],
                'amount':     amt_val,
                'coupon':     r['coupon'],
                'refund':     r['refund'],
            })
        return jsonify({'total': total, 'total_amount': total_amount, 'data': rows})
    finally:
        conn.close()


@app.route('/api/simulation/dist')
def api_sim_dist():
    start = request.args.get('start')
    end   = request.args.get('end')
    conn  = get_conn()
    try:
        cur = conn.cursor()
        flt = date_filter('"Created Date"', start, end)
        cur.execute(f'SELECT product_text AS label, COUNT(*) as cnt FROM "{SCHEMA}"."custom$0_nlt_159_interview_simulation_data" WHERE {flt} GROUP BY 1 ORDER BY 2 DESC')
        product = list(cur.fetchall())
        cur.execute(f'SELECT job_text AS label, COUNT(*) as cnt FROM "{SCHEMA}"."custom$0_nlt_159_interview_simulation_data" WHERE {flt} AND job_text IS NOT NULL AND job_text!=\'\' GROUP BY 1 ORDER BY 2 DESC LIMIT 10')
        job = list(cur.fetchall())
        return jsonify({'product': product, 'job': job})
    finally:
        conn.close()


@app.route('/api/simulation/list')
def api_sim_list():
    start   = request.args.get('start')
    end     = request.args.get('end')
    q       = request.args.get('q', '')
    product = request.args.get('product', '')
    page    = int(request.args.get('page', 1))
    per     = 50
    conn    = get_conn()
    try:
        cur = conn.cursor()
        flt = date_filter('s."Created Date"', start, end)
        params = []
        if q:
            flt += " AND (s.email_text ILIKE %s OR s.name_text ILIKE %s)"
            params.extend([f'%{q}%', f'%{q}%'])
        if product:
            flt += " AND s.product_text = %s"
            params.append(product)

        cur.execute(f"""
            SELECT COUNT(*) as c
            FROM "{SCHEMA}"."custom$0_nlt_159_interview_simulation_data" s
            WHERE {flt}
        """, params)
        total = cur.fetchone()['c']

        cur.execute(f"""
            SELECT s._id AS session_id,
                   TO_CHAR({ts_to_kst('s."Created Date"')}, 'YYYY-MM-DD HH24:MI:SS') AS created,
                   s.name_text AS name,
                   s.email_text AS email,
                   s.job_text AS job,
                   s.company_text AS company,
                   s.product_text AS product,
                   s.interview_mate_yn_boolean AS interview_mate,
                   COUNT(q._id) AS qa_count
            FROM "{SCHEMA}"."custom$0_nlt_159_interview_simulation_data" s
            LEFT JOIN "{SCHEMA}"."custom$0_nlt_162_chatgpt_raw" q ON s._id = q.unique_code_text
            WHERE {flt}
            GROUP BY s._id, s."Created Date", s.name_text, s.email_text,
                     s.job_text, s.company_text, s.product_text, s.interview_mate_yn_boolean
            ORDER BY s."Created Date" DESC
            LIMIT {per} OFFSET {(page-1)*per}
        """, params)
        rows = [{'session_id': r['session_id'], 'created': r['created'], 'name': r['name'],
                 'email': r['email'], 'job': r['job'], 'company': r['company'],
                 'product': r['product'], 'interview_mate': r['interview_mate'],
                 'qa_count': r['qa_count']} for r in cur.fetchall()]
        return jsonify({'total': total, 'data': rows})
    finally:
        conn.close()


@app.route('/api/session/qa')
def api_session_qa():
    session_id = request.args.get('session_id')
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT no__number AS no,
                   question_category_text AS category,
                   question_text AS question,
                   answer_text AS answer,
                   feedback_text AS feedback
            FROM "{SCHEMA}"."custom$0_nlt_162_chatgpt_raw"
            WHERE unique_code_text = %s
            ORDER BY no__number ASC NULLS LAST, "Created Date" ASC
        """, (session_id,))
        rows = [{'no': int(r['no']) if r['no'] else None, 'category': r['category'],
                 'question': r['question'], 'answer': r['answer'], 'feedback': r['feedback']}
                for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()


if __name__ == '__main__':
    print("면접 메이트 대시보드: http://localhost:5002")
    app.run(host='0.0.0.0', port=5002, debug=False)
