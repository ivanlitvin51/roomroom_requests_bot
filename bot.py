import os
import sys
import json
import time

# Корректный вывод эмодзи и юникода в консоль Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
import threading
import requests
from dotenv import load_dotenv
import telebot
from telebot import apihelper, types
from telebot.apihelper import ApiTelegramException

# --- ОПРЕДЕЛЕНИЕ ПУТЕЙ И РЕЖИМА ЗАПУСКА ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def resolve_path(rel_path):
    """Преобразует относительный путь в абсолютный относительно директории скрипта."""
    if not rel_path:
        return rel_path
    if os.path.isabs(rel_path):
        return rel_path
    return os.path.normpath(os.path.join(BASE_DIR, rel_path))

def write_text_file(filepath, content):
    """Безопасная запись текста в файл с автоматическим созданием директорий."""
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(str(content))

# Режим определяется флагом --test, переменной ENV=test или запуском через bot_test.py
IS_TEST = '--test' in sys.argv or os.getenv('ENV') == 'test' or os.path.basename(sys.argv[0]) == 'bot_test.py'
ENV_FILE = resolve_path('.env.test' if IS_TEST else '.env.prod')
load_dotenv(ENV_FILE)

# --- НАСТРОЙКИ ---
TOKEN = os.getenv('TOKEN')
SECRET_KEY = os.getenv('SECRET_KEY')
TIME_FREEZE = 15

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ И ФЛАГИ ---
IS_ONLINE = False

# API эндпоинты для опроса бэкенда
API_URL_REQUESTS = os.getenv('API_URL_REQUESTS')
API_URL_CHATS = os.getenv('API_URL_CHATS')

# Пути к локальным файлам (для хранения ID и списка доступов)
MODERS_FILE = resolve_path(os.getenv('MODERS_FILE', 'moders.json'))
LAST_ID_FILE = resolve_path(os.getenv('LAST_ID_FILE', 'data/last_id.txt'))
LAST_CHAT_ID_FILE = resolve_path(os.getenv('LAST_CHAT_ID_FILE', 'data/last_chat_id.txt'))

# Токен администратора для авторизации запросов к API
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Authorization': f'Bearer {ADMIN_TOKEN}',
    'Accept': 'application/json'
}

# Прокси для Telegram (если системный прокси блокирует или искажает запросы)
TELEGRAM_PROXY = os.getenv('TELEGRAM_PROXY')
if TELEGRAM_PROXY:
    apihelper.proxy = {'https': TELEGRAM_PROXY, 'http': TELEGRAM_PROXY}

bot = telebot.TeleBot(TOKEN)


