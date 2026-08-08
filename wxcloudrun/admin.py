"""管理后台注册:在 Django admin 中管理商城数据。"""
from django.contrib import admin

from . import models


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "parent", "sort", "created_at")
    list_filter = ("parent",)
    search_fields = ("name",)


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "price", "stock", "sales", "is_on_sale", "sort")
    list_filter = ("is_on_sale", "category")
    search_fields = ("title",)
    list_editable = ("is_on_sale", "sort", "stock")


@admin.register(models.Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("id", "image", "link", "sort")


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
