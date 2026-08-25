"""管理后台注册:在 Django admin 中管理商城数据。"""
from django.contrib import admin
from django import forms
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
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
    list_display = (
        "order_no", "user", "status", "payment_amount", "receiver_name",
        "express_summary", "express_action", "created_at",
    )
    list_filter = ("status",)
    search_fields = ("order_no", "receiver_name", "receiver_phone", "express_no", "express_company")
    inlines = [OrderItemInline]
    readonly_fields = ("order_no", "total_amount", "payment_amount", "shipped_at")
    fields = (
        "order_no", "user", "status", "total_amount", "payment_amount", "remark",
        "receiver_name", "receiver_phone", "receiver_address", "pay_time",
        "express_company", "express_company_code", "express_no", "shipped_at",
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/scan-express/",
                self.admin_site.admin_view(self.scan_express_view),
                name="wxcloudrun_order_scan_express",
            ),
        ]
        return custom_urls + urls

    def scan_express_view(self, request, object_id):
        order = self.get_queryset(request).filter(pk=object_id).first()
        if not order:
            self.message_user(request, "订单不存在", level="error")
            return HttpResponseRedirect(reverse("admin:wxcloudrun_order_changelist"))
        if request.method == "POST":
            company = (request.POST.get("express_company") or "").strip()
            company_code = (request.POST.get("express_company_code") or "").strip().lower()
            express_no = (request.POST.get("express_no") or "").strip()
            if not express_no or len(express_no) > 128:
                context = {"order": order, "error": "请输入有效的快递单号(1-128个字符)"}
            else:
                order.express_company = company[:64]
                order.express_company_code = company_code[:32]
                order.express_no = express_no
                order.shipped_at = order.shipped_at or timezone.now()
                if order.status == 1:
                    order.status = 2
                order.save(update_fields=[
                    "express_company", "express_company_code", "express_no",
                    "shipped_at", "status", "updated_at",
                ])
                self.message_user(request, "快递单号已保存，订单已标记为待收货")
                return HttpResponseRedirect(reverse("admin:wxcloudrun_order_changelist"))
        else:
            context = {"order": order}
        context.update({
            **self.admin_site.each_context(request),
            "title": "扫码录入快递单号",
            "opts": self.model._meta,
        })
        return TemplateResponse(request, "admin/wxcloudrun/order/scan_express.html", context)

    @admin.display(description="物流信息")
    def express_summary(self, obj):
        if not obj.express_no:
            return format_html('<span style="color:#999">未填写</span>')
        return format_html("{}<br><small>{}</small>", obj.express_company or "快递", obj.express_no)

    @admin.display(description="操作")
    def express_action(self, obj):
        url = reverse("admin:wxcloudrun_order_scan_express", args=[obj.pk])
        return format_html('<a class="button" href="{}">扫码/录入</a>', url)


@admin.register(models.OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "goods_name", "price", "quantity", "item_total")
    search_fields = ("goods_name",)
