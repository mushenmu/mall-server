"""初始化演示数据:分类 / 轮播图 / 商品 / 演示用户与地址。

运行方式(先执行 migrate):
    python manage.py migrate
    python manage.py seed
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from wxcloudrun import models

CDN = "https://tdesign.gtimg.com/miniprogram/template/retail"

CATEGORIES = [
    # (名称, 图标, 父分类名, 排序)
    ("女装", "category/category-default.png", None, 1),
    ("卫衣", "classify/img-1.png", "女装", 1),
    ("连衣裙", "classify/img-9.png", "女装", 2),
    ("半身裙", "classify/img-10.png", "女装", 3),
    ("男装", "category/category-default.png", None, 2),
    ("卫衣", "classify/img-1.png", "男装", 1),
    ("裤子", "classify/img-11.png", "男装", 2),
    ("美妆", "category/category-default.png", None, 3),
    ("唇釉", "goods/mz-20a1.png", "美妆", 1),
    ("数码", "category/category-default.png", None, 4),
    ("手机配件", "classify/img-12.png", "数码", 1),
]

PRODUCTS = [
    # (标题, 图片, 售价分, 原价分, 库存, 销量, (父分类, 子分类) 或 顶级分类名, 标签)
    ("白色短袖连衣裙荷叶边裙摆宽松韩版休闲纯白清爽优雅连衣裙", "goods/nz-09a.png", 29800, 40000, 510, 1020, ("女装", "连衣裙"), ["限时抢购"]),
    ("纯色纯棉休闲圆领短袖T恤纯白亲肤厚柔软细腻面料短袖套头T恤", "goods/nz-08b.png", 25900, 31900, 320, 880, ("女装", "卫衣"), ["2024夏季新款"]),
    ("带帽午休毯多功能加厚加大加绒简约连帽披肩", "goods/muy-3a.png", 29900, 0, 200, 430, "女装", ["火爆"]),
    ("运动连帽拉链卫衣休闲开衫长袖多色细绒面料运动上衣", "goods/nz-17a.png", 25900, 39900, 60, 540, ("男装", "卫衣"), ["运动"]),
    ("纯棉针织半身裙复古高腰a字中长裙显瘦百搭半身裙", "goods/nz-09a.png", 19900, 29900, 150, 230, ("女装", "半身裙"), []),
    ("自然堂雪域精粹纯粹滋润霜补水保湿面霜化妆品套装", "goods/mz-20a1.png", 19900, 25900, 80, 670, ("美妆", "唇釉"), ["美妆"]),
    ("不锈钢刀叉勺套装家用西餐餐具简约耐用金色银色可选", "goods/gh-2b.png", 29900, 29900, 90, 320, "女装", []),
    ("腾讯极光盒子智能网络电视机顶盒4K高分辨率网络机顶盒", "goods/dz-3a.png", 9900, 16900, 120, 1560, ("数码", "手机配件"), ["新品"]),
    ("男士休闲直筒裤宽松百搭长裤秋季新款", "goods/nz-17a.png", 21900, 29900, 180, 410, ("男装", "裤子"), []),
    ("轻薄羽绒服短款立领保暖外套男女同款", "goods/nz-08b.png", 39900, 59900, 75, 260, "男装", ["冬季"]),
]

BANNERS = [
    "home/v2/banner1.png",
    "home/v2/banner2.png",
    "home/v2/banner3.png",
    "home/v2/banner4.png",
]


class Command(BaseCommand):
    help = "初始化简单商城演示数据"

    @transaction.atomic
    def handle(self, *args, **options):
        # 分类(先建父分类,再建子分类)
        self.stdout.write("初始化分类...")
        cat_map = {}
        for name, icon, parent_name, sort in CATEGORIES:
            parent = cat_map.get(parent_name) if parent_name else None
            cat, _ = models.Category.objects.update_or_create(
                name=name, parent=parent,
                defaults={"icon": f"{CDN}/{icon}", "sort": sort},
            )
            # 键用 (父分类名, 本分类名),避免不同父分类下的同名子分类互相覆盖
            cat_map[(parent_name, name)] = cat
            cat_map[name] = cat  # 兼容顶级分类用名称直接引用

        # 轮播图
        self.stdout.write("初始化轮播图...")
        for i, b in enumerate(BANNERS):
            models.Banner.objects.update_or_create(
                image=f"{CDN}/{b}", defaults={"sort": i}
            )

        # 商品
        self.stdout.write("初始化商品...")
        for title, img, price, origin, stock, sales, cat_key, tags in PRODUCTS:
            if isinstance(cat_key, tuple):
                cat = cat_map.get(cat_key) or cat_map.get(cat_key[1])
            else:
                cat = cat_map.get(cat_key)
            models.Product.objects.update_or_create(
                title=title,
                defaults={
                    "subtitle": "简单商城演示商品",
                    "image": f"{CDN}/{img}",
                    "images": [f"{CDN}/{img}", f"{CDN}/goods/nz-09c.png"],
                    "price": price,
                    "original_price": origin or price,
                    "stock": stock,
                    "sales": sales,
                    "category": cat,
                    "tags": [{"title": t} for t in tags],
                    "detail": f'<p><img src="{CDN}/goods/nz-09c.png" style="width:100%"/></p>',
                    "is_on_sale": True,
                },
            )

        # 演示用户 + 默认地址
        self.stdout.write("初始化演示用户...")
        user, _ = models.MallUser.objects.update_or_create(
            uid="88888888205468",
            defaults={
                "nickname": "演示用户",
                "avatar_url": f"{CDN}/avatar/avatar-1.jpg",
                "phone": "13438358888",
            },
        )
        models.Address.objects.update_or_create(
            user=user, name="张三", phone="13438358888",
            defaults={
                "province": "广东省", "city": "深圳市", "district": "南山区",
                "detail": "科技园腾讯大厦 1001 室", "is_default": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("演示数据初始化完成。"))
        self.stdout.write(
            "演示账号: uid=88888888205468\n"
            "后台地址: /admin (需先 createsuperuser)"
        )
