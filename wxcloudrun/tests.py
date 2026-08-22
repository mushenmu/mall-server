import json

from django.test import TestCase

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


class GoodsApiTests(TestCase):
    def test_invalid_pagination_returns_validation_error(self):
        response = self.client.get(
            "/api/goods/list",
            {"pageNum": "not-a-number", "pageSize": "10"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
