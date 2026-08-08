"""简单商城 API 视图。

响应统一信封格式(与小程序端 request.js 的约定一致):
    {"data": ..., "code": "Success", "msg": null, "success": true}

价格字段单位为「分」(整数),前端展示时除以 100。
用户身份:小程序端通过 uid 参数定位用户(uid 默认取 openid)。
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import models

# 演示数据图片 CDN(与 mall-server 一致的 TDesign 零售模板素材)
CDN = "https://tdesign.gtimg.com/miniprogram/template/retail"


def index(request, _=None):
    """获取主页(云托管模板落地页)。"""
    from django.shortcuts import render
    return render(request, "index.html")


def envelope(data, code="Success", msg=None, success=True, status=200):
    return JsonResponse(
        {
            "data": data,
            "code": code,
            "msg": msg,
            "success": success,
        },
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def _get_or_create_user(uid):
    """按 uid 查找用户,不存在则创建(演示模式自动建号)。"""
    uid = (uid or "").strip() or "mock_user"
    user, _ = models.MallUser.objects.get_or_create(
        uid=uid, defaults={"nickname": "微信用户"}
    )
    return user


def _product_dict(p):
    return {
        "id": p.id,
        "title": p.title,
        "subtitle": p.subtitle,
        "image": p.image,
        "images": p.images or [p.image],
        "price": p.price,
        "originalPrice": p.original_price,
        "stock": p.stock,
        "sales": p.sales,
        "tags": p.tags or [],
        "categoryId": p.category_id,
        "detail": p.detail,
        "isOnSale": p.is_on_sale,
    }


# ---------------------------------------------------------------------------
# 首页 / 分类 / 商品
# ---------------------------------------------------------------------------
@require_GET
def home(request):
    """首页聚合:轮播图 + 分类宫格 + 热门商品。"""
    banners = [
        {"image": b.image, "link": b.link}
        for b in models.Banner.objects.order_by("sort", "id")
    ]
    if not banners:
        banners = [
            {"image": f"{CDN}/home/v2/banner1.png", "link": ""},
            {"image": f"{CDN}/home/v2/banner2.png", "link": ""},
            {"image": f"{CDN}/home/v2/banner3.png", "link": ""},
        ]
    categories = [
        {"id": c.id, "name": c.name, "icon": c.icon or f"{CDN}/category/category-default.png"}
        for c in models.Category.objects.filter(parent__isnull=True).order_by("sort", "id")
    ]
    hot = models.Product.objects.filter(is_on_sale=True).order_by("-sales", "-id")[:8]
    data = {
        "swiper": banners,
        "categoryList": categories,
        "hotGoods": [_product_dict(p) for p in hot],
    }
    return envelope(data)


@require_GET
def category_list(request):
    """分类列表(两级:父分类带 children)。"""
    roots = models.Category.objects.filter(parent__isnull=True).order_by("sort", "id")
    data = [
        {
            "id": c.id,
            "name": c.name,
            "icon": c.icon or f"{CDN}/category/category-default.png",
            "children": [
                {"id": ch.id, "name": ch.name, "icon": ch.icon}
                for ch in c.children.order_by("sort", "id")
            ],
        }
        for c in roots
    ]
    return envelope(data)


@require_GET
def goods_list(request):
    """商品列表 / 搜索。

    Query: keyword, categoryId, pageNum, pageSize, sort
    sort: ""(综合) | "sales"(销量) | "priceAsc" | "priceDesc"
    """
    keyword = request.GET.get("keyword", "").strip()
    category_id = request.GET.get("categoryId", "").strip()
    page_num = max(1, int(request.GET.get("pageNum", 1) or 1))
    page_size = min(100, max(1, int(request.GET.get("pageSize", 20) or 20)))
    sort = request.GET.get("sort", "").strip()

    qs = models.Product.objects.filter(is_on_sale=True)
    if keyword:
        qs = qs.filter(title__icontains=keyword)
    if category_id:
        # 兼容:传入的是子分类或父分类,父分类时包含其所有子分类商品
        try:
            cat = models.Category.objects.get(id=category_id)
        except (models.Category.DoesNotExist, ValueError):
            cat = None
        cat_ids = [cat.id] if cat else []
        if cat:
            cat_ids += [ch.id for ch in cat.children.all()]
        qs = qs.filter(category_id__in=cat_ids)

    total = qs.count()
    if sort == "sales":
        qs = qs.order_by("-sales", "-id")
    elif sort == "priceAsc":
        qs = qs.order_by("price", "id")
    elif sort == "priceDesc":
        qs = qs.order_by("-price", "id")
    else:
        qs = qs.order_by("sort", "-id")

    page = qs[(page_num - 1) * page_size: page_num * page_size]
    data = {
        "list": [_product_dict(p) for p in page],
        "totalCount": total,
        "pageNum": page_num,
        "pageSize": page_size,
    }
    return envelope(data)


@require_GET
def goods_detail(request):
    """商品详情。Query: id"""
    pid = request.GET.get("id", "").strip()
    p = models.Product.objects.filter(id=pid, is_on_sale=True).first()
    if not p:
        return envelope(None, code="NotFound", msg="商品不存在", success=False, status=404)
    return envelope(_product_dict(p))


@require_GET
def search_popular(request):
    """热门搜索词(演示)。"""
    return envelope({"popularWords": ["连衣裙", "T恤", "卫衣", "保温杯", "数据线"]})


# ---------------------------------------------------------------------------
# 用户 / 登录
# ---------------------------------------------------------------------------
@csrf_exempt
@require_POST
def user_login(request):
    """微信登录:wx.login() 拿 code 换 openid,返回 uid。

    未配置 WX_APPID/WX_SECRET(开发模式)时,任意 code 映射到 mock openid,
    开发者工具无需真实密钥即可联调;配置后自动走微信 jscode2session。
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    code = (body.get("code") or "").strip()
    if not code:
        return envelope(None, code="Error", msg="缺少 code 参数", success=False, status=400)

    openid = _exchange_code_for_openid(code)
    if not openid:
        return envelope(None, code="Error", msg="code 换取 openid 失败", success=False, status=401)

    user = models.MallUser.objects.filter(openid=openid).first()
    is_new = user is None
    if is_new:
        try:
            user = models.MallUser.objects.create(uid=openid[:64], openid=openid, nickname="微信用户")
        except IntegrityError:  # 并发兜底
            user = models.MallUser.objects.filter(openid=openid).first()
            is_new = False

    # 可选:登录时更新昵称/头像
    nick_name = (body.get("nickName") or "").strip()
    avatar_url = (body.get("avatarUrl") or "").strip()
    changed = False
    if nick_name and nick_name != user.nickname:
        user.nickname = nick_name
        changed = True
    if avatar_url and avatar_url != user.avatar_url:
        user.avatar_url = avatar_url
        changed = True
    if changed:
        user.save(update_fields=["nickname", "avatar_url", "updated_at"])

    data = {
        "uid": user.uid,
        "isNewUser": is_new,
        "userInfo": {
            "uid": user.uid,
            "nickName": user.nickname,
            "avatarUrl": user.avatar_url,
            "phoneNumber": user.phone,
        },
    }
    return envelope(data)


