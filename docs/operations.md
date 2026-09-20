# 个人健康记录运维手册

## 生产环境准备

准备 Python 3.13、PostgreSQL、Redis 和支持 HTTPS 的反向代理或托管平台。应用进程使用 `Procfile` 中的 Gunicorn 命令启动；反向代理必须传递 `X-Forwarded-Proto: https`。

设置以下环境变量，不要把真实值写入代码或提交到 Git：

```text
DJANGO_ENV=production
SECRET_KEY=<至少 50 位的随机字符串>
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
CACHE_URL=redis://<host>:6379/1
ALLOWED_HOSTS=health.example.com
CSRF_TRUSTED_ORIGINS=https://health.example.com
SECURE_HSTS_SECONDS=0
PORT=8000
```

首次上线时保持 `SECURE_HSTS_SECONDS=0`。确认域名全站 HTTPS、证书续期和所有子域均正常后，再逐步提高到 `3600`、`86400`，最终可设为 `31536000`。只有所有子域永久支持 HTTPS 时才启用 `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` 和 `SECURE_HSTS_PRELOAD=True`。

## 发布步骤

每次发布依次执行：

```bash
python manage.py check --deploy
python manage.py shell -c "from django.core.cache import cache; cache.set('deploy-check', 'ok', 10); assert cache.get('deploy-check') == 'ok'"
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

第二条命令会实际读写 Redis；失败时不得继续发布。限流器采用失败关闭策略，Redis 故障时登录和注册会停止服务，而不会绕过防暴力破解限制。恢复 Redis 后再恢复流量。

首次部署后创建管理员：

```bash
python manage.py createsuperuser
```

完成后启动或滚动重启 Web 进程，并检查 `/accounts/login/`、登录后的今日页和静态资源是否正常。Django 与 Gunicorn 每条日志均为单行 JSON；访问日志只记录来源地址、方法、路径（不含查询字符串）、协议、状态码、字节数和耗时。不要在日志中记录密码、Cookie、认证令牌或请求正文。

## 管理员重置用户密码

首版不提供短信找回。管理员在受控终端中执行：

```bash
python manage.py changepassword <手机号>
```

通过预先约定的安全渠道把临时密码交给用户，并要求用户登录后立即在“我的”页面修改密码。不要通过应用日志、工单正文或公开聊天发送密码。

## 数据库备份与恢复演练

至少每日用托管 PostgreSQL 快照或 `pg_dump` 备份，备份文件应加密、限制访问并设置保留周期。示例：

```bash
pg_dump --format=custom --no-owner "$DATABASE_URL" --file health-YYYYMMDD.dump
pg_restore --clean --if-exists --no-owner --dbname "$RESTORE_DATABASE_URL" health-YYYYMMDD.dump
```

每月至少在隔离数据库执行一次恢复演练，核对用户数和四类健康记录数量。恢复目标必须是专用测试库，禁止直接覆盖生产库。

## 密钥与凭据轮换

数据库、Redis 或平台凭据泄露时，先在服务端创建新凭据，更新环境变量并滚动重启，验证新连接后撤销旧凭据。轮换 `SECRET_KEY` 会使现有登录会话失效，应提前安排维护窗口并通知用户重新登录。

## 上线检查

- 两个测试账号无法查看、编辑或导出彼此的数据。
- 饮食、运动、体重、腰围均可创建、编辑和删除。
- 营养字段可留空，力量训练可保存多组明细。
- 7 天和 30 天趋势、草稿恢复和数据导出可用。
- 页面没有图片上传控件，也不需要对象存储凭据。
- 日志为单行 JSON，不包含查询字符串、请求正文、Cookie 或认证头。
