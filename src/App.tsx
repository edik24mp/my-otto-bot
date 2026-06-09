// OTTO Sales - Telegram Mini App
// React + Chart.js + Telegram WebApp

import { useEffect, useMemo, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import WebApp from '@twa-dev/sdk';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// --- Theme ---
const COLORS = {
  bg: '#FFFFFF',
  card: '#F8F9FA',
  card2: '#F3F4F6',
  border: '#E5E7EB',
  text: '#212529',
  subtle: '#6C757D',
  orange: '#FFA500',
  green: '#22c55e',
  red: '#ef4444',
  cyan: '#0ea5b7',
  gold: '#d49a00',
  mutedBar: '#94A3B8',
  progressBg: '#E5E7EB',
  ringTrack: '#E5E7EB',
};

// --- Types ---
type DailyFact = { payments: number; profitability_pct: number; est?: boolean };
type CurrentMonth = {
  year: number; month: number; month_name: string;
  plan_payments: number; plan_profitability_pct: number;
  fact_payments: number; fact_profitability_pct: number;
  pct_pay: number; pct_prof: number;
  lag_pay: number; lag_prof_pp: number;
  daily_needed: number; avg_daily: number;
  elapsed: number; remaining: number; total_days: number;
  is_behind: boolean; is_ahead: boolean;
  daily_facts: Record<string, DailyFact>;
};
type MonthlyPoint = { month: number; name: string; plan: number; fact: number; pct: number; prof: number };
type CurrentYear = {
  year: number; year_plan_payments: number; year_plan_profitability_pct: number;
  total_fact: number; avg_prof: number; pct_pay: number;
  monthly: MonthlyPoint[];
};
type YearSummary = { year: number; year_plan_payments: number; total_fact: number; pct_pay: number; avg_prof: number };
type ExtReport = {
  period: string;
  total_payments: number;
  new_payments: number;
  repeat_payments: number;
  new_count: number;
  repeat_count_report: number;
  repeat_count_fact?: number;
  new_avg_check: number;
  repeat_avg_check: number;
  total_profitability_pct: number;
  new_profitability_pct?: number;
  repeat_profitability_pct?: number;
};
type ApiResponse = {
  user_name: string;
  user_role: string;
  is_admin: boolean;
  current_month: CurrentMonth | null;
  current_year: CurrentYear | null;
  years: Record<string, YearSummary>;
  extended_reports: ExtReport[];
  error?: string;
};

const MN_FULL = ["","Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"];
const MN_SHORT = ["","Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"];

// --- Mock (для локальной разработки вне Telegram) ---
const MOCK_API: ApiResponse = {
  user_name: "Иван Менеджер",
  user_role: "manager",
  is_admin: true,
  current_month: {
    year: 2025, month: 6, month_name: "Июнь",
    plan_payments: 17000000,
    plan_profitability_pct: 20,
    fact_payments: 9250000,
    fact_profitability_pct: 18.9,
    pct_pay: 54.4,
    pct_prof: 94.5,
    lag_pay: -600000,
    lag_prof_pp: 1.1,
    daily_needed: 516667,
    avg_daily: 566667,
    elapsed: 15,
    remaining: 15,
    total_days: 30,
    is_behind: true,
    is_ahead: false,
    daily_facts: Object.fromEntries(
      Array.from({length:15}, (_,i) => [
        String(i+1),
        { payments: 480000 + Math.sin(i/2)*120000 + Math.random()*185000, profitability_pct: 17.5 + Math.random()*2.8 }
      ])
    ),
  },
  current_year: {
    year: 2025,
    year_plan_payments: 200000000,
    year_plan_profitability_pct: 20,
    total_fact: 96500000,
    avg_prof: 19.2,
    pct_pay: 48.25,
    monthly: [
      {month:1, name:"Январь", plan:15000000, fact:14500000, pct:96.7, prof:19.5},
      {month:2, name:"Февраль", plan:15000000, fact:16200000, pct:108, prof:20.8},
      {month:3, name:"Март", plan:16000000, fact:15300000, pct:95.6, prof:18.9},
      {month:4, name:"Апрель", plan:16500000, fact:17400000, pct:105.5, prof:19.7},
      {month:5, name:"Май", plan:17000000, fact:23850000, pct:140.3, prof:21.4},
      {month:6, name:"Июнь", plan:17000000, fact:9250000, pct:54.4, prof:18.9},
    ]
  },
  years: {
    "2022": { year: 2022, year_plan_payments: 150000000, total_fact: 142000000, pct_pay: 94.7, avg_prof: 17.8 },
    "2023": { year: 2023, year_plan_payments: 165000000, total_fact: 168500000, pct_pay: 102.1, avg_prof: 18.6 },
    "2024": { year: 2024, year_plan_payments: 180000000, total_fact: 192300000, pct_pay: 106.8, avg_prof: 19.4 },
    "2025": { year: 2025, year_plan_payments: 200000000, total_fact: 96500000, pct_pay: 48.25, avg_prof: 19.2 },
    "2026": { year: 2026, year_plan_payments: 220000000, total_fact: 0, pct_pay: 0, avg_prof: 0 },
  },
  extended_reports: [
    { period: "2025-01", total_payments: 14500000, new_payments: 4200000, repeat_payments: 10300000, new_count: 21, repeat_count_report: 108, new_avg_check: 200000, repeat_avg_check: 95370, total_profitability_pct: 19.5, new_profitability_pct: 18.2, repeat_profitability_pct: 20.0 },
    { period: "2025-02", total_payments: 16200000, new_payments: 5100000, repeat_payments: 11100000, new_count: 23, repeat_count_report: 119, new_avg_check: 221739, repeat_avg_check: 93277, total_profitability_pct: 20.8, new_profitability_pct: 19.4, repeat_profitability_pct: 21.5 },
    { period: "2025-03", total_payments: 15300000, new_payments: 4300000, repeat_payments: 11000000, new_count: 20, repeat_count_report: 114, new_avg_check: 215000, repeat_avg_check: 96491, total_profitability_pct: 18.9, new_profitability_pct: 17.5, repeat_profitability_pct: 19.4 },
    { period: "2025-04", total_payments: 17400000, new_payments: 6200000, repeat_payments: 11200000, new_count: 28, repeat_count_report: 123, new_avg_check: 221428, repeat_avg_check: 91057, total_profitability_pct: 19.7, new_profitability_pct: 18.0, repeat_profitability_pct: 20.6 },
    { period: "2025-05", total_payments: 23850000, new_payments: 9400000, repeat_payments: 14450000, new_count: 41, repeat_count_report: 138, new_avg_check: 229268, repeat_avg_check: 104710, total_profitability_pct: 21.4, new_profitability_pct: 20.7, repeat_profitability_pct: 21.9 },
  ]
};

// --- API ---
const API_URL = "https://sales-otto-bot.fly.dev/api/data"; // Замените на свой реальный API если другой

async function fetchApi(initData: string): Promise<ApiResponse> {
  // Если нет Telegram — отдаём мок
  if (!initData) throw new Error("no_initData");
  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ initData }),
  });
  if (!res.ok) {
    const t = await res.text().catch(()=>"");
    throw new Error(t || `HTTP ${res.status}`);
  }
  return res.json();
}