def load_moders():
    """Загружает список chat_id авторизованных модераторов из JSON-файла."""
    if os.path.exists(MODERS_FILE):
        try:
            with open(MODERS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_moders(moders):
    """Сохраняет актуальный список модераторов в файл без дубликатов."""
    dir_path = os.path.dirname(MODERS_FILE)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(MODERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(dict.fromkeys(moders)), f, indent=2)


@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработка команды /start: выдает кнопку для ввода секретного ключа."""
    chat_id = message.chat.id
    moders = load_moders()
    
    if chat_id in moders:
        bot.send_message(chat_id, "⚠️ Вы уже авторизованы и будете получать уведомления.")
        return

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(telebot.types.KeyboardButton("🔑 Ввести код"))
    
    bot.send_message(
        chat_id, 
        "🔒 Для доступа к уведомлениям нажмите кнопку ниже:", 
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Логика проверки введенного ключа и добавления пользователя в модераторы."""
    chat_id = message.chat.id
    moders = load_moders()
    
    if chat_id in moders:
        return
        
    text = message.text.strip()
    
    if text == "🔑 Ввести код":
        bot.send_message(
            chat_id, 
            "✍️ Отправьте секретный ключ следующим сообщением:", 
            reply_markup=telebot.types.ForceReply(selective=True)
        )
    elif text == SECRET_KEY:
        moders.append(chat_id)
        save_moders(moders)
        remove_markup = telebot.types.ReplyKeyboardRemove()
        bot.send_message(
            chat_id, 
            "✅ Доступ разрешен! Вы будете получать уведомления о новых заявках и чатах.", 
            reply_markup=remove_markup
        )
    else:
        bot.send_message(chat_id, "❌ Неверный ключ. Нажмите кнопку «🔑 Ввести код» и попробуйте снова.")


def notify_single(chat_id, text):
    """Отправляет сообщение и обрабатывает ошибки сети и блокировки бота."""
    global IS_ONLINE
    try:
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("🛠 Взять в работу", callback_data="take_order")
        markup.add(btn)

        bot.send_message(chat_id, text, reply_markup=markup)

        if not IS_ONLINE:
            print("✅ Соединение с Telegram успешно восстановлено!")
            IS_ONLINE = True

        return True
    except ApiTelegramException as e:
        # 403 = Bot was blocked by user / kicked from group
        # 400 = Chat not found
        if e.error_code in (400, 403):
            print(f"🚫 Чат/пользователь {chat_id} недоступен ({e.description}). Удаляем из списка модераторов.")
            moders = load_moders()
            if chat_id in moders:
                moders.remove(chat_id)
                save_moders(moders)
            return True  # Не стопорим очередь из-за заблокированного пользователя
        print(f"❌ Ошибка Telegram API для {chat_id}: {e}")
        return False
    except Exception as e:
        if IS_ONLINE:
            print(f"⚠️ Потеряно соединение с Telegram: {e}")
            IS_ONLINE = False
        print(f"Не удалось отправить сообщение для {chat_id}: {e}")
        return False


# --- МОНИТОРИНГ ЗАЯВОК НА ЭКСПЕРТА ---
def check_new_applications():
    if not os.path.exists(LAST_ID_FILE):
        write_text_file(LAST_ID_FILE, '0')
            
    with open(LAST_ID_FILE, 'r', encoding='utf-8') as f:
        last_saved_id = int(f.read().strip() or '0')
    
    try:
        response = requests.get(API_URL_REQUESTS, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            if response.status_code == 401:
                print("❌ Ошибка API заявок: 401 Unauthorized. ADMIN_TOKEN истёк или недействителен!")
            else:
                print(f"⚠️ Ошибка API заявок: HTTP {response.status_code} - {response.text[:200]}")
            return

        data = response.json()
        items = data if isinstance(data, list) else data.get('data', data.get('items', data.get('results', [])))
        if not items:
            return

        if last_saved_id == 0:
            newest_id = int(items[0].get('id', items[0].get('ID', 0)))
            if newest_id > 0:
                write_text_file(LAST_ID_FILE, str(newest_id))
            return

        new_items = [item for item in items if int(item.get('id', item.get('ID', 0))) > last_saved_id]
        if not new_items:
            return

        new_items.sort(key=lambda x: int(x.get('id', x.get('ID', 0))))
        
        moders = load_moders()
        if not moders:
            newest_id = int(new_items[-1].get('id', new_items[-1].get('ID', 0)))
            if newest_id > 0:
                write_text_file(LAST_ID_FILE, str(newest_id))
            return

        for item in new_items:
            current_id = int(item.get('id', item.get('ID', 0)))
            
            name = item.get('fullName', item.get('name', 'Не указано'))
            phone = item.get('phone', item.get('phoneNumber', item.get('tel', 'Не указано')))
            username = item.get('nickname', item.get('username', item.get('tg', 'Не указано')))
            source = item.get('sourceLabel', 'Не указано')
            created_at = item.get('createdAt', item.get('created_at', ''))

            msg = (
                f"🔔 Поступила новая заявка на эксперта!\n\n"
                f"🆔 ID: {current_id}\n"
                f"👤 Имя: {name}\n"
                f"💬 Никнейм: {username}\n"
                f"🌐 Откуда пришли: {source}\n"
                f"📞 Телефон: {phone}"
            )
            if created_at:
                msg += f"\n📅 Дата: {created_at}"

            success_count = 0
            for chat_id in moders:
                if notify_single(chat_id, msg):
                    success_count += 1

            if success_count > 0:
                write_text_file(LAST_ID_FILE, str(current_id))
                print(f"📤 Успешно отправлено и зафиксирован ID заявки: {current_id}")
            else:
                print(f"⚠️ Нет связи с Telegram, оставляем ID {last_saved_id} в файле.")
                break

    except Exception as e:
        print(f"❌ Ошибка в check_new_applications: {e}")


# --- МОНИТОРИНГ ЧАТОВ МЕССЕНДЖЕРА ---
def check_new_chats():
    if not os.path.exists(LAST_CHAT_ID_FILE):
        write_text_file(LAST_CHAT_ID_FILE, '0')
            
    with open(LAST_CHAT_ID_FILE, 'r', encoding='utf-8') as f:
        last_saved_chat_id = int(f.read().strip() or '0')

    try:
        response = requests.get(API_URL_CHATS, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            if response.status_code == 401:
                print("❌ Ошибка API чатов: 401 Unauthorized. ADMIN_TOKEN истёк или недействителен!")
            else:
                print(f"⚠️ Ошибка API чатов: HTTP {response.status_code} - {response.text[:200]}")
            return

        data = response.json()
        chats = data if isinstance(data, list) else data.get('data', data.get('items', data.get('results', [])))
        if not chats:
            return

        if last_saved_chat_id == 0:
            newest_chat_id = int(chats[0].get('id', chats[0].get('ID', 0)))
            if newest_chat_id > 0:
                write_text_file(LAST_CHAT_ID_FILE, str(newest_chat_id))
            return

        new_chats = [chat for chat in chats if int(chat.get('id', chat.get('ID', 0))) > last_saved_chat_id]
        if not new_chats:
            return

        new_chats.sort(key=lambda x: int(x.get('id', x.get('ID', 0))))
        
        moders = load_moders()
        if not moders:
            newest_chat_id = int(new_chats[-1].get('id', new_chats[-1].get('ID', 0)))
            if newest_chat_id > 0:
                write_text_file(LAST_CHAT_ID_FILE, str(newest_chat_id))
            return

        for chat in new_chats:
            current_chat_id = int(chat.get('id', chat.get('ID', 0)))

            chat_type = chat.get('type', chat.get('chatType', ''))
            is_company_chat = False
            
            if 'компании' in str(chat_type).lower() or 'company' in str(chat_type).lower():
                is_company_chat = True
            
            if not is_company_chat:
                label_check = str(chat.get('typeName', '')).lower() + str(chat.get('label', '')).lower()
                if 'компании' in label_check:
                    is_company_chat = True

            if not is_company_chat and ('индивидуальный' in str(chat).lower() or 'individual' in str(chat).lower()):
                continue

            initiator_raw = chat.get('initiator', chat.get('author'))
            if isinstance(initiator_raw, dict):
                initiator = initiator_raw.get('label', initiator_raw.get('name', 'Не указано'))
            else:
                initiator = str(initiator_raw or 'Не указано')

            counterparty_raw = chat.get('counterparty', chat.get('recipient'))
            if isinstance(counterparty_raw, dict):
                counterparty = counterparty_raw.get('label', counterparty_raw.get('name', 'Не указано'))
            else:
                counterparty = str(counterparty_raw or 'Не указано')

            created_at = chat.get('createdAt', chat.get('created_at', ''))

            msg = (
                f"💬 Создан новый чат компании!\n\n"
                f"🆔 ID чата: {current_chat_id}\n"
                f"👤 От кого: {initiator}\n"
                f"🏢 Кому/Контрагент: {counterparty}"
            )
            if created_at:
                msg += f"\n📅 Дата: {created_at}"

            success_count = 0
            for chat_id in moders:
                if notify_single(chat_id, msg):
                    success_count += 1

            if success_count > 0:
                write_text_file(LAST_CHAT_ID_FILE, str(current_chat_id))
                print(f"📤 Успешно отправлено и зафиксирован ID чата: {current_chat_id}")
            else:
                print(f"⚠️ Нет связи с Telegram, оставляем ID чата {last_saved_chat_id} в файле.")
                break

    except Exception as e:
        print(f"❌ Ошибка в check_new_chats: {e}")


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Закрепление заявки за человеком"""
    print(f"DEBUG: Получен callback с данными: {call.data}")
    if call.data == "take_order":
        bot.answer_callback_query(call.id, "Заявка закреплена за вами!")

        new_text = call.message.text + f"\n\n👤 Взял в работу: @{call.from_user.username or call.from_user.first_name}"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=new_text,
            reply_markup=None
        )


def check_telegram_connection():
    """Пинги тг в случае падения сети"""
    global IS_ONLINE
    try:
        tg_response = bot.get_me()

        if not IS_ONLINE and tg_response:
            print("✅ Соединение с Telegram успешно установлено!")
            IS_ONLINE = True

        return True
    except Exception as e:
        if IS_ONLINE:
            print(f"⚠️ Обнаружен обрыв связи с Telegram: {e}")
            IS_ONLINE = False
        return False


def background_checker():
    """Фоновый цикл: проверяет заявки и чаты каждые TIME_FREEZE секунд."""
    print(f"🔄 Фоновый мониторинг заявок и чатов запущен (интервал: {TIME_FREEZE} сек)...")
    while True:
        check_telegram_connection()

        try:
            check_new_applications()
            check_new_chats()
        except Exception as e:
            print(f"❌ Ошибка в чекерах: {e}")

        time.sleep(TIME_FREEZE)


def main():
    mode_title = "ТЕСТОВЫЙ РЕЖИМ" if IS_TEST else "ПРОДАКШН"
    print("=" * 60)
    print(f"🚀 Запуск бота в режиме: [{mode_title}]")
    print(f"📄 Конфигурация: {ENV_FILE}")
    print(f"📂 Файл модераторов: {MODERS_FILE}")
    print(f"📂 Файлы ID: {LAST_ID_FILE}, {LAST_CHAT_ID_FILE}")
    if TELEGRAM_PROXY:
        print(f"🌐 Прокси Telegram: {TELEGRAM_PROXY}")
    print("=" * 60)

    # Фоновый поток
    checker_thread = threading.Thread(target=background_checker)
    checker_thread.daemon = True
    checker_thread.start()
    
    print(f"🤖 Бот [{mode_title}] успешно запущен и слушает события...")
    
    # В случае дропа сети есть бесконечный реконнект
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=10, long_polling_timeout=5)
        except Exception as e:
            if IS_ONLINE:
                print(f"⚠️ Ошибка соединения с Telegram: {e}. Переподключение через 5 секунд...")
                IS_ONLINE = False

            time.sleep(5)


if __name__ == '__main__':
    main()