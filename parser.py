import sqlite3
import re
import os

INPUT_FILE = "content.txt"
DB_FILE = "murphy.db"

def setup_db():
    # Создаем базу с чистого листа
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS exercises')
    cursor.execute('DROP TABLE IF EXISTS units')
    
    # Колонки СТРОГО как в вашем bot.py
    cursor.execute('''CREATE TABLE units 
                      (id INTEGER PRIMARY KEY, title TEXT, theory_text TEXT)''')
    cursor.execute('''CREATE TABLE exercises 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       unit_id INTEGER, question TEXT, correct_answer TEXT)''')
    conn.commit()
    return conn

def parse_text_to_db():
    if not os.path.exists(INPUT_FILE):
        print(f"Ошибка: Файл {INPUT_FILE} не найден!")
        return

    conn = setup_db()
    cursor = conn.cursor()

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    units_blocks = re.split(r'Юнит:\s*', content)
    
    count = 0
    for block in units_blocks[1:]:
        try:
            id_match = re.search(r'^(\d+)', block.strip())
            if not id_match: continue
            unit_id = int(id_match.group(1))
            
            theory_match = re.search(r'Теория:(.*?)Упражнения:', block, re.DOTALL)
            theory = theory_match.group(1).strip() if theory_match else ""
            
            cursor.execute("INSERT INTO units (id, title, theory_text) VALUES (?, ?, ?)", 
                           (unit_id, f"Unit {unit_id}", theory))
            
            exercises_part = block.split('Упражнения:')[-1]
            lines = exercises_part.split('\n')
            
            unit_exercises_count = 0
            for line in lines:
                if '|' in line:
                    match = re.search(r'(?:(\d+)\.\s*)?(.+?)\s*\|\s*(.+)', line)
                    if match:
                        q, a = match.group(2).strip(), match.group(3).strip()
                        cursor.execute("INSERT INTO exercises (unit_id, question, correct_answer) VALUES (?, ?, ?)", 
                                       (unit_id, q, a))
                        unit_exercises_count += 1
            
            print(f"✅ Юнит {unit_id} загружен ({unit_exercises_count} упр.)")
            count += 1
        except Exception as e:
            print(f"❌ Ошибка в Юните {unit_id}: {e}")

    conn.commit()
    conn.close()
    print(f"\n🚀 База данных создана успешно!")

if __name__ == "__main__":
    parse_text_to_db()
