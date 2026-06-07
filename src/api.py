from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from tortoise.expressions import Q

from . import config
from .auth import get_current_user, require_admin
from .models import Creator, CustomOrder, MediaAsset, Payment, Post, Purchase, Report, Subscription, User, Withdrawal
from .services import (
    accept_order,
    active_subscription,
    buy_post,
    create_custom_order,
    request_withdrawal,
    reject_order,
    save_upload,
    slugify,
    stars_to_usd,
    subscribe_user,
    complete_order,
)


router = APIRouter(prefix="/api")


def media_url(asset_id: int | None) -> str | None:
    return f"/api/media/{asset_id}" if asset_id else None


async def current_creator(user: User) -> Creator:
    creator = await Creator.get_or_none(user=user)
    if not creator:
        raise HTTPException(404, "Creator profile is not created")
    return creator


async def creator_card(creator: Creator, user: User | None = None) -> dict:
    subscribed = False
    if user:
        subscribed = bool(await active_subscription(user, creator))
    posts_count = await Post.filter(creator=creator, status="active").count()
    return {
        "id": creator.id,
        "slug": creator.slug,
        "display_name": creator.display_name,
        "bio": creator.bio,
        "avatar_url": media_url(creator.avatar_asset_id),
        "trial_url": media_url(creator.trial_asset_id),
        "face_hidden": creator.face_hidden,
        "subscription_stars": creator.subscription_stars,
        "subscription_usd": stars_to_usd(creator.subscription_stars),
        "status": creator.status,
        "posts_count": posts_count,
        "subscribed": subscribed,
    }


async def post_card(post: Post, user: User) -> dict:
    can_open = await has_access_cached(user, post)
    return {
        "id": post.id,
        "creator_id": post.creator_id,
        "title": post.title,
        "caption": post.caption,
        "access_type": post.access_type,
        "price_stars": post.price_stars,
        "price_usd": stars_to_usd(post.price_stars),
        "teaser_url": media_url(post.teaser_asset_id),
        "media_url": media_url(post.media_asset_id) if can_open else None,
        "locked": not can_open,
        "created_at": post.created_at.isoformat(),
    }


async def has_access_cached(user: User, post: Post) -> bool:
    creator = await post.creator
    if creator.user_id == user.id:
        return True
    if post.access_type == "subscription":
        return bool(await active_subscription(user, creator))
    return bool(await Purchase.get_or_none(user=user, post=post, status="paid"))


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "project": config.PROJECT_NAME}


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    creator = await Creator.get_or_none(user=user)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "balance_stars": user.balance_stars,
        "balance_usd": stars_to_usd(user.balance_stars),
        "age_confirmed": user.age_confirmed,
        "is_admin": user.id in config.BOT_ADMINS or user.role == "admin",
        "creator": await creator_card(creator, user) if creator else None,
    }


@router.post("/me/age-confirm")
async def age_confirm(user: User = Depends(get_current_user)) -> dict:
    user.age_confirmed = True
    await user.save(update_fields=["age_confirmed", "updated_at"])
    return {"ok": True}


@router.get("/feed")
async def feed(user: User = Depends(get_current_user)) -> dict:
    if not user.age_confirmed:
        return {"age_required": True, "creators": [], "posts": []}

    creators = await Creator.filter(status="approved").order_by("-created_at").limit(24)
    posts = await Post.filter(status="active").order_by("-created_at").limit(40)
    return {
        "age_required": False,
        "creators": [await creator_card(creator, user) for creator in creators],
        "posts": [await post_card(post, user) for post in posts],
    }


@router.get("/creators/{slug}")
async def creator_profile(slug: str, user: User = Depends(get_current_user)) -> dict:
    creator = await Creator.get_or_none(slug=slug, status="approved")
    if not creator:
        raise HTTPException(404, "Creator not found")
    posts = await Post.filter(creator=creator, status="active").order_by("-created_at")
    return {
        "creator": await creator_card(creator, user),
        "posts": [await post_card(post, user) for post in posts],
    }


@router.post("/creators/apply")
async def apply_creator(
    display_name: str = Form(..., min_length=2, max_length=96),
    bio: str = Form("", max_length=1000),
    subscription_stars: int = Form(config.DEFAULT_SUBSCRIPTION_STARS),
    face_hidden: bool = Form(True),
    avatar: UploadFile | None = File(None),
    trial_video: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
) -> dict:
    if not user.age_confirmed:
        raise HTTPException(403, "Confirm 18+ first")

    creator = await Creator.get_or_none(user=user)
    if creator:
        raise HTTPException(400, "Creator profile already exists")

    avatar_asset = await save_upload(user, avatar, "teaser") if avatar else None
    trial_asset = await save_upload(user, trial_video, "teaser") if trial_video else None
    base_slug = slugify(display_name)
    slug = base_slug
    counter = 2
    while await Creator.get_or_none(slug=slug):
        slug = f"{base_slug}_{counter}"
        counter += 1

    creator = await Creator.create(
        user=user,
        slug=slug,
        display_name=display_name.strip(),
        bio=bio.strip(),
        avatar_asset_id=avatar_asset.id if avatar_asset else None,
        trial_asset_id=trial_asset.id if trial_asset else None,
        face_hidden=face_hidden,
        subscription_stars=max(subscription_stars, 1),
    )
    user.role = "creator_pending"
    await user.save(update_fields=["role", "updated_at"])
    return {"ok": True, "creator": await creator_card(creator, user)}


