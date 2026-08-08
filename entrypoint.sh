#!/bin/sh
# 容器启动入口:迁移数据库 -> 空库时初始化演示数据 -> 启动服务
set -e

echo "[entrypoint] 执行数据库迁移..."
python3 manage.py migrate --noinput

echo "[entrypoint] 检查演示数据..."
python3 -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wxcloudrun.settings')
django.setup()
from wxcloudrun.models import Product
if not Product.objects.exists():
    print('[entrypoint] 商品表为空,初始化演示数据...')
    from django.core.management import call_command
    call_command('seed')
else:
    print('[entrypoint] 已有商品数据,跳过 seed')
"

echo "[entrypoint] 启动服务..."
exec python3 manage.py runserver 0.0.0.0:80
