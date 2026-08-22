import json
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from . import models


class UserLoginTests(TestCase):
    def test_login_binds_existing_uid_created_by_anonymous_api(self):
        existing = models.MallUser.objects.create(
            uid="mock_openid_dev",
            openid="",
            nickname="临时用户",
        )

        response = self.client.post(
            "/api/user/login",
            data=json.dumps({"code": "dev-code"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["uid"], existing.uid)
        self.assertEqual(models.MallUser.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.openid, "mock_openid_dev")


class AddressApiTests(TestCase):
    def test_user_cannot_overwrite_another_users_address(self):
        owner = models.MallUser.objects.create(uid="owner")
        attacker = models.MallUser.objects.create(uid="attacker")
        address = models.Address.objects.create(
            user=owner,
            name="原收货人",
            phone="13800000000",
            detail="原地址",
        )

        response = self.client.post(
            "/api/address/save",
            data=json.dumps({
                "uid": attacker.uid,
                "id": address.id,
                "name": "被篡改",
                "phone": "13900000000",
                "detail": "攻击者地址",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        address.refresh_from_db()
        self.assertEqual(address.user, owner)
        self.assertEqual(address.name, "原收货人")

    def test_required_address_fields_are_validated(self):
        response = self.client.post(
            "/api/address/save",
            data=json.dumps({"uid": "address-user", "name": "", "phone": "123"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.Address.objects.count(), 0)


class OrderApiTests(TestCase):
    def test_sequential_orders_cannot_exceed_remaining_stock(self):
        user = models.MallUser.objects.create(uid="stock-buyer")
        address = models.Address.objects.create(
            user=user, name="买家", phone="13800000000", detail="测试地址"
        )
        product = models.Product.objects.create(
            title="顺序限量商品",
            image="https://example.com/sequential.png",
            price=1000,
            stock=2,
            sales=3,
            is_on_sale=True,
        )
        payload = {
            "uid": user.uid,
            "addressId": address.id,
            "items": [{"productId": product.id, "quantity": 2}],
        }

        first = self.client.post(
            "/api/order/commit", data=json.dumps(payload), content_type="application/json"
        )
        second = self.client.post(
            "/api/order/commit",
            data=json.dumps({**payload, "items": [{"productId": product.id, "quantity": 1}]}),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["code"], "OutOfStock")
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(product.sales, 5)

    def test_order_detail_is_only_visible_to_its_owner(self):
        owner = models.MallUser.objects.create(uid="order-owner")
        attacker = models.MallUser.objects.create(uid="order-attacker")
        order = models.Order.objects.create(
            order_no="ORDER-PRIVATE",
            user=owner,
            total_amount=100,
            payment_amount=100,
        )

        response = self.client.get(
            "/api/order/detail",
            {"uid": attacker.uid, "orderNo": order.order_no},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])

    def test_invalid_order_status_filter_returns_validation_error(self):
        response = self.client.get(
            "/api/order/list",
            {"uid": "order-user", "status": "unknown"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_duplicate_product_lines_cannot_oversell_stock(self):
        user = models.MallUser.objects.create(uid="buyer")
        address = models.Address.objects.create(
            user=user, name="买家", phone="13800000000", detail="测试地址"
        )
        product = models.Product.objects.create(
            title="限量商品",
            image="https://example.com/product.png",
            price=1000,
            stock=5,
            is_on_sale=True,
        )

        response = self.client.post(
            "/api/order/commit",
            data=json.dumps({
                "uid": user.uid,
                "addressId": address.id,
                "items": [
                    {"productId": product.id, "quantity": 4},
                    {"productId": product.id, "quantity": 4},
                ],
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.Order.objects.count(), 0)
        product.refresh_from_db()
        self.assertEqual(product.stock, 5)


class CartApiTests(TestCase):
    def test_out_of_stock_product_cannot_be_added_to_cart(self):
        user = models.MallUser.objects.create(uid="cart-user")
        product = models.Product.objects.create(
            title="售罄商品",
            image="https://example.com/sold-out.png",
            price=9900,
            stock=0,
            is_on_sale=True,
        )

        response = self.client.post(
            "/api/cart/add",
            data=json.dumps({
                "uid": user.uid,
                "productId": product.id,
                "quantity": 1,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.CartItem.objects.count(), 0)

    def test_cart_quantity_cannot_exceed_remaining_stock(self):
        product = models.Product.objects.create(
            title="限量购物车商品", image="https://example.com/limited.png", price=100, stock=2
        )
        payload = {"uid": "cart-stock-user", "productId": product.id, "quantity": 2}
        first = self.client.post("/api/cart/add", data=json.dumps(payload), content_type="application/json")
        second = self.client.post(
            "/api/cart/add",
            data=json.dumps({**payload, "quantity": 1}),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["code"], "OutOfStock")

    def test_cart_update_rejects_quantity_above_stock(self):
        user = models.MallUser.objects.create(uid="cart-update-stock-user")
        product = models.Product.objects.create(
            title="库存更新商品", image="https://example.com/update.png", price=100, stock=2
        )
        item = models.CartItem.objects.create(user=user, product=product, quantity=1)

        response = self.client.post(
            "/api/cart/update",
            data=json.dumps({"uid": user.uid, "id": item.id, "quantity": 3}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "OutOfStock")
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_product_api_does_not_return_original_price(self):
        product = models.Product.objects.create(
            title="售价商品", image="https://example.com/price.png", price=100, stock=2, sales=7
        )
        response = self.client.get("/api/goods/list")
        item = next(item for item in response.json()["data"]["list"] if item["id"] == product.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(item["sales"], 7)
        self.assertNotIn("originalPrice", item)


class GoodsApiTests(TestCase):
    def test_invalid_pagination_returns_validation_error(self):
        response = self.client.get(
            "/api/goods/list",
            {"pageNum": "not-a-number", "pageSize": "10"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AssetLibraryTests(TestCase):
    def test_uploaded_asset_defaults_name_and_is_used_by_product_gallery(self):
        asset = models.Asset.objects.create(
            file=SimpleUploadedFile("summer-banner.png", b"image", content_type="image/png")
        )
        self.assertEqual(asset.name, "summer-banner")
        self.assertTrue(asset.url.startswith("/media/assets/"))

        product = models.Product.objects.create(
            title="素材商品",
            image=asset.url,
            primary_asset=asset,
            price=100,
            stock=1,
        )
        models.ProductGalleryImage.objects.create(product=product, asset=asset)

        response = self.client.get("/api/goods/detail", {"id": product.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["image"], asset.url)
        self.assertEqual(response.json()["data"]["images"], [asset.url])

    def test_home_uses_banner_asset_url(self):
        asset = models.Asset.objects.create(
            file=SimpleUploadedFile("home-cover.jpg", b"image", content_type="image/jpeg")
        )
        models.Banner.objects.create(image="https://example.com/old.jpg", asset=asset)

        response = self.client.get("/api/home")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["swiper"][0]["image"], asset.url)