def _exchange_code_for_openid(code):
    """用 code 向微信服务器换取 openid。开发模式返回固定 mock openid。"""
    appid = (getattr(settings, "WX_APPID", "") or "").strip()
    secret = (getattr(settings, "WX_SECRET", "") or "").strip()
    if not appid or not secret:
        return "mock_openid_dev"
    query = urllib.parse.urlencode(
        {"appid": appid, "secret": secret, "js_code": code, "grant_type": "authorization_code"}
    )
    url = f"https://api.weixin.qq.com/sns/jscode2session?{query}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as exc:
        print(f"[user_login] jscode2session 请求失败: {exc}")
        return None
    if result.get("openid"):
        return result["openid"]
    print(f"[user_login] jscode2session 返回异常: {result}")
    return None


@require_GET
def user_center(request):
    """用户中心:用户信息 + 各状态订单数量。"""
    user = _get_or_create_user(request.GET.get("uid", ""))
    status_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    for s, c in (
        models.Order.objects.filter(user=user)
        .values_list("status")
        .annotate(c=Count("id"))
    ):
        status_counts[s] = c
    data = {
        "userInfo": {
            "uid": user.uid,
            "nickName": user.nickname,
            "avatarUrl": user.avatar_url,
            "phoneNumber": user.phone,
        },
        "orderCounts": [
            {"status": 0, "count": status_counts[0], "label": "待付款"},
            {"status": 1, "count": status_counts[1], "label": "待发货"},
            {"status": 2, "count": status_counts[2], "label": "待收货"},
            {"status": 3, "count": status_counts[3], "label": "已完成"},
            {"status": 4, "count": status_counts[4], "label": "已取消"},
        ],
    }
    return envelope(data)


