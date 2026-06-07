from tortoise import fields
from tortoise.models import Model

from .config import COMMISSION_PERCENT


class User(Model):
    id = fields.BigIntField(pk=True)
    username = fields.CharField(max_length=64, null=True)
    full_name = fields.CharField(max_length=128, default="")
    role = fields.CharField(max_length=16, default="user")
    balance_stars = fields.IntField(default=0)
    age_confirmed = fields.BooleanField(default=False)
    is_banned = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"


class Creator(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="creator_profiles", on_delete=fields.CASCADE)
    slug = fields.CharField(max_length=64, unique=True)
    display_name = fields.CharField(max_length=96)
    bio = fields.TextField(default="")
    avatar_asset_id = fields.IntField(null=True)
    trial_asset_id = fields.IntField(null=True)
    face_hidden = fields.BooleanField(default=True)
    subscription_stars = fields.IntField(default=250)
    status = fields.CharField(max_length=16, default="pending")
    commission_percent = fields.IntField(default=COMMISSION_PERCENT)
    balance_stars = fields.IntField(default=0)
    pending_stars = fields.IntField(default=0)
    payout_wallet = fields.CharField(max_length=160, default="")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "creators"
        indexes = (("status", "subscription_stars"),)


class MediaAsset(Model):
    id = fields.IntField(pk=True)
    owner = fields.ForeignKeyField("models.User", related_name="media_assets", on_delete=fields.CASCADE)
    kind = fields.CharField(max_length=16)
    storage_path = fields.TextField()
    file_name = fields.CharField(max_length=255, default="")
    mime_type = fields.CharField(max_length=96, default="")
    size_bytes = fields.IntField(default=0)
    duration_seconds = fields.IntField(null=True)
    visibility = fields.CharField(max_length=16, default="private")
    status = fields.CharField(max_length=16, default="active")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "media_assets"


class Post(Model):
    id = fields.IntField(pk=True)
    creator = fields.ForeignKeyField("models.Creator", related_name="posts", on_delete=fields.CASCADE)
    title = fields.CharField(max_length=120)
    caption = fields.TextField(default="")
    access_type = fields.CharField(max_length=16, default="subscription")
    price_stars = fields.IntField(default=0)
    media_asset_id = fields.IntField(null=True)
    teaser_asset_id = fields.IntField(null=True)
    status = fields.CharField(max_length=16, default="active")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "posts"
        indexes = (("creator", "status"), ("access_type", "price_stars"))


class Subscription(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="subscriptions", on_delete=fields.CASCADE)
    creator = fields.ForeignKeyField("models.Creator", related_name="subscriptions", on_delete=fields.CASCADE)
    status = fields.CharField(max_length=16, default="active")
    starts_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()

    class Meta:
        table = "subscriptions"
        unique_together = (("user", "creator"),)


class Purchase(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="purchases", on_delete=fields.CASCADE)
    post = fields.ForeignKeyField("models.Post", related_name="purchases", on_delete=fields.CASCADE)
    amount_stars = fields.IntField()
    status = fields.CharField(max_length=16, default="paid")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "purchases"
        unique_together = (("user", "post"),)


class CustomOrder(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="custom_orders", on_delete=fields.CASCADE)
    creator = fields.ForeignKeyField("models.Creator", related_name="custom_orders", on_delete=fields.CASCADE)
    description = fields.TextField()
    amount_stars = fields.IntField()
    status = fields.CharField(max_length=16, default="pending")
    delivery_asset_id = fields.IntField(null=True)
    deadline_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "custom_orders"
        indexes = (("creator", "status"), ("user", "status"))


class Payment(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="payments", on_delete=fields.CASCADE)
    provider = fields.CharField(max_length=16, default="stars")
    kind = fields.CharField(max_length=32)
    target_type = fields.CharField(max_length=32, default="")
    target_id = fields.IntField(null=True)
    amount_stars = fields.IntField()
    amount_usd = fields.FloatField(default=0)
    status = fields.CharField(max_length=16, default="created")
    payload = fields.CharField(max_length=128, unique=True)
    invoice_link = fields.TextField(null=True)
    telegram_charge_id = fields.CharField(max_length=128, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    paid_at = fields.DatetimeField(null=True)

    class Meta:
        table = "payments"


class Withdrawal(Model):
    id = fields.IntField(pk=True)
    creator = fields.ForeignKeyField("models.Creator", related_name="withdrawals", on_delete=fields.CASCADE)
    amount_stars = fields.IntField()
    wallet = fields.CharField(max_length=160)
    status = fields.CharField(max_length=16, default="pending")
    created_at = fields.DatetimeField(auto_now_add=True)
    processed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "withdrawals"


class Report(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="reports", on_delete=fields.CASCADE)
    target_type = fields.CharField(max_length=32)
    target_id = fields.IntField()
    reason = fields.CharField(max_length=255, default="")
    status = fields.CharField(max_length=16, default="open")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "reports"
        indexes = (("target_type", "target_id"),)
