#!/usr/bin/env python3
"""
test_bot_main.py — Production-ready Aiogram 3.x Telegram тест-бот
11 специализаций × FSM × PDF × Stats × Reminders × Числовые кнопки 1️⃣2️⃣3️⃣4️⃣5️⃣
"""

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.filters import Command

from config.settings import settings
from library import AntiSpamMiddleware, ErrorHandlerMiddleware
from library.keyboards import get_main_keyboard
from library.stats import stats_manager
from library.reminders import reminders_background_task

# Импорт всех роутеров специализаций
from specializations import (
    oupds_router, ispolniteli_router, aliment_router, doznanie_router,
    rozyisk_router, prof_router, oko_router, informatika_router,
    kadry_router, bezopasnost_router, upravlenie_router
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot: Bot | None = None
dp: Dispatcher | None = None
reminder_task = None


async def set_bot_commands(bot: Bot):
    """Установка команд бота в меню."""
    commands = [
        BotCommand(command="start", description="🏠 Начать тест"),
        BotCommand(command="stats", description="📊 Моя статистика"),
        BotCommand(command="help", description="❓ Помощь"),
    ]
    await bot.set_my_commands(commands)
    logger.info("✅ Команды бота установлены")


async def on_startup():
    """Инициализация при запуске бота."""
    global reminder_task
    
    # Инициализация базы данных
    await stats_manager.init_db()
    logger.info("✅ База данных инициализирована")
    
    # Установка команд бота
    await set_bot_commands(bot)
    
    # Запуск фоновой задачи напоминаний
    reminder_task = asyncio.create_task(reminders_background_task(bot))
    logger.info("✅ Сервис напоминаний запущен")
    
    logger.info("🚀 Бот инициализирован и готов к работе")


async def on_shutdown():
    """Корректное завершение работы бота."""
    global reminder_task
    
    logger.info("🛑 Завершение работы бота")
    
    # Остановка напоминаний
    if reminder_task:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        logger.info("✅ Сервис напоминаний остановлен")
    
    # Graceful shutdown
    if dp:
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    
    if bot:
        await bot.session.close()
    
    logger.info("👋 Бот остановлен корректно")


async def main():
    """Главная функция запуска бота."""
    global bot, dp
    
    # Проверка API токена
    if not settings.api_token:
        logger.error("❌ API_TOKEN отсутствует! Установите переменную окружения API_TOKEN")
        sys.exit(1)
    
    # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.api_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация событий
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Подключение middlewares
    dp.message.middleware(AntiSpamMiddleware())
    dp.callback_query.middleware(AntiSpamMiddleware())
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())
    logger.info("✅ Middlewares подключены")
    
    # Главный роутер с командами
    main_router = Router()
    
    @main_router.message(Command("start"))
    async def cmd_start(message: Message):
        """Команда /start - главное меню."""
        text = (
            "🧪 <b>ФССП Тест-бот</b>\n\n"
            "Добро пожаловать в систему тестирования сотрудников ФССП!\n\n"
            "Выберите специализацию для прохождения теста:"
        )
        
        await message.answer(text, reply_markup=get_main_keyboard())
    
    @main_router.message(Command("stats"))
    async def cmd_stats(message: Message):
        """Команда /stats - показать статистику пользователя."""
        try:
            stats = await stats_manager.get_user_stats(message.from_user.id)
            
            if stats.get("total_tests", 0) == 0:
                await message.answer(
                    "📊 <b>Ваша статистика</b>\n\n"
                    "У вас пока нет пройденных тестов.\n"
                    "Начните тестирование командой /start!"
                )
                return
            
            stats_text = (
                f"📊 <b>Ваша статистика</b>\n\n"
                f"📝 Всего тестов: {stats['total_tests']}\n"
                f"📈 Средний балл: {stats['avg_percentage']}%\n"
                f"🏆 Лучший результат: {stats['best_result']}%\n"
                f"📉 Худший результат: {stats['worst_result']}%"
            )
            
            if stats.get('recent_tests'):
                stats_text += "\n\n<b>Последние тесты:</b>\n"
                for r in stats['recent_tests']:
                    stats_text += (
                        f"• {r['specialization']} ({r['difficulty']}): "
                        f"{r['grade']} - {r['percentage']:.1f}%\n"
                    )
            
            await message.answer(stats_text)
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа статистики: {e}", exc_info=True)
            await message.answer("❌ Ошибка загрузки статистики")
    
    @main_router.message(Command("help"))
    async def cmd_help(message: Message):
        """Команда /help - показать справку."""
        help_text = (
            "❓ <b>Справка по боту</b>\n\n"
            "<b>Как пройти тест:</b>\n"
            "1️⃣ Нажмите /start и выберите специализацию\n"
            "2️⃣ Введите ФИО, должность, подразделение\n"
            "3️⃣ Выберите уровень сложности\n"
            "4️⃣ Отвечайте на вопросы кнопками 1️⃣2️⃣3️⃣...\n"
            "5️⃣ Нажимайте ➡️ Далее после выбора ответов\n"
            "6️⃣ Получите результат и PDF сертификат\n\n"
            "<b>Обозначения:</b>\n"
            "• 1️⃣2️⃣3️⃣ - номера вариантов ответа\n"
            "• ✅ - выбранный вариант\n"
            "• ⏰ - оставшееся время\n\n"
            "<b>Функции после теста:</b>\n"
            "• 📋 Показать правильные ответы\n"
            "• 🏆 Скачать PDF сертификат\n"
            "• 📊 Просмотреть статистику\n"
            "• 🔄 Повторить тест\n\n"
            "<b>Команды:</b>\n"
            "/start - начать тест\n"
            "/stats - моя статистика\n"
            "/help - эта справка\n\n"
            "<b>Уровни сложности:</b>\n"
            "🥉 Резерв: 20 вопросов, 35 минут\n"
            "🥈 Базовый: 30 вопросов, 25 минут\n"
            "🥇 Стандартный: 40 вопросов, 20 минут\n"
            "💎 Продвинутый: 50 вопросов, 20 минут\n\n"
            "Удачи на тестировании! 🍀"
        )
        await message.answer(help_text)
    
    # Подключение роутеров
    dp.include_router(main_router)
    dp.include_router(oupds_router)
    dp.include_router(ispolniteli_router)
    dp.include_router(aliment_router)
    dp.include_router(doznanie_router)
    dp.include_router(rozyisk_router)
    dp.include_router(prof_router)
    dp.include_router(oko_router)
    dp.include_router(informatika_router)
    dp.include_router(kadry_router)
    dp.include_router(bezopasnost_router)
    dp.include_router(upravlenie_router)
    
    logger.info("✅ Загружено 11 роутеров специализаций")
    logger.info("🚀 Запуск polling...")
    
    # Запуск бота
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Ошибка при работе бота: {e}", exc_info=True)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Прервано пользователем")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}", exc_info=True)
        sys.exit(1)
