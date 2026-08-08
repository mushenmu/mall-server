# mushenmu-mall-server(木神木简单商城 · 后端)

微信云托管 Django 模板改造的**简单商城后端**:商品、分类、轮播、购物车、
订单、收货地址、微信登录,配套小程序前端为同目录下的
[`mushenmu-mall-mini`](../mushenmu-mall-mini)。

## 快速开始(本地开发)

```bash
# 1. 安装依赖(本地无 MySQL 环境变量时自动使用 SQLite)
pip install -r requirements.txt

# 2. 迁移数据库 + 灌入演示数据
python manage.py migrate
python manage.py seed

# 3. 启动服务
python manage.py runserver 0.0.0.0:8000

# 4. 创建后台管理员(可选)
python manage.py createsuperuser   # 管理后台:http://127.0.0.1:8000/admin/
```

> 微信开发者工具中打开 `mushenmu-mall-mini`,勾选「不校验合法域名」,
> 即可本地联调(后端跑在 8000 端口)。

## 部署(微信云托管)

与模板一致:配置好环境变量后构建部署即可。

| 环境变量 | 说明 |
| --- | --- |
| `MYSQL_ADDRESS` | MySQL 连接地址 `host:port`(设置后自动使用 MySQL) |
| `MYSQL_USERNAME` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | MySQL 账号信息 |
| `WX_APPID` / `WX_SECRET` | 小程序 AppID / AppSecret(设置后登录走微信官方 jscode2session) |

未配置 `WX_APPID`/`WX_SECRET` 时,登录接口进入开发模式:任意 code
映射到同一个 mock openid,本地联调无需真实密钥。

## API 一览

统一响应信封:`{"data": ..., "code": "Success", "msg": ..., "success": true}`
价格字段单位为「分」(整数),前端展示时除以 100。

### 首页 / 分类 / 商品

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/home` | 轮播图 + 分类宫格 + 热门商品 |
| GET | `/api/category/list` | 分类树(两级) |
| GET | `/api/goods/list` | 商品列表/搜索:`keyword` `categoryId` `pageNum` `pageSize` `sort`(sales/priceAsc/priceDesc) |
| GET | `/api/goods/detail?id=` | 商品详情 |
| GET | `/api/search/popular` | 热门搜索词(演示) |

### 用户 / 地址

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/user/login` | 微信登录:`{code, nickName?, avatarUrl?}` → `{uid, isNewUser, userInfo}` |
| GET | `/api/user/center?uid=` | 用户信息 + 各状态订单数量 |
| GET | `/api/address/list?uid=` | 地址列表 |
| POST | `/api/address/save` | 新增/编辑地址(带 `id` 为编辑) |
| POST | `/api/address/delete` | 删除地址 |

### 购物车

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/cart?uid=` | 购物车列表 + 选中合计 |
| POST | `/api/cart/add` | 加购 `{uid, productId, quantity?}`(重复加购自动累加) |
| POST | `/api/cart/update` | 更新 `{uid, id, quantity?/isSelected?}` |
| POST | `/api/cart/delete` | 删除 `{uid, ids: [...]}` |

### 订单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/order/commit` | 下单 `{uid, addressId, remark?, items:[{productId, quantity}]}`(扣库存、清购物车) |
| GET | `/api/order/list?uid=&status=` | 订单列表(status 空=全部) |
| GET | `/api/order/detail?orderNo=` | 订单详情 |
| POST | `/api/order/pay` | 模拟支付(待付款 → 待发货) |
| POST | `/api/order/cancel` | 取消订单(回补库存) |
| POST | `/api/order/confirm` | 确认收货 |

## 订单状态

| 值 | 含义 |
| --- | --- |
| 0 | 待付款 |
| 1 | 待发货 |
| 2 | 待收货 |
| 3 | 已完成 |
| 4 | 已取消 |

## 目录结构

```
mushenmu-mall-server/
├── Dockerfile                  云托管镜像
├── manage.py                   Django 管理入口
├── requirements.txt            依赖(Django 3.2 + PyMySQL)
└── wxcloudrun/
    ├── models.py               商城数据模型
    ├── views.py                全部 API 视图
    ├── urls.py                 路由
    ├── admin.py                管理后台注册
    ├── settings.py             配置(本地 SQLite / 云端 MySQL 自动切换)
    ├── management/commands/seed.py   演示数据初始化
    └── templates/index.html    落地页
```

## License

[MIT](./LICENSE)
