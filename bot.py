import asyncio
import sqlite3
import logging
import sys
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

# Полный список юнитов для меню
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

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    """Создает таблицы, если их нет, но НЕ удаляет данные парсера"""
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
    # Берем случайное упражнение для конкретного юнита
    cursor.execute("SELECT question, correct_answer FROM exercises WHERE unit_id = ? ORDER BY RANDOM() LIMIT 1", (unit_id,))
    res = cursor.fetchone()
    conn.close()
    return res

# --- КЛАВИАТУРЫ ---
def build_main_menu():
    builder = []
    u_ids = sorted(list(GRAMMAR_UNITS.keys()))
    for i in range(0, len(u_ids), 2):
        row = [InlineKeyboardButton(text=f"Unit {u_ids[i]}", callback_data=f"unit:{u_ids[i]}")]
        if i + 1 < len(u_ids):
            row.append(InlineKeyboardButton(text=f"Unit {u_ids[i+1]}", callback_data=f"unit:{u_ids[i+1]}"))
        builder.append(row)
    return InlineKeyboardMarkup(inline_keyboard=builder)

# --- ОБРАБОТЧИКИ ---
router = Router()

@router.message(CommandStart())
async def start(message: Message):
    await message.answer("📚 <b>English Grammar in Use (Murphy)</b>\nВыберите интересующий юнит:", reply_markup=build_main_menu())

@router.callback_query(F.data.startswith("unit:"))
async def show_unit(callback: CallbackQuery):
    unit_id = int(callback.data.split(":")[1])
    data = db_get_unit(unit_id)
    
    if data:
        text = f"📘 <b>{data[0]}</b>\n\n{data[1]}"
    else:
        # Если в БД нет текста, берем заголовок из словаря
        name = GRAMMAR_UNITS.get(unit_id, f"Unit {unit_id}")
        text = f"📘 <b>{name}</b>\n\n⚠️ Теория для этого раздела еще не загружена через parser.py."
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Начать практику", callback_data=f"practice:{unit_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
    ])
    await callback.message.edit_text(text=text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "back_to_list")
async def back_to_list(callback: CallbackQuery):
    await callback.message.edit_text("Выберите юнит:", reply_markup=build_main_menu())
    await callback.answer()

@router.callback_query(F.data.startswith("practice:"))
async def start_practice(callback: CallbackQuery, state: FSMContext):
    unit_id = int(callback.data.split(":")[1])
    ex = db_get_exercise(unit_id)
    
    if ex:
        await state.update_data(correct_answer=ex[1].strip().lower(), unit_id=unit_id)
        await state.set_state(Quiz.waiting_for_answer)
        await callback.message.answer(f"📝 <b>Упражнение (Unit {unit_id}):</b>\n{ex[0]}\n\n<i>Введите правильное слово или фразу:</i>")
    else:
        await callback.message.answer(f"❌ В базе пока нет упражнений для Unit {unit_id}. Загрузите их через parser.py!")
    await callback.answer()

@router.message(Quiz.waiting_for_answer)
async def check_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    correct = data.get("correct_answer")
    unit_id = data.get("unit_id")
    
    user_answer = message.text.strip().lower()
    
    if user_answer == correct:
        await message.answer("✅ <b>Верно!</b> Вы молодец.")
    else:
        await message.answer(f"❌ <b>Не совсем.</b>\nПравильный ответ: <code>{correct}</code>")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Еще одно задание", callback_data=f"practice:{unit_id}")],
        [InlineKeyboardButton(text="📘 Вернуться к теории", callback_data=f"unit:{unit_id}")]
    ])
    await message.answer("Продолжим обучение?", reply_markup=kb)
    await state.clear()

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    init_db() 
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nБот остановлен.")