import telebot
import requests
import json
import os
import time
import threading
import time
import requests
from dotenv import load_dotenv

load_dotenv('.env.prod')

# --- НАСТРОЙКИ ---
TOKEN = os.getenv('TOKEN')
SECRET_KEY = os.getenv('SECRET_KEY')
TIME_FREEZE = 15

# API эндпоинты для опроса бэкенда
API_URL_REQUESTS = os.getenv('API_URL_REQUESTS')
API_URL_CHATS = os.getenv('API_URL_CHATS')

# Пути к локальным файлам (для хранения ID и списка доступов)
MODERS_FILE = os.getenv('MODERS_FILE')
LAST_ID_FILE = os.getenv('LAST_ID_FILE')
LAST_CHAT_ID_FILE = os.getenv('LAST_CHAT_ID_FILE')

# Токен администратора для авторизации запросов к API
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Authorization': f'Bearer {ADMIN_TOKEN}',
    'Accept': 'application/json'
}

bot = telebot.TeleBot(TOKEN)


def load_moders():
    """Загружает список chat_id авторизованных модераторов из JSON-файла."""
    if os.path.exists(MODERS_FILE):
        try:
            with open(MODERS_FILE, 'r') as f:
                content = f.read().strip()
                if not content:
                    return []
                return json.loads(content)
        except json.JSONDecodeError:
            return []
    return []


def save_moders(moders):
    """Сохраняет актуальный список модераторов в файл."""
    with open(MODERS_FILE, 'w') as f:
        json.dump(moders, f)


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
    """Отправляет сообщение конкретному пользователю и возвращает True в случае успеха."""
    try:
        bot.send_message(chat_id, text)
        return True
    except Exception as e:
        print(f"Не удалось отправить сообщение для {chat_id}: {e}")
        return False


# --- МОНИТОРИНГ ЗАЯВОК НА ЭКСПЕРТА ---
def check_new_applications():
    if not os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, 'w') as f:
            f.write('0')
            
    with open(LAST_ID_FILE, 'r') as f:
        last_saved_id = int(f.read().strip() or '0')
    
    try:
        response = requests.get(API_URL_REQUESTS, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return

        data = response.json()
        items = data if isinstance(data, list) else data.get('data', data.get('items', data.get('results', [])))
        if not items:
            return

        if last_saved_id == 0:
            newest_id = int(items[0].get('id', items[0].get('ID', 0)))
            if newest_id > 0:
                with open(LAST_ID_FILE, 'w') as f:
                    f.write(str(newest_id))
            return

        new_items = [item for item in items if int(item.get('id', item.get('ID', 0))) > last_saved_id]
        if not new_items:
            return

        new_items.sort(key=lambda x: int(x.get('id', x.get('ID', 0))))
        
        moders = load_moders()
        if not moders:
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
                with open(LAST_ID_FILE, 'w') as f:
                    f.write(str(current_id))
                print(f"📤 Успешно отправлено и зафиксирован ID заявки: {current_id}")
            else:
                print(f"⚠️ Нет связи с Telegram, оставляем ID {last_saved_id} в файле.")
                break

    except Exception as e:
        print(f"❌ Ошибка в check_new_applications: {e}")


# --- МОНИТОРИНГ ЧАТОВ МЕССЕНДЖЕРА ---
def check_new_chats():
    if not os.path.exists(LAST_CHAT_ID_FILE):
        with open(LAST_CHAT_ID_FILE, 'w') as f:
            f.write('0')
            
    with open(LAST_CHAT_ID_FILE, 'r') as f:
        last_saved_chat_id = int(f.read().strip() or '0')

    try:
        response = requests.get(API_URL_CHATS, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return

        data = response.json()
        chats = data if isinstance(data, list) else data.get('data', data.get('items', data.get('results', [])))
        if not chats:
            return

        if last_saved_chat_id == 0:
            newest_chat_id = int(chats[0].get('id', chats[0].get('ID', 0)))
            if newest_chat_id > 0:
                with open(LAST_CHAT_ID_FILE, 'w') as f:
                    f.write(str(newest_chat_id))
            return

        new_chats = [chat for chat in chats if int(chat.get('id', chat.get('ID', 0))) > last_saved_chat_id]
        if not new_chats:
            return

        new_chats.sort(key=lambda x: int(x.get('id', x.get('ID', 0))))
        
        moders = load_moders()
        if not moders:
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
                counterparty = str(counterparty_raw=counterparty_raw or 'Не указано') # type: ignore

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
                with open(LAST_CHAT_ID_FILE, 'w') as f:
                    f.write(str(current_chat_id))
                print(f"📤 Успешно отправлено и зафиксирован ID чата: {current_chat_id}")
            else:
                print(f"⚠️ Нет связи с Telegram, оставляем ID чата {last_saved_chat_id} в файле.")
                break

    except Exception as e:
        print(f"❌ Ошибка в check_new_chats: {e}")


def background_checker():
  """Фоновый цикл: проверяет заявки и чаты каждые TIME_FREEZE секунд."""
  print(f"🔄 Фоновый мониторинг заявок и чатов запущен (интервал: {TIME_FREEZE} сек)...")
  while True:
    check_new_applications()
    check_new_chats()
    time.sleep(TIME_FREEZE)

if __name__ == '__main__':
    # Фоновый поток
    checker_thread = threading.Thread(target=background_checker)
    checker_thread.daemon = True
    checker_thread.start()
    
    print("🤖 Бот успешно запущен и слушает события...")
    
    # В добавок в случае дропа сети есть бесконечный реконнект
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Ошибка соединения с Telegram: {e}. Переподключение через 5 секунд...")
            time.sleep(5)