// --- helpers ---
const fmtRub = (n: number) => (n||0).toLocaleString('ru-RU', { maximumFractionDigits: 0 });
const fmtPct = (n: number, d = 1) => (n||0).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d });

function RingPct({ value, size = 72 }: { value: number; size?: number }) {
  const r = 28;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(110, value));
  const off = c - c * Math.min(v,100) / 100;
  const col = v >= 100 ? COLORS.green : v >= 78 ? COLORS.orange : COLORS.red;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 72 72" className="-rotate-90">
        <circle cx="36" cy="36" r={r} fill="none" stroke={COLORS.ringTrack} strokeWidth="7" />
        <circle cx="36" cy="36" r={r} fill="none" stroke={col} strokeWidth="7"
          strokeDasharray={c} strokeDashoffset={off}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset .7s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[15px] font-[800] tracking-tight" style={{ color: col }}>{fmtPct(v,0)}%</span>
      </div>
    </div>
  )
}

// --- Chart defaults (light) ---
const darkTicks = { color: COLORS.subtle, font: { family: 'Manrope, Inter, ui-sans-serif', size: 11 } };
const darkGrid = { color: 'rgba(108,117,125,0.2)' };
const darkLegend = {
  labels: { color: COLORS.text, font: { family: 'Manrope, Inter, ui-sans-serif', size: 12 }, boxWidth: 14, usePointStyle: true }
};

