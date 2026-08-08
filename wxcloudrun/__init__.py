"""wxcloudrun 应用包初始化。

微信云托管部署使用 MySQL,通过 PyMySQL 伪装成 MySQLdb 驱动,
仅在设置了 MYSQL_ADDRESS 环境变量(即使用 MySQL)时才加载;
本地开发使用 SQLite,无需安装 PyMySQL。
"""
import os

if os.environ.get("MYSQL_ADDRESS"):
    import pymysql

    pymysql.install_as_MySQLdb()
