"""wxcloudrun URL Configuration

商城 API 路由。所有接口位于 /api/ 前缀,响应信封见 views.envelope。
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path

from wxcloudrun import views
from wxcloudrun.views import index

urlpatterns = [
    # 管理后台
    path("admin/", admin.site.urls),
    # 首页 / 分类 / 商品
    path("api/home", views.home, name="home"),
    path("api/category/list", views.category_list, name="category-list"),
    path("api/goods/list", views.goods_list, name="goods-list"),
    path("api/goods/detail", views.goods_detail, name="goods-detail"),
    path("api/search/popular", views.search_popular, name="search-popular"),
    # 用户 / 登录
    path("api/user/login", views.user_login, name="user-login"),
    path("api/user/center", views.user_center, name="user-center"),
    # 收货地址
    path("api/address/list", views.address_list, name="address-list"),
    path("api/address/save", views.address_save, name="address-save"),
    path("api/address/delete", views.address_delete, name="address-delete"),
    # 购物车
    path("api/cart", views.cart, name="cart"),
    path("api/cart/add", views.cart_add, name="cart-add"),
    path("api/cart/update", views.cart_update, name="cart-update"),
    path("api/cart/delete", views.cart_delete, name="cart-delete"),
    # 订单
    path("api/order/commit", views.order_commit, name="order-commit"),
    path("api/order/list", views.order_list, name="order-list"),
    path("api/order/detail", views.order_detail, name="order-detail"),
    path("api/order/pay", views.order_pay, name="order-pay"),
    path("api/order/cancel", views.order_cancel, name="order-cancel"),
    path("api/order/confirm", views.order_confirm, name="order-confirm"),
    # 主页
    re_path(r"(/)?$", index),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
