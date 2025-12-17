import sqlite3
import os
import re

def parse_and_fill_db(filename="content.txt"):
    if not os.path.exists(filename):
        print(f"Файл {filename} не найден!")
        return

    conn = sqlite3.connect('murphy.db')
    cursor = conn.cursor()

    # Очищаем базу перед обновлением
    cursor.execute("DELETE FROM units")
    cursor.execute("DELETE FROM exercises")

    with open(filename, 'r', encoding='utf-8') as file:
        # Разбиваем файл на блоки по слову Юнит или UNIT
        raw_content = file.read()
        blocks = re.split(r'(?i)UNIT:|ЮНИТ:', raw_content)
        
        for block in blocks:
            if not block.strip():
                continue
            
            lines = [line.strip() for line in block.strip().split('\n') if line.strip()]
            
            try:
                # Извлекаем только цифры из первой строки (ID юнита)
                unit_id = int(re.search(r'\d+', lines[0]).group())
                
                # Извлекаем заголовок, теорию и упражнения
                title = ""
                theory = ""
                exercises_list = []
                
                current_section = None
                for line in lines[1:]:
                    if line.upper().startswith('TITLE:') or line.upper().startswith('ЗАГОЛОВОК:'):
                        title = line.split(':', 1)[1].strip()
                    elif line.upper().startswith('THEORY:') or line.upper().startswith('ТЕОРИЯ:'):
                        theory = line.split(':', 1)[1].strip()
                    elif line == '---':
                        continue
                    elif '|' in line:
                        exercises_list.append(line)
                    else:
                        # Если строка идет после теории, добавляем её к теории
                        theory += " " + line

                # Сохраняем Юнит
                cursor.execute("INSERT INTO units (id, title, theory_text) VALUES (?, ?, ?)", 
                               (unit_id, title, theory))
                
                # Сохраняем упражнения
                for ex in exercises_list:
                    q, a = ex.split('|')
                    cursor.execute("INSERT INTO exercises (unit_id, question, correct_answer) VALUES (?, ?, ?)", 
                                   (unit_id, q.strip(), a.strip()))
                
                print(f"✅ Обработан Юнит {unit_id}: {title}")

            except Exception as e:
                print(f"❌ Ошибка в блоке Юнита: {e}")
                continue

    conn.commit()
    conn.close()
    print("\n🚀 База данных готова! Теперь запускай bot.py")

if __name__ == "__main__":
    parse_and_fill_db()