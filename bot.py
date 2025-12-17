import asyncio
import sqlite3
import logging
import sys
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8434395340:AAFlXoo3p8wUQiVnK3ySWPpaVysXqRMV3qs"

class Quiz(StatesGroup):
    waiting_for_answer = State()

# Список юнитов
GRAMMAR_UNITS = {
    1: "Present continuous", 2: "Present simple", 
    3: "Cont. / Simple 1", 4: "Cont. / Simple 2",
    5: "Past simple", 6: "Past continuous",
    7: "Present perfect 1", 8: "Present perfect 2",
    9: "Present perfect cont.", 10: "Pres. Perf. vs Simple",
    11: "How long have you...", 12: "For and since",
    13: "Pres. Perf. vs Past 1", 14: "Pres. Perf. vs Past 2",
    15: "Past perfect", 16: "Past perfect cont.",
    17: "Have and have got", 18: "Used to"
}

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (ЧТОБЫ НЕ ВЫКЛЮЧАЛСЯ) ---
async def handle(request):
    return web.Response(text="Bot is alive!")

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('murphy.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY, 
            title TEXT, 
            theory_text TEXT
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            unit_id INTEGER, 
            question TEXT, 
            correct_answer TEXT
        )''')
    conn.commit()
    conn.close()

def db_get_unit(unit_id):
    conn = sqlite3.connect('murphy.db')
    cursor = conn.cursor()
    cursor.execute("SELECT title, theory_text FROM units WHERE id = ?", (unit_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def db_get_exercise(unit_id):
    conn = sqlite3.connect('murphy.db')
    cursor = conn.cursor()
    cursor.execute("SELECT question, correct_answer FROM exercises WHERE unit_id = ? ORDER BY RANDOM() LIMIT 1", (unit_id,))
    res = cursor.fetchone()
    conn.close()
    return res

# --- КЛАВИАТУРЫ ---
def build_main_menu():
    builder =
