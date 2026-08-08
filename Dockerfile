# 二开推荐阅读[如何提高项目构建效率](https://developers.weixin.qq.com/miniprogram/dev/wxcloudrun/src/scene/build/speed.html)
# 选择构建用基础镜像（选择原则：在包含所有用到的依赖前提下尽可能体积小）。如需更换，请到[dockerhub官方仓库](https://hub.docker.com/_/python?tab=tags)自行选择后替换。
# 已知alpine镜像与pytorch有兼容性问题会导致构建失败，如需使用pytorch请务必按需更换基础镜像。
# 版本组合说明（重要，勿随意改动）：
#  - 云托管 MySQL 为 5.7，Django 4.2+ 要求 MySQL 8.0+（启动即报 NotSupportedError），
#    故必须使用最后一个支持 MySQL 5.7 的 Django 4.1.x。
#  - Django 4.1 最高支持 Python 3.11，故基础镜像用 alpine 3.19（自带 Python 3.11）。
#  - Python 3.9+ 自带 zoneinfo 标准库，不需要 backports.zoneinfo（该包在 alpine
#    无 gcc 环境下无法编译），也不会触发 PEP 668 之外的额外问题。
FROM alpine:3.19

# 容器默认时区为UTC，如需使用上海时间请启用以下时区设置命令
# RUN apk add tzdata && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo Asia/Shanghai > /etc/timezone

# 使用 HTTPS 协议访问容器云调用证书安装
RUN apk add ca-certificates

# 选用国内镜像源以提高下载速度
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tencent.com/g' /etc/apk/repositories \
&& apk add --update --no-cache python3 py3-pip \
&& rm -rf /var/cache/apk/*

# 拷贝当前项目到/app目录下(.dockerignore中文件除外)
COPY . /app

# 设定当前的工作目录
WORKDIR /app

# 启动入口脚本可执行
RUN chmod +x /app/entrypoint.sh

# 安装依赖到指定的/install文件夹
# 选用国内镜像源以提高下载速度
# alpine 3.19 的 Python 3.11 受 PEP 668 保护(externally-managed-environment),
# 容器是隔离环境,加 --break-system-packages 直接写入系统 site-packages。
RUN pip config set global.index-url http://mirrors.cloud.tencent.com/pypi/simple \
&& pip config set global.trusted-host mirrors.cloud.tencent.com \
&& pip install --break-system-packages --upgrade pip \
# pip install scipy 等数学包失败，可使用 apk add py3-scipy 进行， 参考安装 https://pkgs.alpinelinux.org/packages?name=py3-scipy&branch=v3.19
&& pip install --break-system-packages -r requirements.txt

# 暴露端口
# 此处端口必须与「服务设置」-「流水线」以及「手动上传代码包」部署时填写的端口一致，否则会部署失败。
EXPOSE 80

# 执行启动命令
# 写多行独立的CMD命令是错误写法！只有最后一行CMD命令会被执行，之前的都会被忽略，导致业务报错。
# 请参考[Docker官方文档之CMD命令](https://docs.docker.com/engine/reference/builder/#cmd)
# 使用 entrypoint.sh:先迁移数据库、空库时灌演示数据,再启动服务
CMD ["sh", "/app/entrypoint.sh"]
