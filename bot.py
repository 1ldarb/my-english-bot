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
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("GOOGLE_API_KEY")
DB_PATH = 'murphy.db'	
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
    """Убирает лишние пробелы, нормализует апострофы и раскрывает сокращения для гибкой проверки."""
    if not text:
        return ""
    
    text = text.strip().lower().replace("’", "'").replace("`", "'")
    
    # Словарь сокращений для приведения к единому виду
    contractions = {
        "isn't": "is not", "aren't": "are not", "wasn't": "was not",
        "weren't": "were not", "don't": "do not", "doesn't": "does not",
        "didn't": "did not", "can't": "cannot", "won't": "will not",
        "it's": "it is", "he's": "he is", "she's": "she is",
        "i'm": "i am", "you're": "you are", "we're": "we are", "they're": "they are"
    }
    
    for short, full in contractions.items():
        text = text.replace(short, full)
        
    return re.sub(r'[.\)]+$', '', text).strip()

async def get_explanation(theory: str, question: str, correct_answer: str, user_answer: str) -> str:
    """Запрашивает умную подсказку у ИИ, учитывая тип предложения."""
    prompt = f"""
    Ты — наставник по английскому. Пользователь ошибся в упражнении.
    
    ЗАДАЧА: Дай ОДНУ очень короткую подсказку-намек на русском (до 15 слов).
    
    ПРАВИЛА:
    1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО называть правильный ответ: "{correct_answer}".
    2. Определи тип предложения (вопрос, отрицание или утверждение) и давай совет только по теме.
    3. Если пользователь добавил лишнее слово (например, подлежащее, которое уже есть в задании), укажи на это.
    4. Будь дружелюбным, но лаконичным.

    Теория: {theory}
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
    text = f"📘 <b>{data[0]}</b>\n\n{data[1]}" if data else f"📘 <b>Unit {unit_id}</b>\n\n⚠️ Теория не найдена."
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
            answered_ids=[ex[0]]
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

    user_raw = message.text
    user_ans = normalize_text(user_raw)
    correct_ans = normalize_text(data.get("correct_answer"))
    question_text = data.get("question_text")
    
    # --- УЛУЧШЕННАЯ ЛОГИКА ПРОВЕРКИ ---
    is_correct = (user_ans == correct_ans)

    # Если не совпало, проверяем, не продублировал ли юзер подлежащее из вопроса
    if not is_correct:
        # Ищем слово перед пропуском (например, "it" в "It ___ raining")
        match = re.search(r'(\w+)\s+_{3,}', question_text)
        if match:
            subject = match.group(1).lower()
            if user_ans.startswith(subject):
                # Проверяем остаток строки после подлежащего
                cleaned_user_ans = user_ans[len(subject):].strip()
                if cleaned_user_ans == correct_ans:
                    is_correct = True

    unit_id = data.get("unit_id")
    current_count = data.get("count")
    total_errors = data.get("errors")
    answered_ids = data.get("answered_ids", [])

    if is_correct:
        if current_count < 10:
            ex = db_get_exercise(unit_id, excluded_ids=answered_ids)
            if not ex:
                await state.clear()
                await message.answer("🎉 Больше заданий нет!")
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
        explanation = await get_explanation(theory_text, question_text, data.get("correct_answer"), user_raw)
        await wait_msg.edit_text(f"❌ <b>Не совсем так</b>\n\n{explanation}", reply_markup=get_quiz_kb(), parse_mode="HTML")

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