@router.post("/creators/{creator_id}/subscribe")
async def subscribe(creator_id: int, user: User = Depends(get_current_user)) -> dict:
    creator = await Creator.get_or_none(id=creator_id)
    if not creator:
        raise HTTPException(404, "Creator not found")
    sub = await subscribe_user(user, creator)
    return {"ok": True, "expires_at": sub.expires_at.isoformat(), "balance_stars": user.balance_stars}


@router.post("/posts")
async def create_post(
    title: str = Form(..., min_length=1, max_length=120),
    caption: str = Form("", max_length=2000),
    access_type: str = Form("subscription"),
    price_stars: int = Form(0),
    media: UploadFile = File(...),
    teaser: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
) -> dict:
    creator = await current_creator(user)
    if creator.status != "approved":
        raise HTTPException(403, "Creator is not approved yet")
    if access_type not in {"subscription", "paid"}:
        raise HTTPException(400, "access_type must be subscription or paid")
    if access_type == "paid" and price_stars <= 0:
        raise HTTPException(400, "Paid post needs price_stars")

    media_asset = await save_upload(user, media, "private")
    teaser_asset = await save_upload(user, teaser, "teaser") if teaser else None
    post = await Post.create(
        creator=creator,
        title=title.strip(),
        caption=caption.strip(),
        access_type=access_type,
        price_stars=max(price_stars, 0) if access_type == "paid" else 0,
        media_asset_id=media_asset.id,
        teaser_asset_id=teaser_asset.id,
    )
    return {"ok": True, "post": await post_card(post, user)}


@router.post("/posts/{post_id}/buy")
async def buy(post_id: int, user: User = Depends(get_current_user)) -> dict:
    post = await Post.get_or_none(id=post_id, status="active")
    if not post:
        raise HTTPException(404, "Post not found")
    purchase = await buy_post(user, post)
    return {"ok": True, "purchase_id": purchase.id, "balance_stars": user.balance_stars}


@router.post("/orders")
async def create_order(
    creator_id: int = Form(...),
    description: str = Form(..., min_length=5, max_length=2000),
    amount_stars: int = Form(...),
    user: User = Depends(get_current_user),
) -> dict:
    creator = await Creator.get_or_none(id=creator_id, status="approved")
    if not creator:
        raise HTTPException(404, "Creator not found")
    order = await create_custom_order(user, creator, description, amount_stars)
    return {"ok": True, "order_id": order.id, "balance_stars": user.balance_stars}


@router.get("/creator/dashboard")
async def creator_dashboard(user: User = Depends(get_current_user)) -> dict:
    creator = await current_creator(user)
    active_subs = await Subscription.filter(creator=creator, status="active", expires_at__gt=datetime.now(timezone.utc)).count()
    paid_posts = await Purchase.filter(post__creator=creator, status="paid").count()
    pending_orders = await CustomOrder.filter(creator=creator, status="pending").count()
    return {
        "creator": await creator_card(creator, user),
        "balance_stars": creator.balance_stars,
        "balance_usd": stars_to_usd(creator.balance_stars),
        "active_subscribers": active_subs,
        "paid_posts": paid_posts,
        "pending_orders": pending_orders,
        "commission_percent": creator.commission_percent,
    }


@router.get("/creator/orders")
async def creator_orders(user: User = Depends(get_current_user)) -> dict:
    creator = await current_creator(user)
    orders = await CustomOrder.filter(creator=creator).order_by("-created_at").limit(100)
    return {
        "orders": [
            {
                "id": order.id,
                "user_id": order.user_id,
                "description": order.description,
                "amount_stars": order.amount_stars,
                "status": order.status,
                "deadline_at": order.deadline_at.isoformat() if order.deadline_at else None,
                "delivery_url": media_url(order.delivery_asset_id),
                "created_at": order.created_at.isoformat(),
            }
            for order in orders
        ]
    }


