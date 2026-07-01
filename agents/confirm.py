"""Human-in-the-loop: агент не делает необратимого без подтверждения человека.

Бот шлёт запрос с inline-кнопками Confirm/Reject в Telegram и ждёт ответа.
Один процесс = один диалог подтверждения за раз (достаточно для одного разработчика).
"""
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import settings


class ConfirmGate:
    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        if not self.bot_token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы в .env")

    async def ask(self, task_title: str, action_description: str, timeout: int = 300) -> bool:
        """Отправляет запрос на подтверждение, блокируется до ответа или таймаута.

        Возвращает True (confirm) / False (reject или таймаут — безопасный дефолт).
        """
        bot = Bot(token=self.bot_token)
        dp = Dispatcher()
        result: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

        @dp.callback_query(F.data.in_({"confirm", "reject"}))
        async def on_answer(query: CallbackQuery):
            if not result.done():
                result.set_result(query.data == "confirm")
            await query.answer("принято" if query.data == "confirm" else "отклонено")
            await query.message.edit_reply_markup(reply_markup=None)

        try:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(text="Confirm", callback_data="confirm"),
                    InlineKeyboardButton(text="Reject", callback_data="reject"),
                ]]
            )
            await bot.send_message(
                chat_id=self.chat_id,
                text=f"Задача: {task_title}\n\nАгент собирается:\n{action_description}\n\nПодтвердить?",
                reply_markup=kb,
            )

            polling_task = asyncio.create_task(dp.start_polling(bot))
            try:
                return await asyncio.wait_for(result, timeout=timeout)
            except asyncio.TimeoutError:
                await bot.send_message(chat_id=self.chat_id, text="Таймаут ожидания — действие отклонено.")
                return False
            finally:
                polling_task.cancel()
        finally:
            await bot.session.close()


async def _smoke_test():
    """Ручная проверка: python -m agents.confirm — шлёт тестовый запрос в Telegram."""
    gate = ConfirmGate()
    ok = await gate.ask("Тестовая задача", "Ничего не буду делать, просто проверяю кнопки.")
    print("подтверждено" if ok else "отклонено/таймаут")


if __name__ == "__main__":
    asyncio.run(_smoke_test())
