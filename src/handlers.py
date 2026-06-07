from contextlib import suppress

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, PreCheckoutQuery, WebAppInfo

from . import config
from .models import Creator, CustomOrder, Payment, Post, User, Withdrawal
from .payments import complete_stars_payment


router = Router(name="bot")


def webapp_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Открыть Telega HUB", web_app=WebAppInfo(url=config.WEBAPP_URL))]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def start(message: Message) -> None:
    user, _ = await User.get_or_create(
        id=message.from_user.id,
        defaults={
            "username": message.from_user.username,
            "full_name": message.from_user.full_name or "",
        },
    )
    if user.id in config.BOT_ADMINS and user.role != "admin":
        user.role = "admin"
        await user.save(update_fields=["role", "updated_at"])

    text = (
        f"<b>{config.BOT_TITLE}</b>\n\n"
        "Каталог авторов, подписки, платные посты и кастомные заказы внутри Telegram Web App.\n\n"
        "Перед публикацией и покупками в WebApp нужно подтвердить 18+."
    )
    await message.answer(text, reply_markup=webapp_keyboard())


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if message.from_user.id not in config.BOT_ADMINS:
        return
    summary = {
        "users": await User.all().count(),
        "creators_pending": await Creator.filter(status="pending").count(),
        "posts": await Post.all().count(),
        "orders_pending": await CustomOrder.filter(status="pending").count(),
        "withdrawals_pending": await Withdrawal.filter(status="pending").count(),
        "paid_payments": await Payment.filter(status="paid").count(),
    }
    text = (
        "<b>Админ-панель Telega HUB</b>\n\n"
        f"Пользователи: <code>{summary['users']}</code>\n"
        f"Модели на проверке: <code>{summary['creators_pending']}</code>\n"
        f"Посты: <code>{summary['posts']}</code>\n"
        f"Заказы ждут ответа: <code>{summary['orders_pending']}</code>\n"
        f"Выводы ждут обработки: <code>{summary['withdrawals_pending']}</code>\n"
        f"Оплаченных платежей: <code>{summary['paid_payments']}</code>\n\n"
        "Полная админка открывается в WebApp, если твой Telegram ID есть в bot.admins."
    )
    await message.answer(text, reply_markup=webapp_keyboard())


@router.pre_checkout_query()
async def stars_pre_checkout(query: PreCheckoutQuery) -> None:
    payment = await Payment.get_or_none(payload=query.invoice_payload)
    if not payment:
        await query.answer(ok=False, error_message="Платеж не найден")
        return
    if query.currency != "XTR" or query.total_amount != payment.amount_stars:
        await query.answer(ok=False, error_message="Неверная сумма платежа")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def stars_successful_payment(message: Message) -> None:
    payment_info = message.successful_payment
    if not payment_info or payment_info.currency != "XTR":
        return

    payment = await complete_stars_payment(
        payment_info.invoice_payload,
        payment_info.telegram_payment_charge_id,
    )
    if not payment:
        await message.answer("Оплата прошла, но платеж не найден. Напиши в поддержку.")
        return

    await message.answer(
        f"Готово. Баланс пополнен на <b>{payment.amount_stars} Stars</b>.",
        reply_markup=webapp_keyboard(),
    )
    notice = (
        "<b>Новый платеж Stars</b>\n\n"
        f"User: <code>{message.from_user.id}</code>\n"
        f"Сумма: <b>{payment.amount_stars} Stars</b>\n"
        f"Payment ID: <code>{payment.id}</code>"
    )
    for admin_id in config.BOT_ADMINS:
        with suppress(Exception):
            await message.bot.send_message(admin_id, notice)


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()
