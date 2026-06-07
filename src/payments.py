import uuid
from datetime import datetime, timezone

from aiogram.types import LabeledPrice

from . import config
from .bot_app import bot
from .models import Payment, User
from .services import stars_to_usd


def payment_payload(kind: str, user_id: int) -> str:
    return f"tghub:{kind}:{user_id}:{uuid.uuid4().hex[:16]}"


async def create_stars_invoice(user: User, kind: str, amount_stars: int) -> Payment:
    payload = payment_payload(kind, user.id)
    payment = await Payment.create(
        user=user,
        provider="stars",
        kind=kind,
        amount_stars=amount_stars,
        amount_usd=stars_to_usd(amount_stars),
        payload=payload,
    )
    invoice_link = await bot.create_invoice_link(
        title=f"{config.BOT_TITLE}: пополнение баланса",
        description=f"Пополнение баланса Telega HUB на {amount_stars} Telegram Stars.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="XTR", amount=amount_stars)],
    )
    payment.invoice_link = invoice_link
    await payment.save(update_fields=["invoice_link"])
    return payment


async def complete_stars_payment(payload: str, telegram_charge_id: str | None = None) -> Payment | None:
    payment = await Payment.get_or_none(payload=payload)
    if not payment:
        return None
    if payment.status == "paid":
        return payment

    user = await payment.user
    if payment.kind == "topup":
        user.balance_stars += payment.amount_stars
        await user.save(update_fields=["balance_stars", "updated_at"])

    payment.status = "paid"
    payment.telegram_charge_id = telegram_charge_id
    payment.paid_at = datetime.now(timezone.utc)
    await payment.save(update_fields=["status", "telegram_charge_id", "paid_at"])
    return payment
