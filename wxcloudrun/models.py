"""简单商城数据模型。

价格统一以「分」为单位存储(整数),前端展示时除以 100 得到「元」,
避免浮点精度问题。所有字段名使用 snake_case,API 输出时由序列化层
映射为小程序端友好的 camelCase 字段。
"""
from pathlib import Path

from django.core.validators import FileExtensionValidator
from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        abstract = True


class Asset(BaseModel):
    """后台素材库中的本地图片。"""

    name = models.CharField(max_length=256, blank=True, default="", verbose_name="素材名称")
    file = models.FileField(
        upload_to="assets/%Y/%m",
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "gif", "webp"])],
        verbose_name="图片文件",
    )

    class Meta:
        verbose_name = "素材"
        verbose_name_plural = "素材库"
        ordering = ["-id"]

    def save(self, *args, **kwargs):
        if self.file and not self.name:
            self.name = Path(self.file.name).stem
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def url(self):
        return self.file.url if self.file else ""


class Category(BaseModel):
    """商品分类(支持两级:父分类 + 子分类)。"""

    name = models.CharField(max_length=64, verbose_name="分类名称")
    icon = models.URLField(max_length=512, blank=True, verbose_name="分类图标")
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children",
        on_delete=models.CASCADE, verbose_name="上级分类",
    )
    sort = models.IntegerField(default=0, verbose_name="排序")

    class Meta:
        verbose_name = "商品分类"
        verbose_name_plural = "商品分类"
        ordering = ["sort", "id"]

    def __str__(self):
        return self.name


class Product(BaseModel):
    """商品。简单商城不做多规格 SKU,一个商品一个价格一份库存。"""

    title = models.CharField(max_length=256, verbose_name="商品标题")
    subtitle = models.CharField(max_length=256, blank=True, verbose_name="副标题")
    image = models.URLField(max_length=512, verbose_name="主图")
    images = models.JSONField(default=list, blank=True, verbose_name="图片列表")
    primary_asset = models.ForeignKey(
        Asset,
        null=True,
        blank=True,
        related_name="primary_products",
        on_delete=models.SET_NULL,
        verbose_name="素材库主图",
    )
    # 价格单位:分
    price = models.BigIntegerField(default=0, verbose_name="售价(分)")
    stock = models.IntegerField(default=0, verbose_name="库存")
    sales = models.IntegerField(default=0, verbose_name="已售数量")
    category = models.ForeignKey(
        Category, null=True, blank=True, related_name="products",
        on_delete=models.SET_NULL, verbose_name="所属分类",
    )
    tags = models.JSONField(default=list, blank=True, verbose_name="标签")
    detail = models.TextField(blank=True, verbose_name="图文详情(HTML)")
    is_on_sale = models.BooleanField(default=True, verbose_name="是否上架")
    sort = models.IntegerField(default=0, verbose_name="排序")

    class Meta:
        verbose_name = "商品"
        verbose_name_plural = "商品"
        ordering = ["-is_on_sale", "sort", "-id"]

    def __str__(self):
        return self.title


class ProductGalleryImage(BaseModel):
    """商品图片列表中的素材库图片。"""

    product = models.ForeignKey(
        Product, related_name="gallery_images", on_delete=models.CASCADE, verbose_name="商品"
    )
    asset = models.ForeignKey(
        Asset, related_name="gallery_products", on_delete=models.PROTECT, verbose_name="素材"
    )
    sort = models.IntegerField(default=0, verbose_name="排序")

    class Meta:
        verbose_name = "商品图片"
        verbose_name_plural = "商品图片"
        ordering = ["sort", "id"]
        unique_together = ("product", "asset")

    def __str__(self):
        return f"{self.product} - {self.asset}"


class Banner(BaseModel):
    """首页轮播图。"""

    image = models.URLField(max_length=512, verbose_name="图片")
    asset = models.ForeignKey(
        Asset,
        null=True,
        blank=True,
        related_name="banners",
        on_delete=models.SET_NULL,
        verbose_name="素材库图片",
    )
    link = models.CharField(max_length=256, blank=True, verbose_name="跳转链接")
    sort = models.IntegerField(default=0, verbose_name="排序")

    class Meta:
        verbose_name = "轮播图"
        verbose_name_plural = "轮播图"
        ordering = ["sort", "id"]

    def __str__(self):
        return self.image


