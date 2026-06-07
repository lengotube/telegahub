import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from tortoise.transactions import in_transaction

from . import config
from .models import Creator, CustomOrder, MediaAsset, Post, Purchase, Subscription, User, Withdrawal


SLUG_RE = re.compile(r"[^a-z0-9_]+")


def slugify(value: str) -> str:
    slug = SLUG_RE.sub("_", value.lower()).strip("_")[:48]
    return slug or f"creator_{uuid.uuid4().hex[:8]}"


def stars_to_usd(stars: int) -> float:
    return round(max(stars, 0) * config.STARS_USD_RATE, 2)


def creator_net_amount(amount_stars: int, commission_percent: int) -> int:
    return max(amount_stars - int(amount_stars * commission_percent / 100), 0)


async def save_upload(owner: User, upload: UploadFile, visibility: str = "private") -> MediaAsset:
    if not upload.filename:
        raise HTTPException(400, "File name is missing")
    content = await upload.read()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is bigger than {config.MAX_UPLOAD_MB} MB")

    mime = upload.content_type or "application/octet-stream"
    if mime.startswith("image/"):
        kind = "photo"
    elif mime.startswith("video/"):
        kind = "video"
    else:
        raise HTTPException(400, "Only photo and video files are supported")

    ext = Path(upload.filename).suffix.lower()[:12]
    folder = config.UPLOAD_DIR / str(owner.id)
    folder.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = folder / storage_name
    storage_path.write_bytes(content)

    return await MediaAsset.create(
        owner=owner,
        kind=kind,
        storage_path=str(storage_path.relative_to(config.ROOT_DIR)),
        file_name=upload.filename[:255],
        mime_type=mime[:96],
        size_bytes=len(content),
        visibility=visibility,
    )


async def active_subscription(user: User, creator: Creator) -> Subscription | None:
    now = datetime.now(timezone.utc)
    return await Subscription.get_or_none(user=user, creator=creator, status="active", expires_at__gt=now)


async def has_post_access(user: User, post: Post) -> bool:
    creator = await post.creator
    if creator.user_id == user.id:
        return True
    if post.access_type == "subscription":
        return bool(await active_subscription(user, creator))
    return bool(await Purchase.get_or_none(user=user, post=post, status="paid"))


async def spend_balance(user: User, amount_stars: int) -> None:
    if amount_stars <= 0:
        return
    fresh = await User.get(id=user.id)
    if fresh.balance_stars < amount_stars:
        raise HTTPException(402, "Not enough balance")
    fresh.balance_stars -= amount_stars
    await fresh.save(update_fields=["balance_stars", "updated_at"])
    user.balance_stars = fresh.balance_stars


async def credit_creator(creator: Creator, gross_stars: int) -> int:
    net = creator_net_amount(gross_stars, creator.commission_percent)
    creator.balance_stars += net
    await creator.save(update_fields=["balance_stars", "updated_at"])
    return net


async def subscribe_user(user: User, creator: Creator) -> Subscription:
    if creator.status != "approved":
        raise HTTPException(404, "Creator is not available")
    if creator.user_id == user.id:
        raise HTTPException(400, "You cannot subscribe to yourself")

    async with in_transaction():
        await spend_balance(user, creator.subscription_stars)
        await credit_creator(creator, creator.subscription_stars)
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        sub, _ = await Subscription.get_or_create(user=user, creator=creator, defaults={"expires_at": expires_at})
        sub.status = "active"
        sub.expires_at = expires_at
        await sub.save()
        return sub


async def buy_post(user: User, post: Post) -> Purchase:
    creator = await post.creator
    if creator.user_id == user.id:
        raise HTTPException(400, "This is your post")
    if post.access_type != "paid":
        raise HTTPException(400, "Post is not paid")

    existing = await Purchase.get_or_none(user=user, post=post, status="paid")
    if existing:
        return existing

    async with in_transaction():
        await spend_balance(user, post.price_stars)
        await credit_creator(creator, post.price_stars)
        return await Purchase.create(user=user, post=post, amount_stars=post.price_stars)


async def create_custom_order(user: User, creator: Creator, description: str, amount_stars: int) -> CustomOrder:
    if amount_stars < config.MIN_CUSTOM_ORDER_STARS:
        raise HTTPException(400, f"Minimum order amount is {config.MIN_CUSTOM_ORDER_STARS} Stars")
    if creator.user_id == user.id:
        raise HTTPException(400, "You cannot order from yourself")

    async with in_transaction():
        await spend_balance(user, amount_stars)
        return await CustomOrder.create(
            user=user,
            creator=creator,
            description=description.strip()[:2000],
            amount_stars=amount_stars,
        )


async def accept_order(order: CustomOrder, creator: Creator) -> CustomOrder:
    if order.creator_id != creator.id:
        raise HTTPException(403, "This order belongs to another creator")
    if order.status != "pending":
        raise HTTPException(400, "Order is not pending")
    order.status = "accepted"
    order.deadline_at = datetime.now(timezone.utc) + timedelta(hours=config.CUSTOM_ORDER_HOURS)
    await order.save()
    return order


async def reject_order(order: CustomOrder, creator: Creator) -> CustomOrder:
    if order.creator_id != creator.id:
        raise HTTPException(403, "This order belongs to another creator")
    if order.status != "pending":
        raise HTTPException(400, "Order is not pending")
    user = await order.user
    user.balance_stars += order.amount_stars
    await user.save(update_fields=["balance_stars", "updated_at"])
    order.status = "rejected"
    await order.save()
    return order


async def complete_order(order: CustomOrder, creator: Creator, asset: MediaAsset) -> CustomOrder:
    if order.creator_id != creator.id:
        raise HTTPException(403, "This order belongs to another creator")
    if order.status != "accepted":
        raise HTTPException(400, "Order is not accepted")
    await credit_creator(creator, order.amount_stars)
    order.delivery_asset_id = asset.id
    order.status = "completed"
    await order.save()
    return order


async def request_withdrawal(creator: Creator, amount_stars: int, wallet: str) -> Withdrawal:
    if amount_stars <= 0 or amount_stars > creator.balance_stars:
        raise HTTPException(400, "Invalid withdrawal amount")
    creator.balance_stars -= amount_stars
    creator.payout_wallet = wallet.strip()[:160]
    await creator.save(update_fields=["balance_stars", "payout_wallet", "updated_at"])
    return await Withdrawal.create(creator=creator, amount_stars=amount_stars, wallet=creator.payout_wallet)
