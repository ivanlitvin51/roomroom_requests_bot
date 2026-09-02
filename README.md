# 🤖 RoomRoom Requests & Messenger Bot

Telegram-бот для оперативного мониторинга, оповещения и распределения входящих заявок на экспертов и корпоративных чатов платформы [RoomRoom](https://room-room.app).

---

## 📌 Основные возможности

- **🔔 Мониторинг заявок на экспертов**:
  - Регулярный опрос API бэкенда (`/api/requests/expert-connection`).
  - Формирование карточки заявки: ID, имя клиента, никнейм в Telegram, источник перехода, контактный телефон и дата создания.
- **💬 Мониторинг корпоративных чатов мессенджера**:
  - Отслеживание создания новых чатов компаний (`/api/messenger/chats`).
  - Фильтрация индивидуальных диалогов и выделение чатов с контрагентами.
  - Формирование карточки: ID чата, инициатор, контрагент и дата создания.
- **🛠 Закрепление заявок (Inline-кнопка)**:
  - Под каждым уведомлением создается интерактивная кнопка **«🛠 Взять в работу»**.
  - При нажатии заявка закрепляется за модератором: сообщение обновляется, фиксируя username или имя сотрудника, а кнопка убирается для предотвращения дублирования.
- **🔐 Авторизация модераторов по секретному ключу**:
  - Вход в бота защищен паролем (`SECRET_KEY`).
  - Список авторизованных пользователей сохраняется в локальный JSON-файл и восстанавливается при перезапуске.
- **🛡 Самоочистка и отказоустойчивость**:
  - При блокировке бота пользователем или удалении из чата (ошибки Telegram API `403` и `400`), неактивный ID автоматически исключается из списка рассылки, исключая зависание очереди.
  - Активный фоновый пинг Telegram API с автоматическим переподключением при разрывах связи.
  - Бесконечный цикл `infinity_polling` с перехватом сетевых сбоев.
  - Сохранение ID последнего обработанного элемента (`last_id.txt`, `last_chat_id.txt`) для защиты от повторных оповещений.
- **⚙️ Разделение на Prod и Test режимы**:
  - Поддержка независимых конфигураций окружения (`.env.prod` и `.env.test`) и изолированных баз данных/файлов состояния.

---

## 📂 Структура проекта

```text
RR_bot/
├── bot.py                # Основной скрипт бота и логика фонового мониторинга
├── bot_test.py           # Точка входа для запуска в тестовом режиме
├── requirements.txt      # Зависимости Python
├── .env.example          # Шаблон переменных окружения
├── .env.prod             # Конфигурация для продакшна (не коммитится в Git)
├── .env.test             # Конфигурация для тестирования (не коммитится в Git)
├── moders.json           # Список авторизованных chat_id модераторов (prod)
├── moders_test.json      # Список авторизованных chat_id модераторов (test)
├── data/                 # Директория хранения курсоров (last_id)
│   ├── last_id.txt       # ID последней обработанной заявки
│   └── last_chat_id.txt  # ID последнего обработанного чата
└── README.md             # Документация проекта
```

---

## 🚀 Установка и настройка

### 1. Клонирование репозитория

```bash
git clone https://github.com/ivanlitvin51/roomroom_requests_bot.git
cd roomroom_requests_bot
```

### 2. Создание и активация виртуального окружения

**На Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**На Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env.prod` (для рабочего режима) или `.env.test` (для тестов) на основе шаблона `.env.example`:

```bash
cp .env.example .env.prod
```

Заполните переменные:

| Переменная | Описание | Пример |
|---|---|---|
| `TOKEN` | Токен вашего Telegram-бота, полученный у [@BotFather](https://t.me/BotFather) | `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ` |
| `SECRET_KEY` | Секретный пароль для авторизации модераторов в боте | `SuperSecretPass123` |
| `ADMIN_TOKEN` | Bearer JWT-токен администратора для доступа к API бэкенда RoomRoom | `eyJhbGciOiJIUzI1NiIsInR5cCI6...` |
| `API_URL_REQUESTS` | URL эндпоинта списка заявок на экспертов | `https://room-room.app/api/requests/expert-connection?page=1&pageSize=10` |
| `API_URL_CHATS` | URL эндпоинта списка чатов платформы | `https://room-room.app/api/messenger/chats?page=1&pageSize=5` |
| `MODERS_FILE` | Путь к файлу со списком ID модераторов | `moders.json` |
| `LAST_ID_FILE` | Путь к файлу с последним ID заявки | `data/last_id.txt` |
| `LAST_CHAT_ID_FILE` | Путь к файлу с последним ID чата | `data/last_chat_id.txt` |

---

## 💻 Запуск бота

### Продакшн-режим (по умолчанию используется `.env.prod`):
```bash
python bot.py
```

### Тестовый режим (автоматически использует `.env.test`):
```bash
python bot_test.py
```
*или:*
```bash
python bot.py --test
```

---

## 👥 Инструкция для модератора

1. Откройте диалог с ботом в Telegram и отправьте команду `/start`.
2. Нажмите появившуюся кнопку **«🔑 Ввести код»**.
3. Отправьте боту установленный пароль (`SECRET_KEY`).
4. После сообщения `✅ Доступ разрешен!` вы начнете получать уведомления о новых событиях.
5. При поступлении новой заявки нажмите кнопку **«🛠 Взять в работу»** для закрепления за собой.

---

## 🛠 Запуск в фоне на сервере (systemd)

Для непрерывной работы на Linux-сервере рекомендуется создать systemd-сервис:

1. Создайте файл сервиса:
```bash
sudo nano /etc/systemd/system/rr-bot.service
```

2. Вставьте конфигурацию (скорректируйте пути и пользователя):
```ini
[Unit]
Description=RoomRoom Telegram Requests Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/roomroom_requests_bot
ExecStart=/home/ubuntu/roomroom_requests_bot/venv/bin/python bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

3. Запустите и добавьте в автозагрузку:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rr-bot
sudo systemctl start rr-bot
sudo systemctl status rr-bot
```

---

## 📄 Лицензия

Проект разработан для внутреннего использования платформы RoomRoom.