class MallUser(BaseModel):
    """商城用户。uid 为对外身份标识(默认取 openid),各接口通过 uid 定位用户。"""

    uid = models.CharField(max_length=64, unique=True, verbose_name="用户ID")
    openid = models.CharField(max_length=64, blank=True, verbose_name="OpenID")
    nickname = models.CharField(max_length=64, default="微信用户", verbose_name="昵称")
    avatar_url = models.URLField(max_length=512, blank=True, verbose_name="头像")
    phone = models.CharField(max_length=32, blank=True, verbose_name="手机号")

    class Meta:
        verbose_name = "商城用户"
        verbose_name_plural = "商城用户"

    def __str__(self):
        return self.nickname


class Address(BaseModel):
    """收货地址。"""

    user = models.ForeignKey(MallUser, related_name="addresses", on_delete=models.CASCADE, verbose_name="所属用户")
    name = models.CharField(max_length=64, verbose_name="收货人")
    phone = models.CharField(max_length=32, verbose_name="手机号")
    province = models.CharField(max_length=64, blank=True, verbose_name="省")
    city = models.CharField(max_length=64, blank=True, verbose_name="市")
    district = models.CharField(max_length=64, blank=True, verbose_name="区/县")
    detail = models.CharField(max_length=256, verbose_name="详细地址")
    is_default = models.BooleanField(default=False, verbose_name="是否默认")

    class Meta:
        verbose_name = "收货地址"
        verbose_name_plural = "收货地址"

    def __str__(self):
        return f"{self.name} {self.phone}"


class CartItem(BaseModel):
    """购物车条目。同一用户 + 同一商品唯一。"""

    user = models.ForeignKey(MallUser, related_name="cart_items", on_delete=models.CASCADE, verbose_name="所属用户")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="商品")
    quantity = models.IntegerField(default=1, verbose_name="数量")
    is_selected = models.BooleanField(default=True, verbose_name="是否选中")

    class Meta:
        verbose_name = "购物车"
        verbose_name_plural = "购物车"
        unique_together = ("user", "product")

    def __str__(self):
        return f"cart {self.user_id} -> {self.product_id} x{self.quantity}"


class Order(BaseModel):
    """订单。下单时把收货地址与商品快照冗余进 JSON,避免后续修改影响历史订单。"""

    ORDER_STATUS = (
        (0, "待付款"),
        (1, "待发货"),
        (2, "待收货"),
        (3, "已完成"),
        (4, "已取消"),
    )
    order_no = models.CharField(max_length=64, unique=True, verbose_name="订单号")
    user = models.ForeignKey(MallUser, related_name="orders", on_delete=models.CASCADE, verbose_name="所属用户")
    status = models.IntegerField(choices=ORDER_STATUS, default=0, verbose_name="订单状态")
    total_amount = models.BigIntegerField(default=0, verbose_name="商品总额(分)")
    payment_amount = models.BigIntegerField(default=0, verbose_name="实付金额(分)")
    remark = models.CharField(max_length=256, blank=True, verbose_name="备注")
    # 收货地址快照
    receiver_name = models.CharField(max_length=64, blank=True, verbose_name="收货人")
    receiver_phone = models.CharField(max_length=32, blank=True, verbose_name="收货电话")
    receiver_address = models.CharField(max_length=512, blank=True, verbose_name="收货地址")
    pay_time = models.DateTimeField(null=True, blank=True, verbose_name="支付时间")

    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"
        ordering = ["-id"]

    def __str__(self):
        return self.order_no


class OrderItem(BaseModel):
    """订单明细。商品信息冗余快照,商品删除/改价不影响历史订单。"""

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE, verbose_name="所属订单")
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL, verbose_name="商品")
    goods_name = models.CharField(max_length=256, verbose_name="商品名称")
    goods_image = models.URLField(max_length=512, blank=True, verbose_name="商品图片")
    price = models.BigIntegerField(default=0, verbose_name="成交单价(分)")
    quantity = models.IntegerField(default=1, verbose_name="数量")
    item_total = models.BigIntegerField(default=0, verbose_name="小计金额(分)")

    class Meta:
        verbose_name = "订单明细"
        verbose_name_plural = "订单明细"

    def __str__(self):
        return self.goods_name
