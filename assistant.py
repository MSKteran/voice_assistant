import os
import webbrowser
import speech_recognition as sr
import requests
import pymorphy2
import re
import json
from gtts import gTTS
# Убираю рекламу pygame
# Эта команда может закрашить при использовании exe файлом. Если так будет, удалить
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

# Настройки ассистента
assistant_name = "Ассистент"
openweather_api_key = "79d1ca96933b0328e1c7e3e7a26cb347"  # Ваш API-ключ

# Инициализация pymorphy2
morph = pymorphy2.MorphAnalyzer()

# Ручной список приложений с несколькими названиями
app_list = {
    ("блокнот", "нотпад",): r"C:\Windows\System32\notepad.exe",
    ("калькулятор",): r"C:\Windows\System32\calc.exe",
    ("браузер", "яндекс",): r"C:\Users\admin\AppData\Local\Yandex\YandexBrowser\Application\browser.exe",
    ("офис", "word",): r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
}

# Ручной список известных сайтов
site_list = {
    "вконтакте": "https://www.vk.com",
}

# Функция для определения города по геолокации
def get_location_from_ip(default_city):
    try:
        response = requests.get("http://ip-api.com/json/", params={"lang": "ru"}, timeout=5)
        response.raise_for_status()
        data = response.json()
        city = data.get("city")
        if city:
            return city
    except requests.exceptions.RequestException:
        pass  # Если не удалось определить город, используем город по умолчанию
    return default_city


# Обновляем начальную настройку города
location = get_location_from_ip("Москва")  # Город по умолчанию

# Функция для озвучивания текста
def speak(text):
    print(f"{assistant_name}: {text}")
    audio_file = "assistant_response.mp3"
    tts = gTTS(text=text, lang="ru")
    tts.save(audio_file)

    # Воспроизведение через pygame
    pygame.mixer.init()
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():  # Ждём завершения воспроизведения
        continue

    # Явная остановка и завершение работы pygame
    pygame.mixer.music.stop()
    pygame.mixer.quit()

    # Удаление файла
    try:
        os.remove(audio_file)
    except PermissionError:
        print("Не удалось удалить файл аудио. Возможно, он ещё используется.")

# Функция для преобразования города или запроса
def normalize_text(text, case):
    try:
        parsed = morph.parse(text)[0]
        if case == "nomn":
            return parsed.inflect({"nomn"}).word.capitalize()
        elif case == "loct":
            return parsed.inflect({"loct"}).word.capitalize()
    except AttributeError:
        return text.capitalize()

# Выбор правильного падежа для "градус"
def get_proper_degree_phrase(temp):
    temp = int(temp)
    if 11 <= abs(temp) % 100 <= 14:  # Исключения для 11-14
        degree_word = "градусов"
    else:
        last_digit = abs(temp) % 10
        if last_digit == 1:
            degree_word = "градус"
        elif 2 <= last_digit <= 4:
            degree_word = "градуса"
        else:
            degree_word = "градусов"

    return f"{temp} {degree_word} по цельсию"

# Функция для получения текущей погоды через OpenWeather
def get_weather(city):
    city_nominative = normalize_text(city, "nomn")  # Преобразование в именительный падеж
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city_nominative,
            "appid": openweather_api_key,
            "lang": "ru",
            "units": "metric"
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()  # Проверка на успешный запрос
        data = response.json()
        weather_description = data["weather"][0]["description"].capitalize()
        temperature = data["main"]["temp"]
        temp_phrase = get_proper_degree_phrase(temperature)
        return f"{weather_description}, {temp_phrase}", city
    except requests.exceptions.RequestException:
        return None, city

# Функция для обработки запроса погоды
def handle_weather(command):
    # Удаление предлогов, таких как "в"
    city = re.sub(r"\bв\b", "", command.replace("погода", "").strip()).strip()
    if not city:
        city = location  # Если город не указан, использовать город по умолчанию

    weather, normalized_city = get_weather(city)
    if weather:
        city_locative = normalize_text(normalized_city, "loct")  # Преобразование в предложный падеж
        speak(f"Погода в {city_locative}: {weather}.")
    else:
        speak("Не удалось получить данные о погоде. Проверьте подключение к интернету.")

# Функция для распознавания речи
def listen_continuously():
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.5  # Увеличение времени ожидания между словами, но все равно иногда не распознает
    with sr.Microphone() as source:
        print(f"{assistant_name} слушает...")
        while True:
            try:
                audio = recognizer.listen(source, timeout=None)
                command = recognizer.recognize_google(audio, language='ru-RU').lower()
                print(f"Распознанный текст: {command}")  # Вывод текста из микрофона
                if assistant_name.lower() in command:
                    return command.replace(assistant_name.lower(), "").strip()
            except sr.UnknownValueError:
                continue  # Игнорировать шум
            except sr.RequestError:
                speak("Проблема с подключением к интернету.")
                break
    return ""

# Функция запуска приложения из ручного списка
def open_application(command):
    for names, app_path in app_list.items():
        if any(name in command for name in names):
            if os.path.exists(app_path):
                os.startfile(app_path)
                speak(f"Запускаю {names[0]}.")
                return
            else:
                speak(f"Приложение {names[0]} не найдено по указанному пути.")
                return
    speak("Приложение не найдено в списке.")

# Функция для перехода на сайт
def go_to_website(command):
    site_name = command.replace("перейди на", "").strip()
    if not site_name:
        speak("Не удалось найти сайт. Укажите название.")
        return
    if site_name in site_list:
        webbrowser.open(site_list[site_name])
        speak(f"Открываю {site_name}.")
    else:
        webbrowser.open(f"https://www.{site_name}.com")
        speak(f"Пытаюсь открыть {site_name}.")

# Функция для поиска в интернете
def search_internet(command):
    query = command.replace("найди", "").replace("загугли", "").strip()
    words = query.split()
    if words:
        query = " ".join([normalize_text(words[0], "nomn")] + words[1:])
        webbrowser.open(f"https://www.google.com/search?q={query}")
        speak(f"Ищу {query} в интернете.")
    else:
        speak("Не указан запрос для поиска.")

# Завершение программы
def exit_program():
    speak("До свидания!")
    exit()

# Функция обработки команд
def process_command(command):
    if "запусти" in command or "открой" in command:
        open_application(command)
    elif "погода" in command:
        handle_weather(command)
    elif "найди" in command or "загугли" in command:
        search_internet(command)
    elif "перейди на" in command:
        go_to_website(command)
    elif "выход" in command or "стоп" in command or "пока" in command:
        speak("До свидания!")
        exit()
    else:
        speak("Команда не распознана.")

# Главный цикл программы
if __name__ == "__main__":
    speak(f"Здравствуйте! Вы можете обращаться ко мне как {assistant_name}.")
    while True:
        user_command = listen_continuously()
        process_command(user_command)