// --- Month Dashboard ---
function MonthDashboard({ m }: { m: CurrentMonth }) {
  const daysArr = Object.keys(m.daily_facts).map(Number).sort((a,b)=>a-b);
  const dailyPayments = daysArr.map(d => m.daily_facts[d].payments);
  
  // cumulative
  let cum = 0;
  const cumFact = dailyPayments.map(v => cum += v);
  const cumPlan = daysArr.map(d => m.plan_payments * d / m.total_days);

  const dailyBarData = {
    labels: daysArr.map(String),
    datasets: [{
      label: 'Оплаты / день',
      data: dailyPayments,
      backgroundColor: dailyPayments.map(v => v >= m.avg_daily ? COLORS.green : COLORS.red),
      borderRadius: 6,
      barPercentage: 0.72,
    }]
  };

  const cumLineData = {
    labels: daysArr.map(String),
    datasets: [
      {
        label: 'План',
        data: cumPlan,
        borderDash: [6,5],
        borderColor: COLORS.cyan,
        backgroundColor: 'transparent',
        tension: 0.32,
        pointRadius: 0,
        borderWidth: 2,
      },
      {
        label: 'Факт',
        data: cumFact,
        borderColor: m.is_ahead ? COLORS.green : m.is_behind ? COLORS.red : COLORS.orange,
        backgroundColor: (m.is_ahead ? COLORS.green : m.is_behind ? COLORS.red : COLORS.orange) + '2a',
        fill: true,
        tension: 0.32,
        pointRadius: 2,
        pointHoverRadius: 4,
        borderWidth: 2.7,
      },
    ]
  };

  const payCol = m.is_ahead ? COLORS.green : m.is_behind ? COLORS.red : COLORS.orange;
  const profCol = m.lag_prof_pp <= 0 ? COLORS.green : COLORS.red;

  const statusColor = m.is_ahead ? COLORS.green : m.is_behind ? COLORS.red : COLORS.cyan;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[27px] font-[800] tracking-tight">{m.month_name} {m.year}</div>
          <div className="text-[13px] font-[700]" style={{ color: statusColor }}>
            {m.is_ahead ? '🚀 ПЕРЕВЫПОЛНЕНИЕ' : m.is_behind ? '❗ ОТСТАВАНИЕ' : '📊 В НОРМЕ'}
          </div>
        </div>
        <RingPct value={m.pct_pay} />
      </div>

      {/* Оплаты */}
      <div className="rounded-[22px] px-4 py-4" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
        <div className="text-[12px] font-[700] tracking-wide" style={{ color: COLORS.subtle }}>💰 ОПЛАТЫ</div>
        <div className="mt-2 flex items-baseline flex-wrap gap-x-2">
          <div className="text-[26px] font-[800] tracking-tight">{fmtRub(m.fact_payments)} ₽</div>
          <div className="text-[13.7px] font-[700]" style={{ color: COLORS.subtle }}>/ {fmtRub(m.plan_payments)} ₽</div>
        </div>
        <div className="mt-3 h-[11px] rounded-full overflow-hidden relative" style={{ background: COLORS.progressBg }}>
          <div className="absolute inset-y-0 left-0 rounded-full transition-all" style={{ width: Math.min(m.pct_pay,100)+'% ', background: payCol }} />
        </div>
        <div className="mt-1.5 text-[12.5px] font-[700]" style={{ color: payCol }}>{fmtPct(m.pct_pay)}% выполнено</div>
      </div>

      {/* Рентабельность */}
      <div className="rounded-[22px] px-4 py-4" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
        <div className="text-[12px] font-[700] tracking-wide" style={{ color: COLORS.subtle }}>📈 РЕНТАБЕЛЬНОСТЬ</div>
        <div className="mt-2 flex items-baseline gap-2">
          <div className="text-[26px] font-[800] tracking-tight">{fmtPct(m.fact_profitability_pct)}%</div>
          <div className="text-[13.7px] font-[700]" style={{ color: COLORS.subtle }}>/ {fmtPct(m.plan_profitability_pct)}%</div>
        </div>
        <div className="mt-3 h-[11px] rounded-full overflow-hidden relative" style={{ background: COLORS.progressBg }}>
          <div className="absolute inset-y-0 left-0 rounded-full transition-all" style={{ width: Math.min(m.pct_prof,100)+'% ', background: profCol }} />
        </div>
        <div className="mt-1.5 text-[12.5px] font-[700]" style={{ color: profCol }}>
          {m.pct_prof.toFixed(1)}% от плана
          {m.lag_prof_pp !== 0 && <span style={{ color: COLORS.subtle }}> · {m.lag_prof_pp > 0 ? '−' : '+'}{Math.abs(m.lag_prof_pp).toFixed(1)} п.п.</span>}
        </div>
      </div>

      {/* Метрики */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-[18px] px-3.5 py-3" style={{ background: COLORS.card }}>
          <div className="text-[11px] font-[700]" style={{ color: COLORS.subtle }}>{m.is_behind ? '❗ Отставание' : '🚀 Опережение'}</div>
          <div className="text-[17px] font-[800] mt-1" style={{ color: m.is_behind ? COLORS.red : COLORS.green }}>{fmtRub(Math.abs(m.lag_pay))} ₽</div>
        </div>
        <div className="rounded-[18px] px-3.5 py-3" style={{ background: COLORS.card }}>
          <div className="text-[11px] font-[700]" style={{ color: COLORS.subtle }}>⚡ Нужно в день</div>
          <div className="text-[17px] font-[800] mt-1" style={{ color: COLORS.orange }}>{fmtRub(m.daily_needed)} ₽</div>
        </div>
        <div className="rounded-[18px] px-3.5 py-3" style={{ background: COLORS.card }}>
          <div className="text-[11px] font-[700]" style={{ color: COLORS.subtle }}>📅 День</div>
          <div className="text-[17px] font-[800] mt-1">{m.elapsed} из {m.total_days}<span className="text-[12px] font-[700]" style={{color:COLORS.subtle}}> · ост. {m.remaining}</span></div>
        </div>
        <div className="rounded-[18px] px-3.5 py-3" style={{ background: COLORS.card }}>
          <div className="text-[11px] font-[700]" style={{ color: COLORS.subtle }}>📊 Норма/день</div>
          <div className="text-[17px] font-[800] mt-1" style={{ color: COLORS.cyan }}>{fmtRub(m.avg_daily)} ₽</div>
        </div>
      </div>

      {/* График накопительный */}
      <div className="rounded-[22px] p-4" style={{ background: COLORS.card }}>
        <div className="font-[800] text-[15px] mb-2">Накопительная динамика</div>
        <div className="h-[230px]">
          <Line
            data={cumLineData}
            options={{
              responsive: true, maintainAspectRatio: false,
              plugins: { legend: { ...darkLegend } },
              scales: {
                x: { ticks: darkTicks, grid: darkGrid },
                y: { ticks: { ...darkTicks, callback: (v)=> (+v/1e6).toFixed(1)+'M'}, grid: darkGrid }
              },
              interaction: { mode: 'index', intersect: false }
            }}
          />
        </div>
      </div>

      {/* Ежедневные */}
      <div className="rounded-[22px] p-4" style={{ background: COLORS.card }}>
        <div className="font-[800] text-[15px] mb-2">Ежедневные оплаты</div>
        <div className="h-[198px]">
          <Bar
            data={dailyBarData}
            options={{
              responsive: true, maintainAspectRatio: false,
              plugins: { legend: { display: false } },
              scales: {
                x: { ticks: darkTicks, grid: { display: false } },
                y: { ticks: { ...darkTicks, callback: (v)=> (+v/1000).toFixed(0)+'k' }, grid: darkGrid }
              }
            }}
          />
        </div>
        <div className="text-[11px] mt-1.5" style={{ color: COLORS.subtle }}>Норма: {fmtRub(m.avg_daily)} ₽/день · Зелёные столбцы ≥ нормы</div>
      </div>
    </div>
  );
}

