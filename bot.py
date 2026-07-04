#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM BOT - КОНТРОЛЬ ПЛАНА ПРОДАЖ v4.3 (общая рентабельность, перезапись extended_reports)
"""

import json, os, logging, asyncio, re, secrets
from datetime import datetime, timedelta, timezone
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

WEBAPP_URL = "https://edik24mp.github.io/otto-app-new/"
PWA_AUTH_URL = WEBAPP_URL.rstrip('/') + "/?token="   # для standalone PWA

API_PORT = 8443

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

# Состояния (добавлен EXT_TPROF)
(
    REG_NAME, REG_POSITION,
    SET_PLAN_PAY, SET_PLAN_PROF,
    SET_YPLAN_YEAR, SET_YPLAN_PAY, SET_YPLAN_PROF,
    SET_FACT_CUM, SET_FACT_PROF,
    RETRO_SEL_YEAR, RETRO_SEL_MONTH, RETRO_SEL_FIELD, RETRO_VALUE,
    EXT_SEL_YEAR, EXT_SEL_MONTH,
    EXT_NEW_PAY, EXT_REP_PAY, EXT_NEW_CNT, EXT_RCR, EXT_RCF, EXT_NPROF, EXT_RPROF, EXT_TPROF,
    BAN_SEL, BAN_CONF, ADM_SEL, ADM_CONF,
) = range(27)

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

# ====== СЕССИИ ДЛЯ PWA ======
SESSION_EXPIRY_DAYS = 30

def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=SESSION_EXPIRY_DAYS)
    supabase.table("sessions").insert({
        "user_id": user_id,
        "token": token,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat()
    }).execute()
    return token

def validate_token(token: str) -> Optional[int]:
    res = supabase.table("sessions").select("*").eq("token", token).execute()
    if not res.data:
        return None
    session = res.data[0]
    expires = datetime.fromisoformat(session["expires_at"])
    now = datetime.now(timezone.utc)
    if expires < now:
        supabase.table("sessions").delete().eq("token", token).execute()
        return None
    new_expiry = now + timedelta(days=SESSION_EXPIRY_DAYS)
    supabase.table("sessions").update({"expires_at": new_expiry.isoformat()}).eq("token", token).execute()
    return session["user_id"]

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
    """Сохраняет или обновляет расширенный отчёт (перезаписывает при совпадении года и месяца)."""
    supabase.table("extended_reports").upsert({
        "year": year,
        "month": month,
        "data": data
    }, on_conflict="year,month").execute()

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

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (без изменений, все mtotals, daily_from_cum и т.д.) ======
# ... (оставлены как в предыдущей версии, для краткости опущены, но в реальном файле должны быть)
# Вставьте сюда все функции от days_in до ytotals, gen_month_dash, gen_year_dash, gen_multi_year

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

# ====== /start (без изменений) ======
# ... (вставьте полную функцию start из предыдущей версии)

# ====== РЕГИСТРАЦИЯ (без изменений) ======
# ... (все функции регистрации)

# ====== ПЛАН МЕСЯЦА (без изменений) ======
# ... (set_plan_s, plan_pay, plan_prof)

# ====== ГОДОВОЙ ПЛАН (без изменений) ======
# ... (yplan_s, yplan_year, yplan_pay, yplan_prof)

# ====== ФАКТ (без изменений, дата факта теперь last_reported_day) ======
# ... (fact_s, fact_cum, fact_prof) – используются версии из v4.2

# ====== РЕТРО-ВВОД (без изменений) ======
# ... (retro_s, retro_year, retro_month, retro_field, retro_val)

# ====== ДАШБОРДЫ, СВОДКА, ИСТОРИЯ, ПРЕМИЯ (без изменений) ======
# ... (dash_m, dash_y, multi_y, summary_m, hist_s, hist_y_cb, my_prem, prem_calc)

# ====== РАСШ. ОТЧЁТ (ИЗМЕНЁН) ======
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
    """Сохраняет рентабельность постоянных, запрашивает общую."""
    required = ["enp", "erp", "enc", "ercr", "ercf", "enpr"]
    missing = [k for k in required if k not in ctx.user_data]
    if missing:
        await update.message.reply_text(
            f"❌ Не все данные заполнены. Отсутствуют: {', '.join(missing)}.\n"
            "Пожалуйста, начните расширенный отчёт заново (/ext_report).",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    try:
        v = _extract_number(update.message.text)
    except:
        await update.message.reply_text("❌ Введите рентабельность числом (например, 18.5)")
        return EXT_RPROF

    ctx.user_data["erpr"] = v
    await update.message.reply_text("📊 *Общая рентабельность* (%):", parse_mode="Markdown")
    return EXT_TPROF

async def e_tprof(update, ctx):
    """Получает общую рентабельность и сохраняет весь расширенный отчёт."""
    required = ["enp", "erp", "enc", "ercr", "ercf", "enpr", "erpr"]
    missing = [k for k in required if k not in ctx.user_data]
    if missing:
        await update.message.reply_text(
            f"❌ Не все данные заполнены. Отсутствуют: {', '.join(missing)}.\n"
            "Пожалуйста, начните расширенный отчёт заново (/ext_report).",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    try:
        tpr = _extract_number(update.message.text)
    except:
        await update.message.reply_text("❌ Введите общую рентабельность числом (например, 18.5)")
        return EXT_TPROF

    try:
        y = ctx.user_data["ext_year"]
        m = ctx.user_data["ext_month"]
        np_ = ctx.user_data["enp"]
        rp_ = ctx.user_data["erp"]
        tp_ = np_ + rp_
        nac = np_ / ctx.user_data["enc"] if ctx.user_data["enc"] else 0
        rac = rp_ / ctx.user_data["ercr"] if ctx.user_data["ercr"] else 0
        data = {
            "new_payments": np_, "repeat_payments": rp_, "total_payments": tp_,
            "new_count": ctx.user_data["enc"], "repeat_count_report": ctx.user_data["ercr"],
            "repeat_count_fact": ctx.user_data["ercf"],
            "new_avg_check": nac, "repeat_avg_check": rac,
            "new_profitability_pct": ctx.user_data["enpr"],
            "repeat_profitability_pct": ctx.user_data["erpr"],
            "total_profitability_pct": tpr
        }
        set_extended_report(y, m, data)
        await update.message.reply_text(
            f"✅ *{MN[m]} {y}*\n💰 {tp_:,.0f} ₽\n"
            f"📈 Рент. новых: {ctx.user_data['enpr']:.2f}%\n"
            f"📈 Рент. пост.: {ctx.user_data['erpr']:.2f}%\n"
            f"📊 Общая рент.: {tpr:.2f}%",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"e_tprof error: {e}")
        await update.message.reply_text(f"❌ Ошибка при сохранении: {e}")
        return EXT_TPROF

# ====== УПРАВЛЕНИЕ, НАПОМИНАНИЯ, ROUTER, API, MAIN (добавлен EXT_TPROF) ======
# ... (функции manage, ban, adm, reminder, cancel, router, handle_api_data, start_api_server, post_init)

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ... (все остальные обработчики)
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
            EXT_TPROF: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_tprof)],   # новый шаг
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    # ... (остальное)

if __name__ == "__main__":
    main()