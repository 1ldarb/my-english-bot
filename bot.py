import asyncio
import logging
import sqlite3
import os
import re
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from langchain_google_genai import ChatGoogleGenerativeAI

# --- НАСТРОЙКИ ---
load_dotenv('/home/opc/my-english-bot/.env')
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("GOOGLE_API_KEY")
DB_PATH = '/home/opc/my-english-bot/murphy.db'
UNITS_PER_PAGE = 10 

logging.basicConfig(level=logging.INFO)

# Инициализация AI (Gemini)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash", 
    google_api_key=API_KEY
)

class Quiz(StatesGroup):
    waiting_for_answer = State()

router = Router()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def normalize_text(text: str) -> str:
    """Убирает лишние пробелы, приводит к нижнему регистру и нормализует апострофы."""
    if not text:
        return ""
    # Заменяем все виды апострофов и убираем точки/скобки в конце для гибкости UX
    text = text.strip().lower().replace("’", "'").replace("`", "'")
    return re.sub(r'[.\)]+$', '', text).strip()

async def get_explanation(theory: str, question: str, correct_answer: str, user_answer: str) -> str:
    """Запрашивает подсказку у ИИ БЕЗ называния правильного ответа."""
    prompt = f"""
    Ты — наставник по английскому. Пользователь ошибся.
    ЗАДАЧА: Дай ОДНУ короткую подсказку-намек на русском, чтобы пользователь сам исправил ошибку.
    
    ПРАВИЛА:
    1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО называть правильный ответ или форму глагола (не пиши "{correct_answer}").
    2. Если пользователь прав по смыслу, но ошибся в лишнем слове (которое уже есть в вопросе), намекни на это.
    3. Будь краток (1-2 коротких предложения).

    Правило: {theory}
    Задание: {question}
    Ответ пользователя: {user_answer}
    """
    try:
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=12)
        return response.content
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "Проверь форму глагола и попробуй еще раз!"

def get_quiz_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="💡 Показать ответ", callback_data="show_answer"))
    builder.add(InlineKeyboardButton(text="⬅️ Выйти", callback_data="back_to_list"))
    return builder.as_markup()

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---