@router.post("/creator/orders/{order_id}/accept")
async def order_accept(order_id: int, user: User = Depends(get_current_user)) -> dict:
    creator = await current_creator(user)
    order = await CustomOrder.get_or_none(id=order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    order = await accept_order(order, creator)
    return {"ok": True, "deadline_at": order.deadline_at.isoformat() if order.deadline_at else None}


@router.post("/creator/orders/{order_id}/reject")
async def order_reject(order_id: int, user: User = Depends(get_current_user)) -> dict:
    creator = await current_creator(user)
    order = await CustomOrder.get_or_none(id=order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    await reject_order(order, creator)
    return {"ok": True}


@router.post("/creator/orders/{order_id}/deliver")
async def order_deliver(
    order_id: int,
    media: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    creator = await current_creator(user)
    order = await CustomOrder.get_or_none(id=order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    asset = await save_upload(user, media, "private")
    await complete_order(order, creator, asset)
    return {"ok": True}


@router.post("/creator/withdrawals")
async def withdrawal(
    amount_stars: int = Form(...),
    wallet: str = Form(..., min_length=4, max_length=160),
    user: User = Depends(get_current_user),
) -> dict:
    creator = await current_creator(user)
    item = await request_withdrawal(creator, amount_stars, wallet)
    return {"ok": True, "withdrawal_id": item.id, "balance_stars": creator.balance_stars}


@router.post("/reports")
async def report(
    target_type: str = Form(...),
    target_id: int = Form(...),
    reason: str = Form("", max_length=255),
    user: User = Depends(get_current_user),
) -> dict:
    if target_type not in {"creator", "post", "order"}:
        raise HTTPException(400, "Unknown report target")
    item = await Report.create(user=user, target_type=target_type, target_id=target_id, reason=reason.strip())
    return {"ok": True, "report_id": item.id}


@router.get("/media/{asset_id}")
async def media(asset_id: int, user: User = Depends(get_current_user)):
    asset = await MediaAsset.get_or_none(id=asset_id, status="active")
    if not asset:
        raise HTTPException(404, "Media not found")

    is_admin = user.id in config.BOT_ADMINS or user.role == "admin"
    if asset.visibility != "teaser" and asset.owner_id != user.id and not is_admin:
        post = await Post.get_or_none(Q(media_asset_id=asset.id) | Q(teaser_asset_id=asset.id))
        allowed = bool(post and await has_access_cached(user, post))
        order = await CustomOrder.get_or_none(delivery_asset_id=asset.id, user=user, status="completed")
        if not allowed and not order:
            raise HTTPException(403, "Media is locked")

    path = (config.ROOT_DIR / asset.storage_path).resolve()
    if config.ROOT_DIR.resolve() not in path.parents:
        raise HTTPException(400, "Bad media path")
    if not path.exists():
        raise HTTPException(404, "File is missing")
    return FileResponse(path, media_type=asset.mime_type, filename=Path(asset.file_name).name)


@router.post("/wallet/stars-invoice")
async def stars_invoice(
    amount_stars: int = Form(...),
    user: User = Depends(get_current_user),
) -> dict:
    from .payments import create_stars_invoice

    if amount_stars <= 0:
        raise HTTPException(400, "Amount must be positive")
    payment = await create_stars_invoice(user, "topup", amount_stars)
    return {"ok": True, "invoice_link": payment.invoice_link, "payment_id": payment.id}


@router.get("/admin/summary")
async def admin_summary(user: User = Depends(get_current_user)) -> dict:
    await require_admin(user)
    paid = await Payment.filter(status="paid").count()
    creators_pending = await Creator.filter(status="pending").count()
    return {
        "users": await User.all().count(),
        "creators": await Creator.all().count(),
        "creators_pending": creators_pending,
        "posts": await Post.all().count(),
        "orders_pending": await CustomOrder.filter(status="pending").count(),
        "withdrawals_pending": await Withdrawal.filter(status="pending").count(),
        "payments_paid": paid,
    }


@router.get("/admin/creators")
async def admin_creators(user: User = Depends(get_current_user)) -> dict:
    await require_admin(user)
    creators = await Creator.all().order_by("-created_at").limit(200)
    return {"creators": [await creator_card(creator, user) for creator in creators]}


@router.post("/admin/creators/{creator_id}/approve")
async def admin_creator_approve(creator_id: int, user: User = Depends(get_current_user)) -> dict:
    await require_admin(user)
    creator = await Creator.get_or_none(id=creator_id)
    if not creator:
        raise HTTPException(404, "Creator not found")
    creator.status = "approved"
    await creator.save(update_fields=["status", "updated_at"])
    owner = await creator.user
    owner.role = "creator"
    await owner.save(update_fields=["role", "updated_at"])
    return {"ok": True}


@router.post("/admin/creators/{creator_id}/reject")
async def admin_creator_reject(creator_id: int, user: User = Depends(get_current_user)) -> dict:
    await require_admin(user)
    creator = await Creator.get_or_none(id=creator_id)
    if not creator:
        raise HTTPException(404, "Creator not found")
    creator.status = "rejected"
    await creator.save(update_fields=["status", "updated_at"])
    return {"ok": True}


@router.get("/admin/withdrawals")
async def admin_withdrawals(user: User = Depends(get_current_user)) -> dict:
    await require_admin(user)
    items = await Withdrawal.filter(status="pending").order_by("created_at").limit(200)
    return {
        "withdrawals": [
            {
                "id": item.id,
                "creator_id": item.creator_id,
                "amount_stars": item.amount_stars,
                "wallet": item.wallet,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    }