# ---------------------------------------------------------------------------
# 收货地址
# ---------------------------------------------------------------------------
@require_GET
def address_list(request):
    """地址列表。Query: uid"""
    user = _get_or_create_user(request.GET.get("uid", ""))
    addrs = models.Address.objects.filter(user=user).order_by("-is_default", "-id")
    data = [
        {
            "id": a.id,
            "name": a.name,
            "phone": a.phone,
            "province": a.province,
            "city": a.city,
            "district": a.district,
            "detail": a.detail,
            "fullAddress": f"{a.province}{a.city}{a.district}{a.detail}",
            "isDefault": a.is_default,
        }
        for a in addrs
    ]
    return envelope({"list": data})


@csrf_exempt
@require_POST
def address_save(request):
    """新增/编辑地址。body: { uid, id?, name, phone, province, city, district, detail, isDefault }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    addr_id = body.get("id")
    defaults = {
        "user": user,
        "name": body.get("name", ""),
        "phone": body.get("phone", ""),
        "province": body.get("province", ""),
        "city": body.get("city", ""),
        "district": body.get("district", ""),
        "detail": body.get("detail", ""),
        "is_default": bool(body.get("isDefault", False)),
    }
    with transaction.atomic():
        obj, created = models.Address.objects.update_or_create(
            id=addr_id, defaults=defaults
        ) if addr_id else (models.Address.objects.create(**defaults), True)
        if obj.is_default:
            models.Address.objects.filter(user=user).exclude(id=obj.id).update(is_default=False)
    return envelope({"id": obj.id, "created": created})


@csrf_exempt
@require_POST
def address_delete(request):
    """删除地址。body: { uid, id }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    models.Address.objects.filter(user=user, id=body.get("id")).delete()
    return envelope({"deleted": True})


# ---------------------------------------------------------------------------
# 购物车
# ---------------------------------------------------------------------------
@require_GET
def cart(request):
    """购物车列表。Query: uid"""
    user = _get_or_create_user(request.GET.get("uid", ""))
    items = models.CartItem.objects.filter(user=user).select_related("product").order_by("-id")
    list_data = []
    for it in items:
        p = it.product
        if not p.is_on_sale:
            continue
        list_data.append(
            {
                "id": it.id,
                "productId": p.id,
                "title": p.title,
                "image": p.image,
                "price": p.price,
                "originalPrice": p.original_price,
                "quantity": it.quantity,
                "isSelected": it.is_selected,
                "stock": p.stock,
            }
        )
    total_amount = sum(
        it["price"] * it["quantity"] for it in list_data if it["isSelected"]
    )
    return envelope({"list": list_data, "totalAmount": total_amount, "isNotEmpty": bool(list_data)})


