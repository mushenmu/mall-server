"""管理后台注册:在 Django admin 中管理商城数据。"""
from django.contrib import admin
from django import forms
from django.utils.html import format_html

from . import models


def thumbnail(url, alt="图片"):
    if not url:
        return format_html('<span style="color:#999">暂无图片</span>')
    return format_html(
        '<img src="{}" alt="{}" style="width:80px;height:60px;object-fit:cover;'
        'border-radius:4px;border:1px solid #ddd;background:#f5f5f5;" />',
        url,
        alt,
    )


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = models.Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False


class BannerAdminForm(forms.ModelForm):
    class Meta:
        model = models.Banner
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False


@admin.register(models.Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("id", "preview", "name", "file", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("name", "file")}),
        ("系统信息", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="缩略图")
    def preview(self, obj):
        return thumbnail(obj.url, obj.name)


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "parent", "sort", "created_at")
    list_filter = ("parent",)
    search_fields = ("name",)


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("id", "preview", "title", "category", "price", "stock", "sales", "is_on_sale", "sort")
    list_filter = ("is_on_sale", "category")
    search_fields = ("title",)
    list_editable = ("is_on_sale", "sort", "stock")
    fields = (
        "title", "subtitle", "primary_asset", "image", "category", "price",
        "stock", "sales", "tags", "detail", "is_on_sale", "sort",
    )
    inlines = []

    def save_model(self, request, obj, form, change):
        if obj.primary_asset:
            obj.image = obj.primary_asset.url
        super().save_model(request, obj, form, change)

    @admin.display(description="缩略图")
    def preview(self, obj):
        url = obj.primary_asset.url if obj.primary_asset and obj.primary_asset.file else obj.image
        return thumbnail(url, obj.title)


class ProductGalleryImageInline(admin.TabularInline):
    model = models.ProductGalleryImage
    extra = 1
    autocomplete_fields = ("asset",)
    fields = ("asset", "sort")


ProductAdmin.inlines = [ProductGalleryImageInline]


@admin.register(models.Banner)
class BannerAdmin(admin.ModelAdmin):
    form = BannerAdminForm
    list_display = ("id", "preview", "link", "sort")
    fields = ("asset", "image", "link", "sort")


    def save_model(self, request, obj, form, change):
        if obj.asset:
            obj.image = obj.asset.url
        super().save_model(request, obj, form, change)

    @admin.display(description="缩略图")
    def preview(self, obj):
        url = obj.asset.url if obj.asset and obj.asset.file else obj.image
        return thumbnail(url, "轮播图")


@admin.register(models.MallUser)
class MallUserAdmin(admin.ModelAdmin):
    list_display = ("id", "uid", "nickname", "phone", "created_at")
    search_fields = ("uid", "nickname", "phone")


@admin.register(models.Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "name", "phone", "detail", "is_default")
    search_fields = ("name", "phone", "detail")


@admin.register(models.CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "quantity", "is_selected")


class OrderItemInline(admin.TabularInline):
    model = models.OrderItem
    extra = 0
    readonly_fields = ("goods_name", "goods_image", "price", "quantity", "item_total")


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "user", "status", "payment_amount", "receiver_name", "created_at")
    list_filter = ("status",)
    search_fields = ("order_no", "receiver_name", "receiver_phone")
    inlines = [OrderItemInline]
    readonly_fields = ("order_no", "total_amount", "payment_amount")


@admin.register(models.OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "goods_name", "price", "quantity", "item_total")
    search_fields = ("goods_name",)
