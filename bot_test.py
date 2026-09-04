"""
Запуск бота в тестовом режиме.
Автоматически подгружает .env.test и все тестовые файлы состояния.
"""
import sys

if '--test' not in sys.argv:
    sys.argv.append('--test')

import bot

if __name__ == '__main__':
    bot.main()