@csrf_exempt
@require_POST
def cart_add(request):
    """加入购物车。body: { uid, productId, quantity? } 已存在则数量累加。"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    product = models.Product.objects.filter(id=body.get("productId"), is_on_sale=True).first()
    if not product:
        return envelope(None, code="Error", msg="商品不存在", success=False, status=404)
    quantity = max(1, int(body.get("quantity", 1) or 1))

    obj, created = models.CartItem.objects.get_or_create(
        user=user, product=product,
        defaults={"quantity": quantity, "is_selected": True},
    )
    if not created:
        obj.quantity = min(product.stock, obj.quantity + quantity)
        obj.is_selected = True
        obj.save(update_fields=["quantity", "is_selected", "updated_at"])
    return envelope({"id": obj.id, "quantity": obj.quantity})


@csrf_exempt
@require_POST
def cart_update(request):
    """更新购物车条目。body: { uid, id, quantity?, isSelected? }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    item = models.CartItem.objects.filter(user=user, id=body.get("id")).select_related("product").first()
    if not item:
        return envelope(None, code="Error", msg="购物车条目不存在", success=False, status=404)
    if "quantity" in body:
        item.quantity = max(1, min(item.product.stock, int(body["quantity"] or 1)))
    if "isSelected" in body:
        item.is_selected = bool(body["isSelected"])
    item.save(update_fields=["quantity", "is_selected", "updated_at"])
    return envelope({"id": item.id, "quantity": item.quantity, "isSelected": item.is_selected})


@csrf_exempt
@require_POST
def cart_delete(request):
    """删除购物车条目。body: { uid, ids: [..] 或 id }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    ids = body.get("ids") or ([body["id"]] if body.get("id") else [])
    models.CartItem.objects.filter(user=user, id__in=ids).delete()
    return envelope({"deleted": True})


# ---------------------------------------------------------------------------
# 订单
# ---------------------------------------------------------------------------
def _gen_order_no():
    return time.strftime("%Y%m%d%H%M%S") + str(int(time.time() * 1000))[-6:]


@csrf_exempt
@require_POST
def order_commit(request):
    """提交订单(下单)。body: { uid, addressId, remark?, items: [{productId, quantity}] }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    items = body.get("items") or []
    if not items:
        return envelope(None, code="Error", msg="订单商品不能为空", success=False, status=400)

    addr = models.Address.objects.filter(user=user, id=body.get("addressId")).first()
    if not addr:
        return envelope(None, code="Error", msg="请选择收货地址", success=False, status=400)

    products = {
        p.id: p for p in models.Product.objects.filter(
            id__in=[i.get("productId") for i in items], is_on_sale=True
        )
    }
    order_items = []
    total = 0
    for i in items:
        p = products.get(i.get("productId"))
        if not p:
            return envelope(None, code="Error", msg="商品不存在或已下架", success=False, status=400)
        qty = max(1, int(i.get("quantity", 1) or 1))
        if qty > p.stock:
            return envelope(None, code="Error", msg=f"「{p.title}」库存不足", success=False, status=400)
        order_items.append((p, qty))
        total += p.price * qty

    with transaction.atomic():
        order = models.Order.objects.create(
            order_no=_gen_order_no(),
            user=user,
            status=0,
            total_amount=total,
            payment_amount=total,
            remark=(body.get("remark") or "").strip(),
            receiver_name=addr.name,
            receiver_phone=addr.phone,
            receiver_address=f"{addr.province}{addr.city}{addr.district}{addr.detail}",
        )
        for p, qty in order_items:
            models.OrderItem.objects.create(
                order=order, product=p,
                goods_name=p.title, goods_image=p.image,
                price=p.price, quantity=qty, item_total=p.price * qty,
            )
            # 扣库存、加销量
            models.Product.objects.filter(id=p.id).update(
                stock=F("stock") - qty, sales=F("sales") + qty
            )
        # 清掉购物车中对应的商品(无论是否选中)
        models.CartItem.objects.filter(
            user=user, product_id__in=[p.id for p, _ in order_items]
        ).delete()

    return envelope({
        "orderNo": order.order_no,
        "paymentAmount": order.payment_amount,
        "status": order.status,
    })


