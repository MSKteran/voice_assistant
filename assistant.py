import tkinter as tk
import speech_recognition as sr
import threading
import webbrowser
import os
from gtts import gTTS
import pygame
import requests
import pymorphy3
import re

# Настройки ассистента
assistant_name = "Ассистент"
openweather_api_key = "79d1ca96933b0328e1c7e3e7a26cb347"

# Инициализация библиотеки для морфологического анализа
morph = pymorphy3.MorphAnalyzer(lang='ru')

# Глобальная переменная для режима
is_voice_mode = False  # Режим по умолчанию: текстовый

# Список приложений
app_list = {
    ("блокнот", "notepad",): r"C:\Windows\System32\notepad.exe",
    ("калькулятор",): r"C:\Windows\System32\calc.exe",
    ("браузер", "яндекс",): r"C:\Users\admin\AppData\Local\Yandex\YandexBrowser\Application\browser.exe",
    ("офис", "word",): r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
}

# Список известных сайтов
site_list = {
    ("вконтакте", "вк"): "https://www.vk.com",
}

# Функция озвучивания текста
def speak(text):
    print(f"{assistant_name}: {text}")
    update_ui(f"{assistant_name}: {text}")
    audio_file = "assistant_response.mp3"
    tts = gTTS(text=text, lang="ru")
    tts.save(audio_file)

    pygame.mixer.init()
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        continue

    pygame.mixer.music.stop()
    pygame.mixer.quit()
    try:
        os.remove(audio_file)
    except PermissionError:
        print("Не удалось удалить файл аудио.")

# Падежи для города
def normalize_text(text, case):
    try:
        parsed = morph.parse(text)[0]
        if case in {"nomn", "loct"}:
            return parsed.inflect({case}).word.capitalize()
    except AttributeError:
        return text.capitalize()

# Функция обработки погоды
def handle_weather(command):
    city = re.sub(r"\bв\b", "", command.replace("погода", "").strip()).strip()
    if not city:
        city = "Москва"
    city_nominative = normalize_text(city, "nomn")  # Для API
    city_prepositional = normalize_text(city, "loct")  # Для озвучивания
    weather, _ = get_weather(city_nominative)
    if weather:
        speak(f"Погода в {city_prepositional}: {weather}.")
    else:
        speak("Не удалось получить данные о погоде. Проверьте подключение к интернету.")

# Функция получения погоды
def get_weather(city):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": openweather_api_key, "lang": "ru", "units": "metric"}
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        weather_description = data["weather"][0]["description"].capitalize()
        temperature = data["main"]["temp"]
        temp_phrase = get_proper_degree_phrase(temperature)
        return f"{weather_description}, {temp_phrase}", city
    except requests.exceptions.RequestException:
        return None, city

# Функция для правильного падежа слова "градус"
def get_proper_degree_phrase(temp):
    temp = int(temp)
    if 11 <= abs(temp) % 100 <= 14:
        degree_word = "градусов"
    else:
        last_digit = abs(temp) % 10
        if last_digit == 1:
            degree_word = "градус"
        elif 2 <= last_digit <= 4:
            degree_word = "градуса"
        else:
            degree_word = "градусов"
    return f"{temp} {degree_word} по Цельсию"

# Обработка команд
def process_command(command, is_text_mode=False):
    if is_text_mode or assistant_name.lower() in command:
        command = command.replace(assistant_name.lower(), "").strip()
        if "запусти" in command or "открой" in command:
            open_application(command)
        elif "погода" in command:
            handle_weather(command)
        elif "найди" in command or "загугли" in command:
            search_internet(command)
        elif "перейди на" in command:
            go_to_website(command)
        elif "выход" in command or "пока" in command:
            speak("До свидания!")
            root.quit()
        else:
            speak("Команда не распознана.")
    else:
        update_ui("Обращение не распознано.")

# Функция открытия приложения
def open_application(command):
    for names, app_path in app_list.items():
        if any(name in command for name in names):
            if os.path.exists(app_path):
                os.startfile(app_path)
                speak(f"Запускаю {names[0]}.")
                return
    speak("Приложение не найдено в списке.")

# Функция поиска в интернете
def search_internet(command):
    query = command.replace("найди", "").replace("загугли", "").strip()
    if query:
        words = query.split()
        if words:
            words[0] = normalize_text(words[0], "nomn")
        query = " ".join(words)
        webbrowser.open(f"https://www.google.com/search?q={query}")
        speak(f"Ищу {query} в интернете.")
    else:
        speak("Не указан запрос для поиска.")

# Функция открытия сайта
def go_to_website(command):
    site_name = command.replace("перейди на", "").strip()
    for names, url in site_list.items():
        if any(name in site_name for name in names):
            webbrowser.open(url)
            speak(f"Открываю {names[0]}.")
            return
    webbrowser.open(f"https://www.{site_name}.com")
    speak(f"Пытаюсь открыть {site_name}.")

# Функция для голосового ввода
def listen_continuously():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        update_ui("Слушаю...")
        while is_voice_mode:
            try:
                audio = recognizer.listen(source, timeout=None)  # Без тайм-аута
                command = recognizer.recognize_google(audio, language="ru-RU").lower()
                update_ui(f"Вы: {command}")
                process_command(command)
                update_ui("Слушаю...")  # Обновить после обработки команды
            except sr.UnknownValueError:
                update_ui("Вы: [неразборчиво]")

# Переключение голосового режима
def toggle_voice_mode():
    global is_voice_mode
    is_voice_mode = not is_voice_mode
    if is_voice_mode:
        voice_button.config(bg="green")
        update_ui("Голосовой режим включен.")
        threading.Thread(target=listen_continuously, daemon=True).start()
    else:
        voice_button.config(bg="SystemButtonFace")
        update_ui("Голосовой режим выключен.")

# Обновление интерфейса
def update_ui(text):
    text_area.config(state=tk.NORMAL)
    text_area.insert(tk.END, f"{text}\n")
    text_area.yview(tk.END)
    text_area.config(state=tk.DISABLED)

# Интерфейс
root = tk.Tk()
root.title("Голосовой помощник")

text_area = tk.Text(root, height=10, width=50, wrap=tk.WORD, state=tk.DISABLED)
text_area.pack(padx=20, pady=20)

entry = tk.Entry(root, width=50)
entry.pack(padx=20, pady=10)

def process_text_command(event=None):
    command = entry.get()
    entry.delete(0, tk.END)
    if command:
        update_ui(f"Вы: {command}")
        process_command(command.lower(), is_text_mode=True)

entry.bind("<Return>", process_text_command)

send_button = tk.Button(root, text="Отправить", width=20, height=2, command=process_text_command)
send_button.pack(pady=10)

voice_button = tk.Button(root, text="Голосовой режим", width=20, height=2, command=toggle_voice_mode)
voice_button.pack(pady=10)

speak("Привет! Чем могу помочь?")
root.mainloop()