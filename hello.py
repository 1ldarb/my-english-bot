import datetime
import platform

name = "Ильдар"
current_time = datetime.datetime.now().strftime("%H:%M")
system_info = platform.system()

print(f"Привет, {name}!")
print(f"Сейчас {current_time}. Твой Mac работает на системе {system_info}.")
print("Окружение Python полностью готово к большим проектам!")