// --- Year Dashboard ---
function YearDashboard({ y }: { y: CurrentYear }) {
  const labels = y.monthly.map(m => MN_SHORT[m.month]);
  const planData = y.monthly.map(m => m.plan);
  const factData = y.monthly.map(m => m.fact);
  const profData = y.monthly.map(m => m.prof);

  const barYear = {
    labels,
    datasets: [
      { label: 'План', data: planData, backgroundColor: COLORS.mutedBar, borderRadius: 7 },
      { label: 'Факт', data: factData, backgroundColor: COLORS.orange, borderRadius: 7 },
    ]
  };
  const profYear = {
    labels,
    datasets: [{
      label: 'Рентабельность %',
      data: profData,
      backgroundColor: profData.map(v => v >= y.year_plan_profitability_pct ? COLORS.green : COLORS.red),
      borderRadius: 7,
    }]
  };

  return (
    <div className="space-y-4">
      <div>
        <div className="text-[27px] font-[800] tracking-tight">Год {y.year}</div>
        <div className="text-[13.5px] font-[700]" style={{ color: COLORS.subtle }}>
          {fmtRub(y.total_fact)} / {fmtRub(y.year_plan_payments)} ₽ · {fmtPct(y.pct_pay)}%
        </div>
      </div>

      <div className="rounded-[22px] p-4" style={{ background: COLORS.card }}>
        <div className="font-[800] text-[15px] mb-2">Помесячное выполнение</div>
        <div className="h-[236px]">
          <Bar data={barYear} options={{
            responsive:true, maintainAspectRatio:false,
            plugins:{ legend:{ ...darkLegend }},
            scales:{ x:{ ticks: darkTicks, grid:{ display:false }}, y:{ ticks:{ ...darkTicks, callback: (v)=> (+v/1e6).toFixed(0)+'M'}, grid: darkGrid }}
          }}/>
        </div>
      </div>

      <div className="rounded-[22px] p-4" style={{ background: COLORS.card }}>
        <div className="flex items-center justify-between mb-2">
          <div className="font-[800] text-[15px]">Рентабельность по месяцам</div>
          <div className="text-[12px] font-[700]" style={{ color: COLORS.gold }}>План {fmtPct(y.year_plan_profitability_pct)}%</div>
        </div>
        <div className="h-[198px]">
          <Bar data={profYear} options={{
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { ticks: darkTicks, grid:{ display:false } }, y: { ticks: darkTicks, grid: darkGrid } }
          }} />
        </div>
      </div>

      <div className="rounded-[20px] overflow-hidden" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
        <div className="px-4 py-3 font-[700] text-[13.5px]" style={{ color: COLORS.subtle }}>Детализация</div>
        <div className="px-3 pb-3 overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead style={{ color: COLORS.subtle }}>
              <tr style={{ borderBottom: `1px solid ${COLORS.border}`}}>
                <th className="text-left py-2 font-[700] px-2">Мес</th>
                <th className="text-right py-2 font-[700] px-2">План</th>
                <th className="text-right py-2 font-[700] px-2">Факт</th>
                <th className="text-right py-2 font-[700] px-2">%</th>
                <th className="text-right py-2 font-[700] px-2">Рент</th>
              </tr>
            </thead>
            <tbody>
              {y.monthly.map(mm => (
                <tr key={mm.month} className="last:border-0" style={{ borderBottom: `1px solid ${COLORS.border}`}}>
                  <td className="py-2 px-2 font-[700]">{MN_SHORT[mm.month]}</td>
                  <td className="py-2 px-2 text-right" style={{ color: COLORS.subtle }}>{fmtRub(mm.plan)}</td>
                  <td className="py-2 px-2 text-right font-[700]">{fmtRub(mm.fact)}</td>
                  <td className="py-2 px-2 text-right font-[800]" style={{ color: mm.pct >= 100 ? COLORS.green : mm.pct >= 78 ? COLORS.orange : COLORS.red }}>{fmtPct(mm.pct,1)}%</td>
                  <td className="py-2 px-2 text-right font-[700]">{fmtPct(mm.prof,1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// --- Multi Year ---
function MultiYear({ years }: { years: Record<string, YearSummary> }) {
  const list = Object.values(years).filter(y => y.year_plan_payments > 0 || y.total_fact > 0).sort((a,b)=>a.year-b.year);
  const labels = list.map(y => String(y.year));
  const planM = list.map(y => y.year_plan_payments/1e6);
  const factM = list.map(y => y.total_fact/1e6);

  const barData = {
    labels,
    datasets: [
      { label: 'План (млн)', data: planM, backgroundColor: COLORS.mutedBar, borderRadius: 7 },
      { label: 'Факт (млн)', data: factM, backgroundColor: COLORS.orange, borderRadius: 7 },
    ]
  };

  return (
    <div className="space-y-4">
      <div className="text-[27px] font-[800] tracking-tight">Динамика {list[0]?.year}–{list[list.length-1]?.year}</div>

      <div className="rounded-[22px] p-4" style={{ background: COLORS.card }}>
        <div className="h-[254px]">
          <Bar data={barData} options={{
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { ...darkLegend } },
            scales: { 
              x: { ticks: { ...darkTicks, font: { ...darkTicks.font, size: 12 }}, grid:{ display:false }},
              y: { ticks: { ...darkTicks, callback: v => v+'M' }, grid: darkGrid }
            }
          }} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {list.map(y => (
          <div key={y.year} className="rounded-[18px] px-3.5 py-3" style={{ background: COLORS.card }}>
            <div className="text-[11px] font-[800]" style={{ color: COLORS.subtle }}>{y.year}</div>
            <div className="text-[16px] font-[800] mt-1">{fmtPct(y.pct_pay,1)}%</div>
            <div className="text-[12px] font-[700]" style={{ color: COLORS.subtle }}>{fmtRub(y.total_fact/1e6)} млн</div>
            <div className="text-[12px] font-[700]" style={{ color: COLORS.cyan }}>рент {fmtPct(y.avg_prof,1)}%</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Extended Report ---
function ExtendedReportView({ reports }: { reports: ExtReport[] }) {
  const [idx, setIdx] = useState(reports.length - 1);
  const r = reports[idx];
  if (!r) return <div className="text-center py-14" style={{ color: COLORS.subtle }}>Нет расширенных отчётов</div>;
  const prev = idx > 0 ? reports[idx - 1] : null;
  const delta = (a:number, b:number) => a - b;
  const dColor = (v:number) => v > 0 ? COLORS.green : v < 0 ? COLORS.red : COLORS.subtle;
  const [y,m] = r.period.split('-').map(Number);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-[24px] font-[800]">{MN_FULL[m]} {y}</div>
        <div className="flex gap-1.5">
          <button disabled={idx===0} onClick={()=>setIdx(i=>Math.max(0,i-1))} className="px-3 py-2 rounded-xl text-[13px] font-[800] disabled:opacity-35" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`}}>‹</button>
          <button disabled={idx===reports.length-1} onClick={()=>setIdx(i=>Math.min(reports.length-1,i+1))} className="px-3 py-2 rounded-xl text-[13px] font-[800] disabled:opacity-35" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}`}}>›</button>
        </div>
      </div>

      <div className="rounded-[22px] px-4 py-4" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
        <div className="text-[12px] font-[700]" style={{ color: COLORS.subtle }}>ИТОГО ОПЛАТЫ</div>
        <div className="text-[28px] font-[900] mt-1">{fmtRub(r.total_payments)} ₽</div>
        <div className="text-[13px] font-[700] mt-1" style={{ color: COLORS.cyan }}>Рентабельность {fmtPct(r.total_profitability_pct)}%</div>
        {prev && (
          <div className="text-[12px] font-[700] mt-1" style={{ color: dColor(r.total_payments - prev.total_payments)}}>
            {r.total_payments >= prev.total_payments ? '▲' : '▼'} {fmtPct(Math.abs((r.total_payments/prev.total_payments-1)*100))}% к пред. мес
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-[20px] px-4 py-4" style={{ background: COLORS.card2, border: `1px solid ${COLORS.border}` }}>
          <div className="text-[12px] font-[700]" style={{ color: COLORS.subtle }}>👤 Новые</div>
          <div className="text-[19px] font-[800] mt-1">{fmtRub(r.new_payments)} ₽</div>
          <div className="text-[12.5px] mt-2" style={{ color: COLORS.subtle }}>{r.new_count} шт · ср. чек {fmtRub(r.new_avg_check)} ₽</div>
          {r.new_profitability_pct !== undefined && <div className="text-[12.5px] font-[700] mt-1" style={{ color: COLORS.gold }}>рент {fmtPct(r.new_profitability_pct)}%</div>}
          {prev && <div className="text-[11.7px] font-[700] mt-1" style={{ color: dColor(delta(r.new_payments, prev.new_payments))}}>{delta(r.new_payments, prev.new_payments) >= 0 ? '+' : ''}{fmtRub(delta(r.new_payments, prev.new_payments))} ₽</div>}
        </div>
        <div className="rounded-[20px] px-4 py-4" style={{ background: COLORS.card2, border: `1px solid ${COLORS.border}` }}>
          <div className="text-[12px] font-[700]" style={{ color: COLORS.subtle }}>🔄 Постоянные</div>
          <div className="text-[19px] font-[800] mt-1">{fmtRub(r.repeat_payments)} ₽</div>
          <div className="text-[12.5px] mt-2" style={{ color: COLORS.subtle }}>{r.repeat_count_report} шт · ср. чек {fmtRub(r.repeat_avg_check)} ₽</div>
          {r.repeat_profitability_pct !== undefined && <div className="text-[12.5px] font-[700] mt-1" style={{ color: COLORS.gold }}>рент {fmtPct(r.repeat_profitability_pct)}%</div>}
          {prev && <div className="text-[11.7px] font-[700] mt-1" style={{ color: dColor(delta(r.repeat_payments, prev.repeat_payments))}}>{delta(r.repeat_payments, prev.repeat_payments) >= 0 ? '+' : ''}{fmtRub(delta(r.repeat_payments, prev.repeat_payments))} ₽</div>}
        </div>
      </div>

      <div className="rounded-[20px] overflow-hidden" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
        <table className="w-full text-[13.5px]">
          <tbody>
            {[
              ["Итого оплат", r.total_payments, prev?.total_payments],
              ["Новые, ₽", r.new_payments, prev?.new_payments],
              ["Постоянные, ₽", r.repeat_payments, prev?.repeat_payments],
              ["Новых, шт", r.new_count, prev?.new_count, true],
              ["Пост., шт", r.repeat_count_report, prev?.repeat_count_report, true],
              ["Ср. чек новые", r.new_avg_check, prev?.new_avg_check],
              ["Ср. чек пост.", r.repeat_avg_check, prev?.repeat_avg_check],
            ].map(([label, cur, prv, intOnly]) => {
              const c = cur as number; const p = prv as number | undefined;
              const diff = p ? c - p : null;
              const pct = p && p !== 0 ? (c / p - 1) * 100 : null;
              return (
                <tr key={String(label)} className="last:border-0" style={{ borderBottom: `1px solid ${COLORS.border}`}}>
                  <td className="py-[11px] px-4 font-[600]" style={{ color:COLORS.subtle}}>{label}</td>
                  <td className="py-[11px] px-4 text-right font-[800]">{intOnly ? c : fmtRub(c) + (String(label).includes('шт') ? '' : ' ₽')}</td>
                  <td className="py-[11px] px-4 text-right text-[12px] font-[700] w-[94px]" style={{ color: diff===null?COLORS.subtle: dColor(diff) }}>
                    {diff===null ? '—' : `${diff>0?'+':''}${intOnly ? diff : fmtPct(pct!,1)+'%'} `}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="text-center text-[11.5px]" style={{ color: COLORS.subtle }}>Динамика: зелёным — прирост, красным — спад</div>
    </div>
  );
}

// --- Premium Calculator ---
function PremiumCalculator(props: { userName:string, reports: ExtReport[], cy: CurrentYear | null }) {
  const PREMIUM_START_YEAR = 2025, PREMIUM_START_MONTH = 9;
  const monthOptions: { y:number; m:number; label:string }[] = [];
  for(let y=2025; y<=2026; y++){
    for(let m = (y===PREMIUM_START_YEAR?PREMIUM_START_MONTH:1); m<=12; m++){
      monthOptions.push({ y, m, label: `${MN_FULL[m]} ${y}`});
    }
  }
  monthOptions.reverse();
  const [sel, setSel] = useState(monthOptions[0] || {y:2025,m:9,label:''});
  useEffect(()=>{ (window as any)._pmHack = (y:number,m:number)=> setSel({y,m,label:`${MN_FULL[m]} ${y}`}); },[]);
  const mp = props.cy?.year===sel.y ? props.cy.monthly.find(mm => mm.month === sel.m) : null;
  const factPay = mp?.fact || 0;
  const factProf = mp?.prof || 0;
  const premium = factPay * (factProf/100) * 0.01;
  const extForMonth = props.reports.find(r => r.period === `${sel.y}-${String(sel.m).padStart(2,'0')}`);
  const hasData = factPay > 0 || !!extForMonth;

  return (
    <div className="space-y-4">
      <div>
        <div className="text-[22px] font-[800]">💰 Моя премия</div>
        <div className="text-[13.5px] font-[600]" style={{ color: COLORS.subtle }}>{props.userName}</div>
      </div>

      <div className="rounded-[18px] px-3 py-3" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
        <div className="text-[11.5px] font-[700] mb-2" style={{ color: COLORS.subtle }}>Выберите месяц</div>
        <div className="grid grid-cols-2 gap-2 max-h-[270px] overflow-auto pr-1">
          {monthOptions.map(o => (
            <button key={o.label}
              onClick={()=>setSel(o)}
              className="text-left px-3 py-2.5 rounded-[13px] text-[13.2px] font-[700] transition"
              style={{ background: (o.y===sel.y && o.m===sel.m) ? COLORS.orange : COLORS.card2, color: (o.y===sel.y && o.m===sel.m) ? '#fff' : COLORS.text, border: `1px solid ${o.y===sel.y && o.m===sel.m ? COLORS.orange : COLORS.border}` }}
              >
              {o.label}
            </button>
          ))}
        </div>
        <div className="text-[11px] mt-2" style={{color:COLORS.subtle}}>Премия доступна с сентября 2025</div>
      </div>

      <div className="rounded-[22px] px-4 py-5 text-center" style={{ background: COLORS.card, border:`1px solid ${COLORS.border}`}}>
        <div className="text-[12px] font-[800]" style={{ color: COLORS.subtle }}>{MN_FULL[sel.m]} {sel.y}</div>
        {!hasData ? (
          <div className="mt-3 text-[15px] font-[700]" style={{ color: COLORS.subtle }}>Нет данных за этот месяц</div>
        ) : (
          <>
            <div className="mt-2 text-[36px] font-[900] tracking-tight" style={{ color: COLORS.orange }}>{fmtRub(premium)} ₽</div>
            <div className="text-[12.5px] font-[700] mt-1" style={{ color: COLORS.subtle }}>
              {fmtRub(factPay)} ₽ × {fmtPct(factProf)}% × 1%
            </div>
            <div className="text-[11.5px] mt-3" style={{ color: COLORS.subtle }}>Формула: факт оплат × рентабельность / 100 × 1%</div>
          </>
        )}
      </div>

      {extForMonth && (
        <div className="rounded-[18px] px-3.5 py-3" style={{ background: COLORS.card }}>
          <div className="text-[12.5px] font-[700]" style={{ color: COLORS.subtle }}>Расширенный отчёт</div>
          <div className="text-[13.5px] font-[700] mt-1">Оплаты: {fmtRub(extForMonth.total_payments)} ₽ · Рент: {fmtPct(extForMonth.total_profitability_pct)}%</div>
        </div>
      )}

      <div className="text-[12px] px-1" style={{ color: COLORS.subtle }}>
        Премия менеджера = факт оплат × факт рентабельность × 1%
      </div>
    </div>
  );
}

// --- Main App ---
export default function App() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<'month'|'year'|'multi'|'report'|'premium'>('month');

  useEffect(() => {
    const wa = (window as any).Telegram?.WebApp ?? WebApp;
    try {
      wa.ready();
      wa.expand();
      wa.setHeaderColor('#FFFFFF');
      wa.setBackgroundColor('#FFFFFF');
      wa.MainButton.hide();
    } catch {}
    
    const initData = wa?.initData || '';
    const isTg = !!initData;

    const load = async () => {
      setLoading(true);
      try {
        let resp: ApiResponse;
        if (isTg) {
          resp = await fetchApi(initData);
        } else {
          // Dev mode outside Telegram
          await new Promise(r => setTimeout(r, 620));
          resp = MOCK_API;
        }
        if ((resp as any).error) throw new Error((resp as any).error);
        setData(resp);
        setErr(null);
      } catch (e:any) {
        console.error(e);
        if (!isTg) {
          setData(MOCK_API);
          setErr(null);
        } else {
          setErr(e.message || 'Ошибка загрузки');
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Telegram BackButton
  useEffect(() => {
    const wa = (window as any).Telegram?.WebApp ?? WebApp;
    try {
      if (tab !== 'month' && wa?.BackButton) {
        wa.BackButton.show();
        const onBack = () => setTab('month');
        wa.BackButton.onClick(onBack);
        return () => { try { wa.BackButton.offClick(onBack); wa.BackButton.hide(); } catch {} };
      } else {
        wa?.BackButton?.hide();
      }
    } catch {}
  }, [tab]);

  const tabs = useMemo(() => {
    const base = [
      { id: 'month', label: 'Месяц', icon: '📊' },
      { id: 'year', label: 'Год', icon: '📈' },
      { id: 'multi', label: 'Динам.', icon: '📉' },
      { id: 'report', label: 'Отчёт', icon: '📋' },
    ] as { id: string; label: string; icon: string }[];
    if (data?.user_role === 'manager') base.push({ id: 'premium', label: 'Премия', icon: '💰' });
    return base;
  }, [data?.user_role]);

  return (
    <div style={{ background: COLORS.bg, color: COLORS.text, minHeight: '100dvh', fontFamily: 'Manrope, Inter, ui-sans-serif' }}>
      <style>{`
        *{ -webkit-tap-highlight-color: transparent }
        ::-webkit-scrollbar{ width:6px; height:6px }
        ::-webkit-scrollbar-thumb{ background:#d1d5db; border-radius:4px }
      `}</style>

      <div className="max-w-[680px] mx-auto px-[16px] pt-[14px] pb-[100px]" style={{ paddingTop: 'calc(14px + var(--tg-content-safe-area-inset-top,0px))'}}>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-[13px] flex items-center justify-center font-[900] text-[17px]" style={{ background: COLORS.orange, color: '#fff' }}>O</div>
            <div>
              <div className="text-[15.5px] font-[800] tracking-tight">OTTO Sales</div>
              <div className="text-[11.5px] font-[600]" style={{ color: COLORS.subtle }}>{data?.user_name || 'Загрузка…'}</div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[11px] font-[700]" style={{color:COLORS.subtle}}>{data?.user_role ? ({manager:'Менеджер', marketer:'Маркетолог', director:'Директор', founder:'Учредитель'}[data.user_role] || data.user_role) : '—'}</div>
            {data?.is_admin && <div className="text-[11px] font-[800]" style={{color:COLORS.gold}}>👑 админ</div>}
          </div>
        </div>

        {loading && (
          <div className="py-28 text-center">
            <div className="mx-auto w-10 h-10 rounded-full border-[3px] animate-spin" style={{ borderColor: COLORS.border, borderTopColor: COLORS.orange }} />
            <div className="mt-4 text-[13.5px] font-[600]" style={{ color: COLORS.subtle }}>Загружаем данные…</div>
          </div>
        )}

        {err && !loading && (
          <div className="rounded-[20px] px-4 py-6 text-center" style={{ background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
            <div className="text-[20px] font-[800]">{err === 'not_registered' ? '👋 Сначала запусти бота' : 'Ошибка'}</div>
            <div className="text-[13.5px] mt-2" style={{ color: COLORS.subtle }}>
              {err === 'not_registered' ? 'Открой @your_bot в Telegram и нажми /start' : err}
              {err === 'no_initData' && ' — открой приложение через кнопку в Telegram-боте'}
            </div>
            <button onClick={()=>location.reload()} className="mt-4 px-4 py-2 rounded-xl font-[700] text-[13.5px]" style={{ background: COLORS.orange, color: '#fff' }}>Обновить</button>
            <div className="mt-3 text-[11.5px]" style={{ color: COLORS.subtle }}>API: {API_URL}</div>
          </div>
        )}

        {!loading && !err && data && (
          <>
            {tab === 'month' && (data.current_month
              ? <MonthDashboard m={data.current_month} />
              : <div className="rounded-[18px] px-4 py-10 text-center" style={{ background: COLORS.card, color: COLORS.subtle }}>Нет данных по текущему месяцу</div>
            )}
            {tab === 'year' && (data.current_year
              ? <YearDashboard y={data.current_year} />
              : <div className="rounded-[18px] px-4 py-10 text-center" style={{ background: COLORS.card, color: COLORS.subtle }}>Годовой план не установлен</div>
            )}
            {tab === 'multi' && <MultiYear years={data.years} />}
            {tab === 'report' && <ExtendedReportView reports={data.extended_reports} />}
            {tab === 'premium' && data.user_role === 'manager' && <PremiumCalculator userName={data.user_name} reports={data.extended_reports} cy={data.current_year} />}
          </>
        )}
      </div>

      {/* Bottom Tabs */}
      <div className="fixed bottom-0 inset-x-0 z-40" style={{
        background: 'rgba(255,255,255,0.96)',
        backdropFilter: 'blur(14px)',
        borderTop: `1px solid ${COLORS.border}`
      }}>
        <div className="max-w-[680px] mx-auto px-3 pt-2 pb-[calc(10px+var(--tg-content-safe-area-inset-bottom,env(safe-area-inset-bottom)))] flex justify-around gap-1">
          {tabs.map(t => {
            const active = tab === t.id;
            return (
              <button key={t.id}
                onClick={()=>setTab(t.id as any)}
                className="flex-1 flex flex-col items-center py-[8px] rounded-[14px] transition"
                style={{ background: active ? COLORS.card2 : 'transparent' }}
              >
                <span className="text-[18px] leading-none">{t.icon}</span>
                <span className="text-[11px] font-[700] mt-1" style={{ color: active ? COLORS.orange : COLORS.subtle }}>{t.label}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}