def db_get_unit(unit_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, theory_text FROM units WHERE id = ?", (unit_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def db_get_exercise(unit_id, excluded_ids=None):
    """Получает случайное упражнение, исключая уже пройденные."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if excluded_ids and len(excluded_ids) > 0:
        placeholders = ', '.join('?' for _ in excluded_ids)
        query = f"SELECT id, question, answer FROM exercises WHERE unit_id = ? AND id NOT IN ({placeholders}) ORDER BY RANDOM() LIMIT 1"
        cursor.execute(query, (unit_id, *excluded_ids))
    else:
        cursor.execute("SELECT id, question, answer FROM exercises WHERE unit_id = ? ORDER BY RANDOM() LIMIT 1", (unit_id,))
    
    res = cursor.fetchone()
    conn.close()
    return res

def get_units_page(page: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM units")
    total = cursor.fetchone()[0]
    offset = page * UNITS_PER_PAGE
    cursor.execute("SELECT id FROM units ORDER BY id ASC LIMIT ? OFFSET ?", (UNITS_PER_PAGE, offset))
    units = cursor.fetchall()
    conn.close()
    return units, total

# --- ГЕНЕРАТОР КЛАВИАТУРЫ МЕНЮ ---

def get_units_kb(page: int):
    units, total_count = get_units_page(page)
    builder = InlineKeyboardBuilder()
    for unit in units:
        builder.add(InlineKeyboardButton(text=f"Unit {unit[0]}", callback_data=f"unit:{unit[0]}"))
    builder.adjust(2)
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"page:{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page+1} / {(total_count // UNITS_PER_PAGE) + 1}", callback_data="ignore"))
    if (page + 1) * UNITS_PER_PAGE < total_count:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"page:{page+1}"))
    builder.row(*nav_row)
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = (
        "<b>Привет! Я твой персональный AI-репетитор по английскому. 🇬🇧</b>\n\n"
        "Я помогу тебе освоить грамматику по методике <b>Raymond Murphy</b>.\n\n"
        "<b>Как это работает:</b>\n"
        "1. Выбираешь юнит в меню.\n"
        "2. Читаешь теорию.\n"
        "3. Решаешь 10 заданий.\n\n"
        "🤖 Мой ИИ поможет тебе разобраться в ошибках, не давая готовых ответов!"
    )
    await message.answer(welcome_text, reply_markup=get_units_kb(0), parse_mode="HTML")

@router.callback_query(F.data.startswith("page:"))
async def change_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=get_units_kb(page))
    await callback.answer()

@router.callback_query(F.data.startswith("unit:"))
async def show_unit(callback: CallbackQuery):
    unit_id = int(callback.data.split(":")[1])
    data = db_get_unit(unit_id)
    if data:
        text = f"📘 <b>{data[0]}</b>\n\n{data[1]}"
    else:
        text = f"📘 <b>Unit {unit_id}</b>\n\n⚠️ Теория не найдена."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Практика (10 заданий)", callback_data=f"practice:{unit_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_list")]
    ])
    await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_to_list")
async def back_to_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("📚 <b>Выберите юнит:</b>", reply_markup=get_units_kb(0), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("practice:"))
async def start_practice(callback: CallbackQuery, state: FSMContext):
    unit_id = int(callback.data.split(":")[1])
    ex = db_get_exercise(unit_id)
    if ex:
        await state.update_data(
            correct_answer=ex[2], 
            unit_id=unit_id,
            question_text=ex[1],
            count=1,
            errors=0,
            answered_ids=[ex[0]] # Запоминаем ID первого задания
        )
        await state.set_state(Quiz.waiting_for_answer)
        await callback.message.answer(f"<b>Задание 1/10</b>\n\n📝 {ex[1]}", reply_markup=get_quiz_kb(), parse_mode="HTML")
    else:
        await callback.message.answer("⚠️ Упражнения не найдены.")
    await callback.answer()

@router.callback_query(F.data == "show_answer")
async def handle_show_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ans = data.get("correct_answer")
    await state.update_data(errors=data.get("errors", 0) + 1)
    await callback.message.answer(f"💡 Правильный ответ: <code>{ans}</code>", parse_mode="HTML")
    await callback.answer()

@router.message(Quiz.waiting_for_answer)
async def check_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    if not message.text: return

    user_ans = normalize_text(message.text)
    correct_ans = normalize_text(data.get("correct_answer"))
    unit_id = data.get("unit_id")
    current_count = data.get("count")
    total_errors = data.get("errors")
    answered_ids = data.get("answered_ids", [])

    # Лояльная проверка: если в базе "She's having", а юзер ввел "having", или наоборот
    if user_ans == correct_ans or (len(user_ans) > 3 and user_ans in correct_ans):
        if current_count < 10:
            ex = db_get_exercise(unit_id, excluded_ids=answered_ids)
            if not ex: # Если вдруг кончились задания
                await state.clear()
                await message.answer("🎉 Больше заданий нет! Вы прошли всё доступное.")
                return
                
            answered_ids.append(ex[0])
            new_count = current_count + 1
            await state.update_data(
                question_text=ex[1],
                correct_answer=ex[2],
                count=new_count,
                answered_ids=answered_ids
            )
            await message.answer(f"✅ <b>Правильно!</b>\n\n<b>Задание {new_count}/10</b>\n📝 {ex[1]}", reply_markup=get_quiz_kb(), parse_mode="HTML")
        else:
            await state.clear()
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Следующий юнит", callback_data=f"unit:{unit_id + 1}")],
                [InlineKeyboardButton(text="📚 В меню", callback_data="back_to_list")]
            ])
            await message.answer(f"🎉 <b>Юнит {unit_id} пройден!</b>\nОшибок: {total_errors}", reply_markup=kb, parse_mode="HTML")
    else:
        await state.update_data(errors=total_errors + 1)
        unit_data = db_get_unit(unit_id)
        theory_text = unit_data[1] if unit_data else ""
        
        wait_msg = await message.answer("🤔 Анализирую...")
        explanation = await get_explanation(theory_text, data.get("question_text"), data.get("correct_answer"), message.text)
        await wait_msg.edit_text(f"❌ <b>Не совсем так</b>\n\n{explanation}", reply_markup=get_quiz_kb(), parse_mode="HTML")

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