@require_GET
def order_list(request):
    """订单列表。Query: uid, status?(空=全部)"""
    user = _get_or_create_user(request.GET.get("uid", ""))
    qs = models.Order.objects.filter(user=user)
    status = request.GET.get("status", "").strip()
    if status != "":
        qs = qs.filter(status=int(status))
    qs = qs.prefetch_related("items")
    data = []
    for o in qs:
        first = o.items.first()
        data.append(
            {
                "orderNo": o.order_no,
                "status": o.status,
                "statusLabel": dict(models.Order.ORDER_STATUS)[o.status],
                "totalAmount": o.total_amount,
                "paymentAmount": o.payment_amount,
                "goodsCount": sum(i.quantity for i in o.items.all()),
                "firstImage": first.goods_image if first else "",
                "title": first.goods_name if first else "",
                "createTime": o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return envelope({"list": data})


@require_GET
def order_detail(request):
    """订单详情。Query: orderNo"""
    order = models.Order.objects.filter(order_no=request.GET.get("orderNo", "")).first()
    if not order:
        return envelope(None, code="NotFound", msg="订单不存在", success=False, status=404)
    items = [
        {
            "productId": i.product_id,
            "goodsName": i.goods_name,
            "goodsImage": i.goods_image,
            "price": i.price,
            "quantity": i.quantity,
            "itemTotal": i.item_total,
        }
        for i in order.items.all()
    ]
    data = {
        "orderNo": order.order_no,
        "status": order.status,
        "statusLabel": dict(models.Order.ORDER_STATUS)[order.status],
        "totalAmount": order.total_amount,
        "paymentAmount": order.payment_amount,
        "remark": order.remark,
        "receiver": {
            "name": order.receiver_name,
            "phone": order.receiver_phone,
            "address": order.receiver_address,
        },
        "createTime": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "items": items,
    }
    return envelope(data)


@csrf_exempt
@require_POST
def order_pay(request):
    """模拟支付(演示:直接置为待发货)。body: { uid, orderNo }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    order = models.Order.objects.filter(user=user, order_no=body.get("orderNo", "")).first()
    if not order:
        return envelope(None, code="Error", msg="订单不存在", success=False, status=404)
    if order.status != 0:
        return envelope(None, code="Error", msg="订单状态不允许支付", success=False, status=400)
    order.status = 1
    order.pay_time = datetime.now()
    order.save(update_fields=["status", "pay_time", "updated_at"])
    return envelope({"orderNo": order.order_no, "status": order.status})


@csrf_exempt
@require_POST
def order_cancel(request):
    """取消订单(仅待付款可取消,并回补库存)。body: { uid, orderNo }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    order = models.Order.objects.filter(user=user, order_no=body.get("orderNo", "")).first()
    if not order:
        return envelope(None, code="Error", msg="订单不存在", success=False, status=404)
    if order.status != 0:
        return envelope(None, code="Error", msg="订单状态不允许取消", success=False, status=400)
    with transaction.atomic():
        for i in order.items.all():
            if i.product_id:
                models.Product.objects.filter(id=i.product_id).update(
                    stock=F("stock") + i.quantity,
                    sales=F("sales") - i.quantity,
                )
        order.status = 4
        order.save(update_fields=["status", "updated_at"])
    return envelope({"orderNo": order.order_no, "status": order.status})


@csrf_exempt
@require_POST
def order_confirm(request):
    """确认收货。body: { uid, orderNo }"""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        body = {}
    user = _get_or_create_user(body.get("uid", ""))
    order = models.Order.objects.filter(user=user, order_no=body.get("orderNo", "")).first()
    if not order:
        return envelope(None, code="Error", msg="订单不存在", success=False, status=404)
    if order.status != 2:
        return envelope(None, code="Error", msg="订单状态不允许确认收货", success=False, status=400)
    order.status = 3
    order.save(update_fields=["status", "updated_at"])
    return envelope({"orderNo": order.order_no, "status": order.status})
