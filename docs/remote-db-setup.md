# 远程 PostgreSQL 部署检查清单

本文档汇总了在 Open WebUI 部署中使用远程 PostgreSQL 数据库时的关键步骤，并确保 OAuth 会话加密机制能够正常工作。

## 1. 准备 OAuth 会话加密密钥

1. 生成高熵密钥（建议至少 32 字节随机数，再进行 Base64 编码）。如果直接提供 44 个字符的 Fernet Base64 字符串，程序会原样使用；若提供其他长度的值，应用会先对其执行 SHA-256 再派生合规密钥，因此无论哪种方式都应保证原始密钥足够安全。
2. 将密钥写入运行环境中的 `OAUTH_SESSION_TOKEN_ENCRYPTION_KEY` 变量，可放在 `.env` 文件、Systemd 的 `Environment=` 或 Docker Compose 的 `environment:` 中。该变量缺失时，OAuth 会话管理器会拒绝启动，因为所有 token 都需要静态加密。

## 2. 配置远程 PostgreSQL 连接

在启动后台服务之前，需要设置完整的 SQLAlchemy 连接串或拆分后的组件变量。

### 方案 A：单个连接 URL
```bash
export DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@222.197.201.55:5432/open-web"
```
- 如果密码包含保留字符，务必先做 URL 编码。
- 当提供 `postgres://` 前缀时，程序会自动改写为 SQLAlchemy 兼容的 `postgresql://`。

### 方案 B：逐项组件变量
```bash
export DATABASE_TYPE="postgresql+psycopg2"
export DATABASE_HOST="222.197.201.55"
export DATABASE_PORT="5432"
export DATABASE_NAME="open-web"
export DATABASE_USER="open_webui"
export DATABASE_PASSWORD="URL-ENCODED-PASSWORD"
```
- 启动时 `env.py` 会把上述变量拼成 `DATABASE_URL`，并依次运行 Peewee 与 Alembic 迁移以初始化远端数据库结构。
- 请确保密码经过 URL 编码，否则连接会失败并在日志中提示。

> **提示：** 如果使用 Systemd，可将这些键值写入 `/etc/systemd/system/open-webui.service.d/override.conf` 的 `Environment=` 中；Docker Compose 则放在服务的 `environment:` 字段。无论哪种方式，都要在服务启动前重新加载配置，使变量对进程可见。

## 3. 验证配置

1. 重启后端服务（或让进程管理器重新加载），观察日志中是否出现数据库连接成功与 OAuth 会话初始化成功的提示。
2. 在容器或宿主机内运行以下 Python 脚本确认环境变量是否生效：
   ```bash
   python - <<'PY'
   import os
   for key in (
       "OAUTH_SESSION_TOKEN_ENCRYPTION_KEY",
       "DATABASE_URL",
       "DATABASE_TYPE",
       "DATABASE_HOST",
       "DATABASE_PORT",
       "DATABASE_NAME",
       "DATABASE_USER",
   ):
       print(f"{key}={os.environ.get(key, '<missing>')}")
   PY
   ```
3. 测试一次 OAuth 登录。远程 PostgreSQL 的 `oauth_session` 表应写入加密后的 token，表示加密密钥与数据库配置均已生效。

## 4. 处理数据库迁移冲突

如果你已经在远端 PostgreSQL 手工建表，启动时 Peewee 迁移可能会因为“列已存在”等错误终止。出现这种情况时，可以按需选择以下两种处理方式：

### 方式 A：让数据库回到迁移预期的空结构

1. **测试环境/无数据时**：直接清空或删除 `auth`、`"user"`、`oauth_session`、`config` 等表，然后重新启动服务，让 Peewee 与 Alembic 自动创建全部结构。
2. **需要保留数据时**：手动删除报错中提到的列（例如 `ALTER TABLE "user" DROP COLUMN api_key;`），再重新启动服务，让迁移脚本重新补齐该列。

### 方式 B：告知 Peewee 对应迁移已经执行

1. 保留手工创建的列，并在远端数据库中插入一条迁移记录，例如：
   ```sql
   INSERT INTO peewee_migrate (name) VALUES ('003_add_auth_api_key');
   ```
   如果还有其他已手工完成的迁移，也按需补齐对应的名称。
2. 重新启动服务。Peewee 会跳过这些已登记的迁移，继续执行剩余未完成的脚本。

> **最佳实践：** 远端数据库初始化时，仅创建空库与账号，把表结构的创建和演进交给项目自带的迁移体系处理，可以避免重复 DDL，也能确保后续新增字段和索引自动同步。
