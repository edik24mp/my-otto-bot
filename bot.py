#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM BOT - КОНТРОЛЬ ПЛАНА ПРОДАЖ v3.9 (поддержка userId в API, исправлена сводка)
pip install "python-telegram-bot[job-queue]>=21.0" matplotlib numpy aiohttp supabase
"""
import json, os, logging, asyncio, re
from datetime import datetime, timedelta
from calendar import monthrange
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, MenuButtonWebApp
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters)
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO

# Supabase
from supabase import create_client, Client

# ====== НАСТРОЙКИ ======
BOT_TOKEN = "8996749929:AAF5Li8zgytNCGoy3QDmDRol0nE6-83KleE"
ADMIN_USER_ID = 307720204
SECRET_CODE = "Ваня мудила"
PREMIUM_START_YEAR = 2025
PREMIUM_START_MONTH = 9

SUPABASE_URL = "https://fqoigjvvtvayeobxzaui.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZxb2lnanZ2dHZheWVvYnh6YXVpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MTI3NDM0NSwiZXhwIjoyMDk2ODUwMzQ1fQ.n_aESJHrD4ZEOdyyxOP1fpvAERSarpjYF-wJrfTnlOQ"

WEBAPP_URL = "https://edik24mp.github.io/my-otto-frontend/"
API_PORT = 8443

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

# Состояния
(
    REG_NAME, REG_POSITION,
    SET_PLAN_PAY, SET_PLAN_PROF,
    SET_YPLAN_YEAR, SET_YPLAN_PAY, SET_YPLAN_PROF,
    SET_FACT_CUM, SET_FACT_PROF,
    RETRO_SEL_YEAR, RETRO_SEL_MONTH, RETRO_SEL_FIELD, RETRO_VALUE,
    EXT_SEL_YEAR, EXT_SEL_MONTH,
    EXT_NEW_PAY, EXT_REP_PAY, EXT_NEW_CNT, EXT_RCR, EXT_RCF, EXT_NPROF, EXT_RPROF,
    BAN_SEL, BAN_CONF, ADM_SEL, ADM_CONF,
) = range(26)

MN = {1:"Январь",2:"Февраль",3:"Март",4:"Апрель",5:"Май",6:"Июнь",
      7:"Июль",8:"Август",9:"Сентябрь",10:"Октябрь",11:"Ноябрь",12:"Декабрь"}
POS = {"manager":"Менеджер","marketer":"Маркетолог","director":"Коммерческий директор","founder":"Учредитель"}

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====== USERS (Supabase) ======
def get_user(uid: int) -> dict | None:
    res = supabase.table("users").select("*").eq("user_id", uid).execute()
    return res.data[0] if res.data else None

def is_reg(uid: int) -> bool:
    u = get_user(uid)
    return u is not None and not u.get("is_banned", False)

def is_admin(uid: int) -> bool:
    if uid == ADMIN_USER_ID:
        return True
    res = supabase.table("users").select("is_admin").eq("user_id", uid).execute()
    return res.data[0].get("is_admin", False) if res.data else False

def is_banned(uid: int) -> bool:
    u = get_user(uid)
    return u is not None and u.get("is_banned", False)

def dname(uid: int) -> str:
    u = get_user(uid)
    return u.get("name", "Пользователь") if u else "Пользователь"

def reg_user(uid: int, name: str, pos: str):
    if get_user(uid):
        return
    supabase.table("users").insert({
        "user_id": uid,
        "name": name,
        "position": pos,
        "is_admin": (uid == ADMIN_USER_ID),
        "is_banned": False,
        "registered_at": datetime.now().isoformat()
    }).execute()

def ban_u(uid: int):
    supabase.table("users").update({"is_banned": True}).eq("user_id", uid).execute()

def promote(uid: int):
    supabase.table("users").update({"is_admin": True}).eq("user_id", uid).execute()

# ====== DATA (Supabase) ======
def get_year_plan(year: int) -> dict:
    res = supabase.table("year_plans").select("*").eq("year", year).execute()
    if res.data:
        return {"year_plan_payments": res.data[0]["plan_payments"], "year_plan_profitability_pct": res.data[0]["plan_profitability"]}
    return {"year_plan_payments": 0, "year_plan_profitability_pct": 0}

def set_year_plan(year: int, payments: float, profitability: float):
    supabase.table("year_plans").upsert({
        "year": year,
        "plan_payments": int(payments),
        "plan_profitability": profitability
    }).execute()

def get_month_data(year: int, month: int) -> dict:
    res = supabase.table("month_data").select("*").eq("year", year).eq("month", month).execute()
    if res.data:
        row = res.data[0]
        return {
            "plan_payments": row["plan_payments"],
            "plan_profitability_pct": row["plan_profitability"],
            "result_payments": row.get("result_payments"),
            "result_profitability_pct": row.get("result_profitability"),
            "cumulative_entries": row.get("cumulative_entries", [])
        }
    return {
        "plan_payments": 0,
        "plan_profitability_pct": 0,
        "result_payments": None,
        "result_profitability_pct": None,
        "cumulative_entries": []
    }

def set_month_data(year: int, month: int, data: dict):
    plan_payments = data.get("plan_payments", 0)
    if plan_payments is not None:
        plan_payments = int(plan_payments)
    result_payments = data.get("result_payments")
    if result_payments is not None:
        result_payments = int(result_payments)
    supabase.table("month_data").upsert({
        "year": year,
        "month": month,
        "plan_payments": plan_payments,
        "plan_profitability": data.get("plan_profitability_pct", 0),
        "result_payments": result_payments,
        "result_profitability": data.get("result_profitability_pct"),
        "cumulative_entries": data.get("cumulative_entries", [])
    }).execute()

def get_extended_report(year: int, month: int) -> dict | None:
    res = supabase.table("extended_reports").select("data").eq("year", year).eq("month", month).execute()
    return res.data[0]["data"] if res.data else None

def set_extended_report(year: int, month: int, data: dict):
    supabase.table("extended_reports").upsert({
        "year": year,
        "month": month,
        "data": data
    }).execute()

def get_all_years() -> List[int]:
    res = supabase.table("year_plans").select("year").execute()
    return [row["year"] for row in res.data] if res.data else []

def get_all_extended_reports() -> dict:
    res = supabase.table("extended_reports").select("year", "month", "data").execute()
    reports = {}
    for row in res.data:
        key = f"{row['year']}-{row['month']:02d}"
        reports[key] = row["data"]
    return reports

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======
def days_in(y, m): return monthrange(y, m)[1]

def daily_from_cum(md, y, m):
    entries = sorted(md.get("cumulative_entries", []), key=lambda x: x["date"])
    if not entries:
        return {}
    facts = {}
    pc, pd = 0, 0
    for e in entries:
        day = int(e["date"].split("-")[2])
        cum = e.get("cumulative_payments", 0)
        pr = e.get("profitability_pct", 0)
        span = day - pd
        if span > 0:
            dp = (cum - pc) / span
            st = pd + 1 if pd > 0 else 1
            for dd in range(st, day + 1):
                facts[dd] = {"payments": dp, "profitability_pct": pr, "est": span > 1}
        pc, pd = cum, day
    return facts

def mtotals(md, y, m, ref=None):
    now = datetime.now()
    td = days_in(y, m)
    if ref is None:
        if y == now.year and m == now.month:
            ref = now.day
        elif datetime(y, m, 1) < now:
            ref = td
        else:
            ref = 1

    elapsed = ref - 1
    remaining = td - ref + 1

    pp = md.get("plan_payments", 0)
    ppr = md.get("plan_profitability_pct", 0)
    rp = md.get("result_payments")
    rpr = md.get("result_profitability_pct")
    df = daily_from_cum(md, y, m)
    fp = rp if rp is not None else sum(v["payments"] for v in df.values())

    # Рентабельность – последняя внесённая
    ents = md.get("cumulative_entries", [])
    if ents:
        last_entry = sorted(ents, key=lambda x: x["date"])[-1]
        fpr = last_entry.get("profitability_pct", 0)
    elif rpr is not None:
        fpr = rpr
    else:
        fpr = 0

    # План на сегодня
    if elapsed > 0:
        plan_today = (pp / td) * elapsed
    else:
        plan_today = 0
    pct_today = (fp / plan_today * 100) if plan_today > 0 else 0

    # Отставание/опережение
    ideal = (pp / td) * elapsed if td else 0
    lag = ideal - fp

    rem = pp - fp
    dn = rem / remaining if remaining > 0 else rem
    avgd = pp / td if td else 0

    pctp = fp / pp * 100 if pp else 0
    pctpr = fpr / ppr * 100 if ppr else 0
    lagpr = ppr - fpr

    behind = lag > 0
    ahead = pctp >= 100 or lag < -pp * 0.05

    return {
        "year": y, "month": m, "mn": MN.get(m, ""),
        "ref": ref, "td": td,
        "elapsed": elapsed,
        "remaining": remaining,
        "pp": pp, "ppr": ppr,
        "fp": fp, "fpr": fpr,
        "lc": ents[-1]["cumulative_payments"] if ents else 0,
        "ld": ents[-1]["date"] if ents else None,
        "pctp": pctp, "pctpr": pctpr,
        "lag": lag, "lagpr": lagpr,
        "rem": rem, "dn": dn, "avgd": avgd,
        "df": df, "behind": behind, "ahead": ahead,
        "pct_today": pct_today
    }

def ytotals(year):
    yd = get_year_plan(year)
    ypp = yd["year_plan_payments"]
    ypr = yd["year_plan_profitability_pct"]
    now = datetime.now()
    tp = 0
    fp_ = 0
    pv = []
    mr = []
    for mi in range(1, 13):
        md = get_month_data(year, mi)
        if md["plan_payments"] > 0 or md["cumulative_entries"]:
            tp += md["plan_payments"]
            if year < now.year or (year == now.year and mi <= now.month):
                t = mtotals(md, year, mi)
                fp_ += t["fp"]
                if t["fpr"] > 0:
                    pv.append(t["fpr"])
                mr.append({"m": mi, "n": MN[mi], "plan": md["plan_payments"], "fact": t["fp"], "pct": t["pctp"], "prof": t["fpr"]})
    ap = sum(pv) / len(pv) if pv else 0
    return {
        "y": year, "ypp": ypp, "ypr": ypr, "tp": tp, "fp": fp_, "ap": ap,
        "pctp": fp_ / ypp * 100 if ypp else 0, "pctpr": ap / ypr * 100 if ypr else 0, "mr": mr
    }

# ====== ГРАФИКИ (без изменений) ======
def gen_month_dash(md, t):
    fig = plt.figure(figsize=(14,20), facecolor="#FFFFFF")
    BG, CB, T, TS = "#FFFFFF", "#F8F9FA", "#212529", "#6C757D"
    GR, RD, OR, GD, CY = "#22c55e", "#ef4444", "#FFA500", "#FFD700", "#06b6d4"

    fig.text(0.5,0.97, f'{t["mn"]} {t["year"]}', ha="center", fontsize=28, fontweight="bold", color=T)
    stxt, scol = ("ПЕРЕВЫПОЛНЕНИЕ", GR) if t["ahead"] else (("ОТСТАВАНИЕ", RD) if t["behind"] else ("В НОРМЕ", CY))
    fig.text(0.5,0.945, stxt, ha="center", fontsize=18, fontweight="bold", color=scol)

    ax1 = fig.add_axes([0.06,0.86,0.88,0.04], facecolor=CB)
    ax1.set_xlim(0,100); ax1.set_ylim(0,1); ax1.set_xticks([]); ax1.set_yticks([])
    for s in ax1.spines.values(): s.set_visible(False)
    pct = min(t["pctp"],100)
    bc = GR if t["ahead"] else (RD if t["behind"] else OR)
    ax1.barh(0.5, pct, 0.7, color=bc, alpha=0.9, zorder=2)
    ax1.barh(0.5, 100, 0.7, color="#E5E7EB", alpha=0.8, zorder=1)
    icon = "🚀" if t["ahead"] else ("❗" if t["behind"] else "💰")
    ax1.text(0,1.8, f'{icon} ОПЛАТЫ', fontsize=18, fontweight="bold", color=T, transform=ax1.transAxes)
    ax1.text(1,1.8, f'{t["fp"]:,.0f} / {t["pp"]:,.0f} ₽  ({t["pctp"]:.1f}%)', fontsize=16, color=bc, ha="right", fontweight="bold", transform=ax1.transAxes)

    ax2 = fig.add_axes([0.06,0.78,0.88,0.04], facecolor=CB)
    ax2.set_xlim(0,100); ax2.set_ylim(0,1); ax2.set_xticks([]); ax2.set_yticks([])
    for s in ax2.spines.values(): s.set_visible(False)
    pp2 = min(t["pctpr"],100)
    pc2 = GR if t["lagpr"]<=0 else RD
    ax2.barh(0.5, pp2, 0.7, color=pc2, alpha=0.9, zorder=2)
    ax2.barh(0.5, 100, 0.7, color="#E5E7EB", alpha=0.8, zorder=1)
    ic2 = "🚀" if t["lagpr"]<=0 else "❗"
    ax2.text(0,1.8, f'{ic2} РЕНТАБЕЛЬНОСТЬ', fontsize=18, fontweight="bold", color=T, transform=ax2.transAxes)
    ax2.text(1,1.8, f'{t["fpr"]:.1f}% / {t["ppr"]:.1f}% ({t["pctpr"]:.1f}%)', fontsize=16, color=pc2, ha="right", fontweight="bold", transform=ax2.transAxes)

    y0 = 0.72
    lagc = RD if t["behind"] else GR
    lagpc = RD if t["lagpr"]>0 else GR
    mets = [
        (f'{"❗" if t["behind"] else "🚀"} Отставание:', f'{abs(t["lag"]):,.0f} ₽', lagc),
        (f'{"❗" if t["lagpr"]>0 else "🚀"} Откл. рентаб.:', f'{t["lagpr"]:+.1f} п.п.', lagpc),
        ("⚡ Нужно в день:", f'{t["dn"]:,.0f} ₽', OR),
        ("📅 День:", f'{t["elapsed"]} из {t["td"]} (ост. {t["remaining"]})', CY),
        ("📊 Норма/день:", f'{t["avgd"]:,.0f} ₽', TS),
    ]
    for lb, vl, cl in mets:
        fig.text(0.08, y0, lb, fontsize=16, color=TS)
        fig.text(0.92, y0, vl, fontsize=16, color=cl, ha="right", fontweight="bold")
        y0 -= 0.03

    df = t.get("df", {})
    if df:
        days = sorted(df.keys())
        cum = []
        r = 0
        for d in days:
            r += df[d]["payments"]
            cum.append(r)
        ax3 = fig.add_axes([0.08,0.32,0.86,0.24], facecolor=CB)
        pdays = list(range(1, t["td"]+1))
        pline = [t["pp"] * d / t["td"] for d in pdays]
        lc = GR if t["ahead"] else (RD if t["behind"] else OR)
        ax3.plot(pdays, pline, "--", color=CY, lw=2, alpha=0.7, label="План")
        ax3.plot(days, cum, "-o", color=lc, lw=2.5, ms=5, label="Факт")
        ax3.fill_between(days, cum, alpha=0.15, color=lc)
        ax3.legend(loc="upper left", fontsize=12, facecolor="white", edgecolor="#E5E7EB", labelcolor=T)
        ax3.set_title("Накопительная динамика", fontsize=16, fontweight="bold", color=T, pad=12)
        ax3.tick_params(colors=TS, labelsize=12)
        ax3.grid(True, alpha=0.2, color="#E5E7EB")
        for s in ax3.spines.values(): s.set_color("#E5E7EB")

        ax4 = fig.add_axes([0.08,0.05,0.86,0.20], facecolor=CB)
        pays = [df[d]["payments"] for d in days]
        bcols = [GR if p >= t["avgd"] else RD for p in pays]
        ax4.bar(days, pays, color=bcols, alpha=0.8)
        ax4.axhline(t["avgd"], color=GD, lw=2, ls="--")
        ax4.set_title("Ежедневные оплаты", fontsize=16, fontweight="bold", color=T, pad=12)
        ax4.tick_params(colors=TS, labelsize=12)
        ax4.grid(True, alpha=0.2, color="#E5E7EB", axis="y")
        for s in ax4.spines.values(): s.set_color("#E5E7EB")

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=BG)
    buf.seek(0)
    plt.close(fig)
    return buf

def gen_year_dash(yd, yt):
    fig = plt.figure(figsize=(14,14), facecolor="#FFFFFF")
    BG, CB, T, TS = "#FFFFFF", "#F8F9FA", "#212529", "#6C757D"
    GR, RD, OR, GD = "#22c55e", "#ef4444", "#FFA500", "#FFD700"
    fig.text(0.5,0.97, f'Год {yt["y"]}', ha="center", fontsize=28, fontweight="bold", color=T)
    fig.text(0.5,0.94, f'{yt["fp"]:,.0f} / {yt["ypp"]:,.0f} ₽ ({yt["pctp"]:.1f}%)', ha="center", fontsize=16, color=OR)
    mr = yt.get("mr", [])
    if mr:
        ax = fig.add_axes([0.08,0.45,0.86,0.42], facecolor=CB)
        ms = [r["m"] for r in mr]
        ps = [r["plan"] for r in mr]
        fs = [r["fact"] for r in mr]
        x = np.arange(len(ms))
        w = 0.35
        ax.bar(x-w/2, ps, w, label="План", color="#94A3B8", alpha=0.7)
        ax.bar(x+w/2, fs, w, label="Факт", color=OR, alpha=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels([MN[m][:3] for m in ms], fontsize=11)
        ax.legend(fontsize=12, facecolor="white", edgecolor="#E5E7EB", labelcolor=T)
        ax.set_title("Помесячное выполнение", fontsize=16, fontweight="bold", color=T, pad=12)
        ax.tick_params(colors=TS, labelsize=11)
        ax.grid(True, alpha=0.2, color="#E5E7EB", axis="y")
        for s in ax.spines.values(): s.set_color("#E5E7EB")

        ax2 = fig.add_axes([0.08,0.06,0.86,0.30], facecolor=CB)
        profs = [r["prof"] for r in mr]
        cols = [GR if p >= yt["ypr"] else RD for p in profs]
        ax2.bar(range(len(ms)), profs, color=cols, alpha=0.8)
        ax2.axhline(yt["ypr"], color=GD, lw=2, ls="--", label=f'План {yt["ypr"]:.0f}%')
        ax2.set_xticks(range(len(ms)))
        ax2.set_xticklabels([MN[m][:3] for m in ms], fontsize=11)
        ax2.legend(fontsize=11, facecolor="white", edgecolor="#E5E7EB", labelcolor=T)
        ax2.set_title("Рентабельность по месяцам (%)", fontsize=16, fontweight="bold", color=T, pad=12)
        ax2.tick_params(colors=TS, labelsize=11)
        ax2.grid(True, alpha=0.2, color="#E5E7EB", axis="y")
        for s in ax2.spines.values(): s.set_color("#E5E7EB")
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=BG)
    buf.seek(0)
    plt.close(fig)
    return buf

def gen_multi_year(data, years):
    fig = plt.figure(figsize=(16,10), facecolor="#FFFFFF")
    BG, CB, T, TS, OR, CY = "#FFFFFF", "#F8F9FA", "#212529", "#6C757D", "#FFA500", "#06b6d4"
    res = []
    for y in sorted(years):
        s = str(y)
        if s in data.get("years", {}):
            yt = ytotals(y)
            res.append({"y": y, "plan": yt["ypp"], "fact": yt["fp"], "prof": yt["ap"]})
    if not res:
        fig.text(0.5,0.5, "Нет данных", ha="center", fontsize=18, color=TS)
    else:
        fig.text(0.5,0.95, f'Динамика {min(years)}-{max(years)}', ha="center", fontsize=24, fontweight="bold", color=T)
        ax = fig.add_axes([0.08,0.15,0.78,0.72], facecolor=CB)
        ys = [r["y"] for r in res]
        ps = [r["plan"]/1e6 for r in res]
        fs = [r["fact"]/1e6 for r in res]
        x = np.arange(len(ys))
        w = 0.35
        ax.bar(x-w/2, ps, w, label="План (млн)", color="#94A3B8", alpha=0.7)
        ax.bar(x+w/2, fs, w, label="Факт (млн)", color=OR, alpha=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels(ys, fontsize=14)
        ax.set_ylabel("Млн ₽", color=T, fontsize=13)
        ax.tick_params(colors=TS, labelsize=12)
        ax.legend(fontsize=12, facecolor="white", edgecolor="#E5E7EB", labelcolor=T)
        ax.grid(True, alpha=0.2, color="#E5E7EB", axis="y")
        for s in ax.spines.values(): s.set_color("#E5E7EB")
        ax2 = ax.twinx()
        profs = [r["prof"] for r in res]
        ax2.plot(x, profs, "-o", color=CY, lw=2, ms=8, label="Рентаб. %")
        ax2.set_ylabel("Рентаб. %", color=CY, fontsize=13)
        ax2.tick_params(colors=CY, labelsize=12)
        ax2.legend(loc="upper right", fontsize=12, facecolor="white", edgecolor="#E5E7EB", labelcolor=T)
        for s in ax2.spines.values(): s.set_color("#E5E7EB")
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=BG)
    buf.seek(0)
    plt.close(fig)
    return buf

# ====== ACCESS ======
async def _chk(update):
    if is_banned(update.effective_user.id):
        await (update.message or update.callback_query.message).reply_text("⛔ Доступ заблокирован.")
        return False
    return True

async def _adm(update):
    uid = update.effective_user.id if update.message else update.callback_query.from_user.id
    if not is_admin(uid):
        t = "⛔ Только администратор."
        if update.callback_query:
            await update.callback_query.answer(t, show_alert=True)
        else:
            await update.message.reply_text(t)
        return False
    return True

def _msg(update):
    return update.callback_query.message if update.callback_query else update.message

# ====== /start ======
async def start(update, ctx):
    if not await _chk(update):
        return ConversationHandler.END
    uid = update.effective_user.id
    now = datetime.now()
    if update.message.text and update.message.text.startswith('/start login'):
        # Пользователь перешёл по ссылке авторизации
        # Если он уже зарегистрирован, просто открываем приложение
        if is_reg(uid):
            # Отправляем сообщение с кнопкой для открытия приложения
            await update.message.reply_text(
                "✅ Вы уже зарегистрированы!\nНажмите кнопку, чтобы открыть приложение:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))]
                ])
            )
            return ConversationHandler.END
        else:
            # Если не зарегистрирован – предлагаем зарегистрироваться
            await update.message.reply_text(
                "👋 Добро пожаловать!\nДавайте зарегистрируем вас.\n\nКак вас зовут?",
                parse_mode="Markdown"
            )
            return REG_NAME
    if uid == ADMIN_USER_ID and not is_reg(uid):
        nm = update.effective_user.first_name or "Админ"
        reg_user(uid, nm, "director")
        miss = []
        for yy in range(2022, now.year + 1):
            yp = get_year_plan(yy)
            if yp["year_plan_payments"] == 0:
                miss.append(f"📅 Годовой план {yy}")
        md = get_month_data(now.year, now.month)
        if md["plan_payments"] == 0:
            miss.append(f"📋 План {MN[now.month]} {now.year}")
        miss.append("✏️ Ретро-данные за прошлые периоды")
        mt = "\n".join(f"  • {m}" for m in miss)
        kb = [
            [InlineKeyboardButton("📋 План месяца", callback_data="set_plan")],
            [InlineKeyboardButton("📝 Внести факт", callback_data="add_fact")],
            [InlineKeyboardButton("📅 Годовой план", callback_data="year_plan")],
            [InlineKeyboardButton("✏️ Ретро-данные", callback_data="retro")],
            [InlineKeyboardButton("📊 Дашборд месяца", callback_data="dash_m")],
            [InlineKeyboardButton("👥 Управление", callback_data="manage")]
        ]
        await update.message.reply_text(
            f"👑 *Добро пожаловать, {nm}!*\n\n"
            f"Я узнал тебя — ты *главный администратор*.\n\n"
            f"📅 Сегодня: *{now.strftime('%d.%m.%Y')}* ({MN[now.month]} {now.year})\n\n"
            f"🔧 *Рекомендую внести:*\n{mt}\n\nВыбери с чего начать:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
        return ConversationHandler.END
    if not is_reg(uid):
        await update.message.reply_text("👋 *Добро пожаловать!*\n\nКак вас зовут?", parse_mode="Markdown")
        return REG_NAME
    u = get_user(uid)
    dn_ = dname(uid)
    if is_admin(uid):
        md = get_month_data(now.year, now.month)
        hints = []
        if md["plan_payments"] == 0:
            hints.append(f"⚠️ Нет плана на {MN[now.month]}")
        if md["plan_payments"] != 0 and not md["cumulative_entries"]:
            hints.append("⚠️ Нет фактов")
        ht = ("\n" + "\n".join(hints)) if hints else ""
        kb = [
            [InlineKeyboardButton("📋 План месяца", callback_data="set_plan"), InlineKeyboardButton("📊 Дашборд месяца", callback_data="dash_m")],
            [InlineKeyboardButton("📝 Внести факт", callback_data="add_fact"), InlineKeyboardButton("📈 Текущая сводка", callback_data="summary")],
            [InlineKeyboardButton("📅 Годовой план", callback_data="year_plan"), InlineKeyboardButton("📊 Дашборд по году", callback_data="dash_y")],
            [InlineKeyboardButton("📋 Расш. отчёт", callback_data="ext_report"), InlineKeyboardButton("📉 Динамика по годам", callback_data="multi_y")],
            [InlineKeyboardButton("🕐 История", callback_data="history"), InlineKeyboardButton("✏️ Ретро", callback_data="retro")],
            [InlineKeyboardButton("👥 Управление", callback_data="manage")]
        ]
        if WEBAPP_URL and WEBAPP_URL != "ВСТАВЬТЕ_URL_ВАШЕГО_WEBAPP":
            kb.append([InlineKeyboardButton("📱 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))])
        await update.message.reply_text(
            f"🔥 *Привет, {dn_}!* 👑\n📅 {now.strftime('%d.%m.%Y')}{ht}\n\nВыбери:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
    else:
        kb = [
            [InlineKeyboardButton("📊 Дашборд месяца", callback_data="dash_m"), InlineKeyboardButton("📈 Текущая сводка", callback_data="summary")],
            [InlineKeyboardButton("📊 Дашборд по году", callback_data="dash_y"), InlineKeyboardButton("📉 Динамика по годам", callback_data="multi_y")],
            [InlineKeyboardButton("📋 Расш. отчёт", callback_data="view_ext"), InlineKeyboardButton("🕐 История", callback_data="history")]
        ]
        if u and u.get("position") == "manager":
            kb.append([InlineKeyboardButton("💰 Моя премия", callback_data="my_premium")])
        if WEBAPP_URL and WEBAPP_URL != "ВСТАВЬТЕ_URL_ВАШЕГО_WEBAPP":
            kb.append([InlineKeyboardButton("📱 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))])
        await update.message.reply_text(
            f"👋 *{dn_}!*\n📅 {now.strftime('%d.%m.%Y')}\n\nВыбери:",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )
    return ConversationHandler.END

# ====== РЕГИСТРАЦИЯ ======
async def reg_name(update, ctx):
    ctx.user_data["rn"] = update.message.text.strip()
    kb = [[InlineKeyboardButton(v, callback_data=f"pos_{k}")] for k, v in POS.items()]
    await update.message.reply_text(f"*{ctx.user_data['rn']}*, должность?",
                                    reply_markup=InlineKeyboardMarkup(kb),
                                    parse_mode="Markdown")
    return REG_POSITION

async def reg_pos(update, ctx):
    q = update.callback_query
    await q.answer()
    pos = q.data.replace("pos_", "")
    ctx.user_data["rp"] = pos
    return await _freg(update, ctx)

async def _freg(update, ctx):
    uid = update.effective_user.id
    nm = ctx.user_data.get("rn", "")
    pos = ctx.user_data.get("rp", "")
    reg_user(uid, nm, pos)
    msg = _msg(update)
    try:
        pn = POS.get(pos, pos)
        await ctx.bot.send_message(ADMIN_USER_ID, f"👤 Новый: {nm}\n{pn}\n✅", parse_mode="Markdown")
    except:
        pass
    if pos in ("manager", "marketer"):
        await msg.reply_text(f"✅ *{nm}!*\n\nРад, что ты заинтересован! 👍\nДавай делать деньги! 💰",
                             parse_mode="Markdown")
    elif pos == "founder":
        await msg.reply_text(f"🙇 *{nm}*, какая честь для нас, что Вы с нами ! Мы сделаем все возможное, чтобы на дашбордах Вы видели только прирост за приростом! 🚀",
                             parse_mode="Markdown")
    elif pos == "director":
        await msg.reply_text("✅ Спасибо за твой интерес к показателям ! 👏 Давай разбогатеем вместе! 💰",
                             parse_mode="Markdown")
    else:
        await msg.reply_text(f"✅ {nm}!")
    return ConversationHandler.END

# ====== ПЛАН МЕСЯЦА ======
async def set_plan_s(update, ctx):
    if not await _adm(update):
        return ConversationHandler.END
    now = datetime.now()
    ctx.user_data["py"], ctx.user_data["pm"] = now.year, now.month
    msg = _msg(update)
    if update.callback_query:
        await update.callback_query.answer()
    await msg.reply_text(f"📋 *План {MN[now.month]} {now.year}*\n\nОплаты (₽):", parse_mode="Markdown")
    return SET_PLAN_PAY

def _extract_number(text: str) -> float:
    cleaned = re.sub(r'[^0-9.,-]', '', text.replace(',', '.'))
    if not cleaned:
        raise ValueError("No number found")
    return float(cleaned)

async def plan_pay(update, ctx):
    try:
        v = _extract_number(update.message.text)
        ctx.user_data["pp"] = int(v)
        await update.message.reply_text(f"✅ {int(v):,.0f} ₽\nРентабельность (%):")
        return SET_PLAN_PROF
    except Exception:
        await update.message.reply_text("❌ Введите число (например, 1500000)")
        return SET_PLAN_PAY

async def plan_prof(update, ctx):
    try:
        raw = update.message.text
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', raw)
        match = re.search(r'(\d+[.,]?\d*)', cleaned)
        if not match:
            raise ValueError("No number found")
        num_str = match.group(1).replace(',', '.')
        v = float(num_str)
        md = get_month_data(ctx.user_data["py"], ctx.user_data["pm"])
        md["plan_payments"] = ctx.user_data["pp"]
        md["plan_profitability_pct"] = v
        set_month_data(ctx.user_data["py"], ctx.user_data["pm"], md)
        td = days_in(ctx.user_data["py"], ctx.user_data["pm"])
        dp = ctx.user_data["pp"] / td if td else 0
        await update.message.reply_text(
            f"✅ *План!*\n💰 {ctx.user_data['pp']:,.0f} ₽\n📈 {v:.1f}%\n📅 Дней: {td}\n📊 Норма: {dp:,.0f} ₽/день",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"plan_prof error: {e}, raw text: {repr(update.message.text)}")
        await update.message.reply_text("❌ Введите рентабельность (например, 20)")
        return SET_PLAN_PROF

# ====== ГОДОВОЙ ПЛАН ======
async def yplan_s(update, ctx):
    if not await _adm(update):
        return ConversationHandler.END
    msg = _msg(update)
    if update.callback_query:
        await update.callback_query.answer()
    await msg.reply_text("📅 *Годовой план*\n\nВведите год (2022-2030):", parse_mode="Markdown")
    return SET_YPLAN_YEAR

async def yplan_year(update, ctx):
    try:
        y = int(update.message.text.strip())
        if y < 2020 or y > 2030:
            raise ValueError
        ctx.user_data["ypy"] = y
        await update.message.reply_text(f"Год: *{y}*\nОплаты на год (₽):", parse_mode="Markdown")
        return SET_YPLAN_PAY
    except:
        await update.message.reply_text("❌ Введите год от 2020 до 2030")
        return SET_YPLAN_YEAR

async def yplan_pay(update, ctx):
    try:
        v = _extract_number(update.message.text)
        ctx.user_data["ypp"] = int(v)
        await update.message.reply_text(f"✅ {int(v):,.0f} ₽\nРентабельность (%):", parse_mode="Markdown")
        return SET_YPLAN_PROF
    except:
        await update.message.reply_text("❌ Введите число (оплаты на год)")
        return SET_YPLAN_PAY

async def yplan_prof(update, ctx):
    try:
        v = _extract_number(update.message.text)
        set_year_plan(ctx.user_data["ypy"], ctx.user_data["ypp"], v)
        await update.message.reply_text(
            f"✅ *Год {ctx.user_data['ypy']}*\n💰 {ctx.user_data['ypp']:,.0f} ₽\n📈 {v:.1f}%",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Введите рентабельность (например, 20)")
        return SET_YPLAN_PROF

# ====== ФАКТ ======
async def fact_s(update, ctx):
    if not await _adm(update):
        return ConversationHandler.END
    now = datetime.now()
    md = get_month_data(now.year, now.month)
    if md["plan_payments"] == 0:
        await _msg(update).reply_text("⚠️ Сначала /set_plan")
        return ConversationHandler.END
    ents = md.get("cumulative_entries", [])
    lc = ents[-1]["cumulative_payments"] if ents else 0
    ld_ = ents[-1]["date"] if ents else "—"
    ctx.user_data["fd"] = now.strftime("%Y-%m-%d")
    ctx.user_data["fy"], ctx.user_data["fm"] = now.year, now.month
    msg = _msg(update)
    if update.callback_query:
        await update.callback_query.answer()
    await msg.reply_text(
        f"📝 *Факт*\n📅 {now.strftime('%d.%m.%Y')}\nПосл: {lc:,.0f} ₽ ({ld_})\n\n"
        f"НАКОПИТЕЛЬНАЯ сумма с 1 по {now.day-1} {MN[now.month][:3]}:",
        parse_mode="Markdown"
    )
    return SET_FACT_CUM

async def fact_cum(update, ctx):
    try:
        v = _extract_number(update.message.text)
        ctx.user_data["fc"] = int(v)
        await update.message.reply_text(f"✅ {int(v):,.0f} ₽\nРентабельность (%):")
        return SET_FACT_PROF
    except:
        await update.message.reply_text("❌ Введите накопленную сумму")
        return SET_FACT_CUM

async def fact_prof(update, ctx):
    try:
        v = _extract_number(update.message.text)
        md = get_month_data(ctx.user_data["fy"], ctx.user_data["fm"])
        e = {"date": ctx.user_data["fd"], "cumulative_payments": ctx.user_data["fc"], "profitability_pct": v}
        ents = md.get("cumulative_entries", [])
        idx = next((i for i, x in enumerate(ents) if x["date"] == e["date"]), None)
        if idx is not None:
            ents[idx] = e
        else:
            ents.append(e)
        md["cumulative_entries"] = ents
        set_month_data(ctx.user_data["fy"], ctx.user_data["fm"], md)
        t = mtotals(md, ctx.user_data["fy"], ctx.user_data["fm"])
        li = "❗" if t["behind"] else "🚀"
        lw = "Отставание" if t["behind"] else "Опережение"
        await update.message.reply_text(
            f"✅ *Сохранено!*\n\n💰 {t['fp']:,.0f}/{t['pp']:,.0f} ₽ ({t['pctp']:.1f}%)\n"
            f"{li} {lw}: {abs(t['lag']):,.0f} ₽\n⚡ Нужно/день: {t['dn']:,.0f} ₽\n"
            f"📈 Рент: {t['fpr']:.1f}%/{t['ppr']:.1f}%\n📅 Ост: {t['remaining']} дн.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"fact_prof error: {e}")
        await update.message.reply_text("❌ Ошибка, попробуйте ещё раз")
        return SET_FACT_PROF

# ====== РЕТРО-ВВОД ======
async def retro_s(update, ctx):
    if not await _adm(update):
        return ConversationHandler.END
    msg = _msg(update)
    if update.callback_query:
        await update.callback_query.answer()
    kb = [[InlineKeyboardButton(str(y), callback_data=f"ry_{y}")] for y in range(2026, 2021, -1)]
    await msg.reply_text("✏️ *Ретро-ввод*\n\nВыберите год:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return RETRO_SEL_YEAR

async def retro_year(update, ctx):
    q = update.callback_query
    await q.answer()
    y = int(q.data.replace("ry_", ""))
    ctx.user_data["rty"] = y
    kb = [[InlineKeyboardButton(MN[m], callback_data=f"rm_{m}")] for m in range(1, 13)]
    await q.message.reply_text(f"Год: *{y}*\nВыберите месяц:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return RETRO_SEL_MONTH

async def retro_month(update, ctx):
    q = update.callback_query
    await q.answer()
    m = int(q.data.replace("rm_", ""))
    ctx.user_data["rtm"] = m
    y = ctx.user_data["rty"]
    kb = [
        [InlineKeyboardButton("💰 План оплат (₽)", callback_data="rf_plan_pay")],
        [InlineKeyboardButton("📈 План рентаб. (%)", callback_data="rf_plan_prof")],
        [InlineKeyboardButton("💰 Факт оплат (₽)", callback_data="rf_fact_pay")],
        [InlineKeyboardButton("📈 Факт рентаб. (%)", callback_data="rf_fact_prof")],
        [InlineKeyboardButton("📦 Всё сразу (план+факт)", callback_data="rf_all")],
    ]
    md = get_month_data(y, m)
    pp = md.get("plan_payments", 0)
    ppr = md.get("plan_profitability_pct", 0)
    rp = md.get("result_payments")
    rpr = md.get("result_profitability_pct")
    cur = f"\n\n📋 *Текущие данные:*\nПлан: {pp:,.0f} ₽ / {ppr:.1f}%\nФакт: {'—' if rp is None else f'{rp:,.0f} ₽'} / {'—' if rpr is None else f'{rpr:.1f}%'}"
    await q.message.reply_text(
        f"✏️ *{MN[m]} {y}*{cur}\n\nЧто заполнить?",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return RETRO_SEL_FIELD

async def retro_field(update, ctx):
    q = update.callback_query
    await q.answer()
    f = q.data.replace("rf_", "")
    ctx.user_data["rtf"] = f
    prompts = {
        "plan_pay": "Введите *план оплат* (₽):",
        "plan_prof": "Введите *план рентабельности* (%):",
        "fact_pay": "Введите *факт оплат* (₽):",
        "fact_prof": "Введите *факт рентабельности* (%):",
        "all": "Введите через запятую:\n*план оплат, факт оплат, план рент%, факт рент%*\nПример: 5000000, 4800000, 20, 18.5",
    }
    await q.message.reply_text(prompts.get(f, "Введите значение:"), parse_mode="Markdown")
    return RETRO_VALUE

async def retro_val(update, ctx):
    try:
        y, m = ctx.user_data["rty"], ctx.user_data["rtm"]
        f = ctx.user_data["rtf"]
        txt = update.message.text.strip()
        md = get_month_data(y, m)

        if f == "plan_pay":
            md["plan_payments"] = int(_extract_number(txt))
        elif f == "plan_prof":
            md["plan_profitability_pct"] = _extract_number(txt)
        elif f == "fact_pay":
            val = _extract_number(txt)
            md["result_payments"] = int(val) if val is not None else None
        elif f == "fact_prof":
            md["result_profitability_pct"] = _extract_number(txt)
        elif f == "all":
            parts = [p.strip() for p in txt.split(",")]
            if len(parts) < 4:
                raise ValueError("Нужно 4 значения")
            md["plan_payments"] = int(_extract_number(parts[0]))
            md["result_payments"] = int(_extract_number(parts[1]))
            md["plan_profitability_pct"] = _extract_number(parts[2])
            md["result_profitability_pct"] = _extract_number(parts[3])

        set_month_data(y, m, md)
        pp = md.get("plan_payments", 0)
        ppr = md.get("plan_profitability_pct", 0)
        rp = md.get("result_payments")
        rpr = md.get("result_profitability_pct")
        await update.message.reply_text(
            f"✅ *{MN[m]} {y} — сохранено!*\n\n"
            f"План: {pp:,.0f} ₽ / {ppr:.1f}%\n"
            f"Факт: {'—' if rp is None else f'{rp:,.0f} ₽'} / {'—' if rpr is None else f'{rpr:.1f}%'}",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}\nПопробуйте ещё раз (например, 5000000)")
        return RETRO_VALUE

# ====== ДАШБОРДЫ ======
async def dash_m(update, ctx):
    if not await _chk(update):
        return
    if update.callback_query:
        await update.callback_query.answer("⏳")
    now = datetime.now()
    md = get_month_data(now.year, now.month)
    msg = _msg(update)
    if md["plan_payments"] == 0:
        await msg.reply_text("⚠️ План не установлен.")
        return
    t = mtotals(md, now.year, now.month)
    img = gen_month_dash(md, t)
    await msg.reply_photo(photo=img, caption=f"📊 {MN[now.month]} {now.year}")

async def dash_y(update, ctx):
    if not await _chk(update):
        return
    if update.callback_query:
        await update.callback_query.answer("⏳")
    now = datetime.now()
    yd = get_year_plan(now.year)
    msg = _msg(update)
    if yd["year_plan_payments"] == 0:
        await msg.reply_text("⚠️ Годовой план не установлен. /set_year_plan")
        return
    yt = ytotals(now.year)
    img = gen_year_dash(yd, yt)
    await msg.reply_photo(photo=img, caption=f"📊 Год {now.year}")

async def multi_y(update, ctx):
    if not await _chk(update):
        return
    if update.callback_query:
        await update.callback_query.answer("⏳")
    years = get_all_years()
    msg = _msg(update)
    if not years:
        await msg.reply_text("⚠️ Нет данных.")
        return
    data = {"years": {}}
    for y in years:
        yp = get_year_plan(y)
        data["years"][str(y)] = {
            "year_plan_payments": yp["year_plan_payments"],
            "year_plan_profitability_pct": yp["year_plan_profitability_pct"],
            "months": {}
        }
        for m in range(1, 13):
            md = get_month_data(y, m)
            if md["plan_payments"] > 0 or md["cumulative_entries"]:
                data["years"][str(y)]["months"][f"{m:02d}"] = md
    img = gen_multi_year(data, years)
    await msg.reply_photo(photo=img, caption="📉 Динамика по годам")

# ====== СВОДКА (исправлена) ======
async def summary_m(update, ctx):
    if not await _chk(update):
        return
    if update.callback_query:
        await update.callback_query.answer()
    now = datetime.now()
    md = get_month_data(now.year, now.month)
    msg = _msg(update)
    if md["plan_payments"] == 0:
        await msg.reply_text("⚠️ План не установлен.")
        return
    t = mtotals(md, now.year, now.month)
    si = "🚀" if t["ahead"] else ("❗" if t["behind"] else "📊")
    st = "ПЕРЕВЫПОЛНЕНИЕ" if t["ahead"] else ("ОТСТАВАНИЕ" if t["behind"] else "В НОРМЕ")
    n = int(t["pctp"] // 5)
    bar = "█" * min(n, 20) + "░" * max(20 - n, 0)

    # Формируем строку отставания/перевыполнения
    if t['behind']:
        lag_text = f"❗ Отставание: {abs(t['lag']):,.0f} ₽"
    else:
        lag_text = f"🚀 Перевыполнение: {abs(t['lag']):,.0f} ₽"

    await msg.reply_text(
        f"{si} *{MN[now.month]} {now.year} — {st}*\n"
        f"📅 День {now.day} (прошло {t['elapsed']} из {t['td']}, осталось {t['remaining']})\n\n"
        f"💰 *ОПЛАТЫ*\nПлан: {t['pp']:>12,.0f} ₽\nФакт: {t['fp']:>12,.0f} ₽\n"
        f"[{bar}] {t['pctp']:.1f}%\n"
        f"📈 *Темп выполнения:* {t['pct_today']:.1f}%\n"
        f"{lag_text}\n"
        f"⚡ Нужно/день: *{t['dn']:,.0f} ₽*\n\n"
        f"📈 Рент: {t['fpr']:.1f}% / {t['ppr']:.1f}%",
        parse_mode="Markdown"
    )

# ====== ИСТОРИЯ ======
async def hist_s(update, ctx):
    if not await _chk(update):
        return
    if update.callback_query:
        await update.callback_query.answer()
    years = get_all_years()
    years.sort(reverse=True)
    msg = _msg(update)
    if not years:
        await msg.reply_text("📅 Нет данных.")
        return
    kb = [[InlineKeyboardButton(f"📅 {y}", callback_data=f"hist_{y}")] for y in years]
    await msg.reply_text("📅 *История* — год:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def hist_y_cb(update, ctx):
    q = update.callback_query
    await q.answer()
    y = int(q.data.replace("hist_", ""))
    lines = [f"📅 *{y}:*\n"]
    for mi in range(1, 13):
        md = get_month_data(y, mi)
        if md["plan_payments"] > 0 or md["cumulative_entries"]:
            t = mtotals(md, y, mi)
            e = "✅" if t["pctp"] >= 100 else ("🟡" if t["pctp"] >= 70 else "🔴")
            lines.append(f"{e} *{MN[mi]}*: {t['fp']:,.0f}/{t['pp']:,.0f} ({t['pctp']:.0f}%) рент {t['fpr']:.1f}%")
    await q.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ====== ПРЕМИЯ ======
async def my_prem(update, ctx):
    uid = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
    u = get_user(uid)
    if not u or u.get("position") != "manager":
        if update.callback_query:
            await update.callback_query.answer("⛔ Только для менеджеров.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Только для менеджеров.")
        return
    if update.callback_query:
        await update.callback_query.answer()
    now = datetime.now()
    kb = []
    y, m = PREMIUM_START_YEAR, PREMIUM_START_MONTH
    while y < now.year or (y == now.year and m <= now.month):
        kb.append([InlineKeyboardButton(f"{MN[m]} {y}", callback_data=f"prem_{y}_{m}")])
        m += 1
        if m > 12:
            m = 1
            y += 1
    kb.reverse()
    await _msg(update).reply_text(f"💰 *{dname(uid)}*, месяц:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def prem_calc(update, ctx):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    if not u or u.get("position") != "manager":
        await q.message.reply_text("⛔")
        return
    dn_ = dname(uid)
    p = q.data.replace("prem_", "").split("_")
    sy, sm = int(p[0]), int(p[1])
    if sy < PREMIUM_START_YEAR or (sy == PREMIUM_START_YEAR and sm < PREMIUM_START_MONTH):
        await q.message.reply_text("⛔ *Закрытый период*", parse_mode="Markdown")
        return
    md = get_month_data(sy, sm)
    t = mtotals(md, sy, sm)
    fp, fpr, pp, ppr = t["fp"], t["fpr"], t["pp"], t["ppr"]
    now = datetime.now()
    ic = sy == now.year and sm == now.month
    if fp == 0 and pp == 0:
        await q.message.reply_text("😕 Нет данных за этот месяц.")
        return

    premium_now = fp * (fpr / 100) * 0.01
    premium_plan = pp * (ppr / 100) * 0.01

    if ic:
        await q.message.reply_text(
            f"💰 *Твоя премия с текущими показателями:* {premium_now:,.0f} ₽\n"
            f"🎯 *При выполнении плановых показателей:* {premium_plan:,.0f} ₽\n\n"
            f"🔥 Держи планку! 💪🚀",
            parse_mode="Markdown"
        )
    else:
        await q.message.reply_text(
            f"💰 *Твоя премия за {MN[sm]} {sy}:* {premium_now:,.0f} ₽\n\n"
            f"✨ Отличный результат! 👏",
            parse_mode="Markdown"
        )

# ====== РАСШ. ОТЧЁТ ======
async def ext_s(update, ctx):
    if not await _adm(update):
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
    years = list(range(2024, datetime.now().year + 1))
    kb = [[InlineKeyboardButton(str(y), callback_data=f"ext_year_{y}")] for y in years]
    await _msg(update).reply_text("📅 *Выберите год для расширенного отчёта:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return EXT_SEL_YEAR

async def ext_sel_year(update, ctx):
    q = update.callback_query
    await q.answer()
    year = int(q.data.replace("ext_year_", ""))
    ctx.user_data["ext_year"] = year
    kb = [[InlineKeyboardButton(MN[m], callback_data=f"ext_month_{m}")] for m in range(1, 13)]
    await q.message.reply_text(f"📆 *Год {year}* – выберите месяц:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return EXT_SEL_MONTH

async def ext_sel_month(update, ctx):
    q = update.callback_query
    await q.answer()
    month = int(q.data.replace("ext_month_", ""))
    ctx.user_data["ext_month"] = month
    await q.message.reply_text(f"📋 *{MN[month]} {ctx.user_data['ext_year']}*\n\nОплаты НОВЫХ (₽):", parse_mode="Markdown")
    return EXT_NEW_PAY

async def e_np(update, ctx):
    try:
        ctx.user_data["enp"] = int(_extract_number(update.message.text))
        await update.message.reply_text("Оплаты ПОСТОЯННЫХ (₽):")
        return EXT_REP_PAY
    except:
        await update.message.reply_text("❌ Введите число")
        return EXT_NEW_PAY

async def e_rp(update, ctx):
    try:
        ctx.user_data["erp"] = int(_extract_number(update.message.text))
        await update.message.reply_text("Кол-во оплат (новые):")
        return EXT_NEW_CNT
    except:
        await update.message.reply_text("❌ Введите целое число")
        return EXT_REP_PAY

async def e_nc(update, ctx):
    try:
        ctx.user_data["enc"] = int(_extract_number(update.message.text))
        await update.message.reply_text("Кол-во по отчету (пост.):")
        return EXT_RCR
    except:
        await update.message.reply_text("❌ Введите целое число")
        return EXT_NEW_CNT

async def e_rcr(update, ctx):
    try:
        ctx.user_data["ercr"] = int(_extract_number(update.message.text))
        await update.message.reply_text("Кол-во по факту (пост.):")
        return EXT_RCF
    except:
        await update.message.reply_text("❌ Введите целое число")
        return EXT_RCR

async def e_rcf(update, ctx):
    try:
        ctx.user_data["ercf"] = int(_extract_number(update.message.text))
        await update.message.reply_text("Рент. новых (%):")
        return EXT_NPROF
    except:
        await update.message.reply_text("❌ Введите число")
        return EXT_RCF

async def e_nprof(update, ctx):
    try:
        ctx.user_data["enpr"] = _extract_number(update.message.text)
        await update.message.reply_text("Рент. постоянных (%):")
        return EXT_RPROF
    except:
        await update.message.reply_text("❌ Введите число")
        return EXT_NPROF

async def e_rprof(update, ctx):
    try:
        v = _extract_number(update.message.text)
        y = ctx.user_data["ext_year"]
        m = ctx.user_data["ext_month"]
        np_, rp_ = ctx.user_data["enp"], ctx.user_data["erp"]
        tp_ = np_ + rp_
        nac = np_ / ctx.user_data["enc"] if ctx.user_data["enc"] else 0
        rac = rp_ / ctx.user_data["ercr"] if ctx.user_data["ercr"] else 0
        tpr = (np_ * ctx.user_data["enpr"] + rp_ * v) / tp_ if tp_ else 0
        data = {
            "new_payments": np_, "repeat_payments": rp_, "total_payments": tp_,
            "new_count": ctx.user_data["enc"], "repeat_count_report": ctx.user_data["ercr"],
            "repeat_count_fact": ctx.user_data["ercf"],
            "new_avg_check": nac, "repeat_avg_check": rac,
            "new_profitability_pct": ctx.user_data["enpr"], "repeat_profitability_pct": v,
            "total_profitability_pct": tpr
        }
        set_extended_report(y, m, data)
        await update.message.reply_text(f"✅ *{MN[m]} {y}*\n💰 {tp_:,.0f} ₽\n📈 Рент: {tpr:.1f}%", parse_mode="Markdown")
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ Введите число")
        return EXT_RPROF

# ====== УПРАВЛЕНИЕ ======
async def manage(update, ctx):
    if not await _adm(update):
        return
    if update.callback_query:
        await update.callback_query.answer()
    res = supabase.table("users").select("*").execute()
    users = res.data if res.data else []
    act = [u for u in users if not u.get("is_banned")]
    txt = f"👥 Активных: {len(act)}\n\n"
    for u in act[:10]:
        am = " 👑" if (u["user_id"] == ADMIN_USER_ID or u.get("is_admin")) else ""
        pos_name = POS.get(u.get("position"), "")
        txt += f"• {u.get('name')} — {pos_name}{am}\n"
    kb = [[InlineKeyboardButton("⛔ Блокировать", callback_data="ban"),
           InlineKeyboardButton("👑 Добавить админа", callback_data="add_adm")]]
    await _msg(update).reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def ban_s(update, ctx):
    await update.callback_query.answer()
    res = supabase.table("users").select("*").eq("is_banned", False).neq("user_id", ADMIN_USER_ID).execute()
    candidates = res.data if res.data else []
    if not candidates:
        await update.callback_query.message.reply_text("Нет.")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{u['name']}", callback_data=f"b_{u['user_id']}")] for u in candidates[:10]]
    kb.append([InlineKeyboardButton("❌", callback_data="b_cancel")])
    await update.callback_query.message.reply_text("Кого?", reply_markup=InlineKeyboardMarkup(kb))
    return BAN_SEL

async def ban_sel(update, ctx):
    q = update.callback_query
    await q.answer()
    if q.data == "b_cancel":
        await q.message.reply_text("Отмена.")
        return ConversationHandler.END
    ctx.user_data["bid"] = int(q.data.replace("b_", ""))
    await q.message.reply_text("Кодовое слово:")
    return BAN_CONF

async def ban_conf(update, ctx):
    if update.message.text.strip() != SECRET_CODE:
        await update.message.reply_text("❌ Неверное кодовое слово.")
        return ConversationHandler.END
    ban_u(ctx.user_data["bid"])
    await update.message.reply_text("✅ Заблокирован.")
    return ConversationHandler.END

async def adm_s(update, ctx):
    await update.callback_query.answer()
    res = supabase.table("users").select("*").eq("is_banned", False).neq("user_id", ADMIN_USER_ID).execute()
    admins_res = supabase.table("users").select("user_id").eq("is_admin", True).execute()
    admin_ids = {row["user_id"] for row in admins_res.data} if admins_res.data else set()
    candidates = [u for u in res.data if u["user_id"] not in admin_ids]
    if not candidates:
        await update.callback_query.message.reply_text("Нет.")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(f"{u['name']}", callback_data=f"a_{u['user_id']}")] for u in candidates[:10]]
    kb.append([InlineKeyboardButton("❌", callback_data="a_cancel")])
    await update.callback_query.message.reply_text("Кого?", reply_markup=InlineKeyboardMarkup(kb))
    return ADM_SEL

async def adm_sel(update, ctx):
    q = update.callback_query
    await q.answer()
    if q.data == "a_cancel":
        await q.message.reply_text("Отмена.")
        return ConversationHandler.END
    ctx.user_data["aid"] = int(q.data.replace("a_", ""))
    await q.message.reply_text("Кодовое слово:")
    return ADM_CONF

async def adm_conf(update, ctx):
    if update.message.text.strip() != SECRET_CODE:
        await update.message.reply_text("❌ Неверное кодовое слово.")
        return ConversationHandler.END
    promote(ctx.user_data["aid"])
    await update.message.reply_text("✅ Админ! 👑")
    return ConversationHandler.END

# ====== НАПОМИНАНИЯ ======
async def reminder(ctx):
    now = datetime.now()
    if now.day == 15:
        rm = 12 if now.month == 1 else now.month - 1
        ry = now.year - 1 if now.month == 1 else now.year
        try:
            await ctx.bot.send_message(ADMIN_USER_ID, f"📋 Пора внести расш. отчёт за *{MN[rm]} {ry}*", parse_mode="Markdown")
        except:
            pass

async def cancel(update, ctx):
    await update.message.reply_text("❌ /start")
    return ConversationHandler.END

# ====== ROUTER ======
async def router(update, ctx):
    q = update.callback_query
    cb = q.data
    if cb == "dash_m":
        await dash_m(update, ctx)
    elif cb == "dash_y":
        await dash_y(update, ctx)
    elif cb == "multi_y":
        await multi_y(update, ctx)
    elif cb == "summary":
        await summary_m(update, ctx)
    elif cb == "manage":
        await manage(update, ctx)
    elif cb == "my_premium":
        await my_prem(update, ctx)
    elif cb.startswith("prem_"):
        await prem_calc(update, ctx)
    elif cb == "history":
        await hist_s(update, ctx)
    elif cb.startswith("hist_"):
        await hist_y_cb(update, ctx)
    elif cb == "view_ext":
        await q.answer()
        now = datetime.now()
        rm = 12 if now.month == 1 else now.month - 1
        ry = now.year - 1 if now.month == 1 else now.year
        r = get_extended_report(ry, rm)
        if not r:
            await q.message.reply_text(f"📋 Нет данных за {MN[rm]} {ry}.")
        else:
            tp = r.get("total_payments", 0)
            nac = r.get("new_avg_check", 0)
            rac = r.get("repeat_avg_check", 0)
            tpr = r.get("total_profitability_pct", 0)
            await q.message.reply_text(
                f"📋 *{MN[rm]} {ry}*\n\n💰 Итого: {tp:,.0f} ₽\n"
                f"👤 Новые: {r.get('new_payments',0):,.0f} ₽ ({r.get('new_count',0)} шт, ср.чек {nac:,.0f})\n"
                f"🔄 Пост.: {r.get('repeat_payments',0):,.0f} ₽ ({r.get('repeat_count_report',0)} шт, ср.чек {rac:,.0f})\n"
                f"📈 Рент: {tpr:.1f}%", parse_mode="Markdown"
            )
    else:
        await q.answer()

# ====== WEB API SERVER (ИСПРАВЛЕНА ПОДДЕРЖКА USER ID) ======
import hashlib, hmac, urllib.parse
from aiohttp import web
from aiohttp_middlewares import cors_middleware

def verify_telegram_data(init_data_str, bot_token):
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data_str))
        check_hash = parsed.pop("hash", "")
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, check_hash)
    except Exception:
        return False

def extract_user_id(init_data_str):
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data_str))
        import json as _json
        user = _json.loads(parsed.get("user", "{}"))
        return user.get("id")
    except Exception:
        return None

def build_api_response(user_id):
    u = get_user(user_id)
    if not u:
        return {"error": "not_registered"}
    now = datetime.now()
    cm_data = None
    try:
        md = get_month_data(now.year, now.month)
        if md["plan_payments"] > 0:
            t = mtotals(md, now.year, now.month)
            cm_data = {
                "year": now.year, "month": now.month, "month_name": MN[now.month],
                "plan_payments": t["pp"], "plan_profitability_pct": t["ppr"],
                "fact_payments": t["fp"], "fact_profitability_pct": t["fpr"],
                "pct_pay": t["pctp"], "pct_prof": t["pctpr"],
                "lag_pay": t["lag"], "lag_prof_pp": t["lagpr"],
                "daily_needed": t["dn"], "avg_daily": t["avgd"],
                "elapsed": t["elapsed"], "remaining": t["remaining"],
                "total_days": t["td"],
                "is_behind": t["behind"], "is_ahead": t["ahead"],
                "daily_facts": {str(k): v for k, v in t["df"].items()},
                "cumulative_entries": md.get("cumulative_entries", []),
                "pct_today": t["pct_today"]
            }
    except Exception:
        pass
    cy_data = None
    try:
        yp = get_year_plan(now.year)
        if yp["year_plan_payments"] > 0:
            yt = ytotals(now.year)
            cy_data = {
                "year": now.year,
                "year_plan_payments": yt["ypp"],
                "year_plan_profitability_pct": yt["ypr"],
                "total_fact": yt["fp"], "avg_prof": yt["ap"],
                "pct_pay": yt["pctp"],
                "monthly": [{"month": m["m"], "name": m["n"], "plan": m["plan"],
                             "fact": m["fact"], "pct": m["pct"], "prof": m["prof"]} for m in yt["mr"]],
            }
    except Exception:
        pass
    years_data = {}
    for year in get_all_years():
        try:
            yt = ytotals(year)
            years_data[str(year)] = {
                "year": year, "year_plan_payments": yt["ypp"],
                "total_fact": yt["fp"], "pct_pay": yt["pctp"], "avg_prof": yt["ap"],
            }
        except Exception:
            pass
    ext_reports = []
    reports_dict = get_all_extended_reports()
    for period, data in sorted(reports_dict.items()):
        data["period"] = period
        ext_reports.append(data)
    return {
        "user_name": dname(user_id),
        "user_role": u.get("position", ""),
        "is_admin": is_admin(user_id),
        "current_month": cm_data,
        "current_year": cy_data,
        "years": years_data,
        "extended_reports": ext_reports,
    }

async def handle_api_data(request):
    if request.method == "OPTIONS":
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })
    try:
        body = await request.json()
        init_data = body.get("initData")
        user_id = body.get("userId")

        # Определяем способ аутентификации
        if init_data:
            # Из Telegram Mini App
            if not verify_telegram_data(init_data, BOT_TOKEN):
                return web.json_response({"error": "unauthorized"}, status=403,
                                         headers={"Access-Control-Allow-Origin": "*"})
            user_id = extract_user_id(init_data)
            if not user_id:
                return web.json_response({"error": "no_user"}, status=400,
                                         headers={"Access-Control-Allow-Origin": "*"})
        elif user_id is not None:
            # Из PWA/браузера – передали userId
            # Проверяем, зарегистрирован ли пользователь
            if not is_reg(int(user_id)):
                return web.json_response({"error": "not_registered"}, status=403,
                                         headers={"Access-Control-Allow-Origin": "*"})
            user_id = int(user_id)
        else:
            return web.json_response({"error": "no_credentials"}, status=400,
                                     headers={"Access-Control-Allow-Origin": "*"})

        if is_banned(user_id):
            return web.json_response({"error": "banned"}, status=403,
                                     headers={"Access-Control-Allow-Origin": "*"})

        result = build_api_response(user_id)
        return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logging.error(f"API error: {e}")
        return web.json_response({"error": str(e)}, status=500,
                                 headers={"Access-Control-Allow-Origin": "*"})

async def handle_root(request):
    return web.Response(text="Bot is alive", status=200)

async def start_api_server():
    app_web = web.Application(middlewares=[cors_middleware(allow_all=True)])
    app_web.router.add_get("/", handle_root)
    app_web.router.add_post("/api/data", handle_api_data)
    app_web.router.add_options("/api/data", handle_api_data)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", API_PORT)
    await site.start()
    logging.info(f"API server started on port {API_PORT}")

# ====== МЕНЮ КОМАНД ======
async def post_init(app):
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Главное меню"),
        BotCommand("dashboard", "Дашборд месяца"),
        BotCommand("summary", "Текущая сводка"),
        BotCommand("year_dashboard", "Дашборд по году"),
        BotCommand("dynamics", "Динамика по годам"),
        BotCommand("history", "История по месяцам/годам"),
        BotCommand("my_premium", "Моя премия (менеджер)"),
        BotCommand("cancel", "Отменить текущее действие"),
    ]
    await app.bot.set_my_commands(commands)
    await app.bot.set_chat_menu_button(menu_button=None)

# ====== MAIN ======
def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_POSITION: [CallbackQueryHandler(reg_pos, pattern="^pos_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)], allow_reentry=True
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("set_plan", set_plan_s), CallbackQueryHandler(set_plan_s, pattern="^set_plan$")],
        states={SET_PLAN_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_pay)],
                SET_PLAN_PROF: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_prof)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("set_year_plan", yplan_s), CallbackQueryHandler(yplan_s, pattern="^year_plan$")],
        states={SET_YPLAN_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, yplan_year)],
                SET_YPLAN_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, yplan_pay)],
                SET_YPLAN_PROF: [MessageHandler(filters.TEXT & ~filters.COMMAND, yplan_prof)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add_fact", fact_s), CallbackQueryHandler(fact_s, pattern="^add_fact$")],
        states={SET_FACT_CUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, fact_cum)],
                SET_FACT_PROF: [MessageHandler(filters.TEXT & ~filters.COMMAND, fact_prof)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("retro", retro_s), CallbackQueryHandler(retro_s, pattern="^retro$")],
        states={RETRO_SEL_YEAR: [CallbackQueryHandler(retro_year, pattern="^ry_")],
                RETRO_SEL_MONTH: [CallbackQueryHandler(retro_month, pattern="^rm_")],
                RETRO_SEL_FIELD: [CallbackQueryHandler(retro_field, pattern="^rf_")],
                RETRO_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, retro_val)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("ext_report", ext_s), CallbackQueryHandler(ext_s, pattern="^ext_report$")],
        states={
            EXT_SEL_YEAR: [CallbackQueryHandler(ext_sel_year, pattern="^ext_year_")],
            EXT_SEL_MONTH: [CallbackQueryHandler(ext_sel_month, pattern="^ext_month_")],
            EXT_NEW_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_np)],
            EXT_REP_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_rp)],
            EXT_NEW_CNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_nc)],
            EXT_RCR: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_rcr)],
            EXT_RCF: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_rcf)],
            EXT_NPROF: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_nprof)],
            EXT_RPROF: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_rprof)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(ban_s, pattern="^ban$")],
        states={BAN_SEL: [CallbackQueryHandler(ban_sel)], BAN_CONF: [MessageHandler(filters.TEXT & ~filters.COMMAND, ban_conf)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_s, pattern="^add_adm$")],
        states={ADM_SEL: [CallbackQueryHandler(adm_sel)], ADM_CONF: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_conf)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    app.add_handler(CommandHandler("dashboard", dash_m))
    app.add_handler(CommandHandler("year_dashboard", dash_y))
    app.add_handler(CommandHandler("dynamics", multi_y))
    app.add_handler(CommandHandler("summary", summary_m))
    app.add_handler(CommandHandler("my_premium", my_prem))
    app.add_handler(CommandHandler("history", hist_s))
    app.add_handler(CallbackQueryHandler(router))

    app.job_queue.run_daily(reminder, time=datetime.strptime("09:00", "%H:%M").time())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_api_server())

    print("🤖 Бот v3.9 (поддержка userId, исправлена сводка) запущен!")
    print(f"🌐 API сервер: http://localhost:{API_PORT}/api/data")
    print(f"📱 WebApp URL: {WEBAPP_URL}")
    print("📋 Команды зарегистрированы в меню Telegram.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()