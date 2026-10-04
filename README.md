# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。

规则实现：`backend/core/rules.py`

### 铅封锁（RackLock）

- 新布卷入晾晒架前，须先在对应帆布间落一条**未作废**铅封号；没有可用锁不得新建布卷（中文拦截）。
- 锁字段：帆布间、铅封号、落锁时刻、落锁人、作废时刻（可空）。铅封号非空；**同间未作废铅封号唯一**（数据库部分唯一约束兜底并发）。
- 操作工可落锁；**作废仅管理员**；作废后该号可再发。
- 建卷成功与绑锁在**同一事务**完成；改已有卷的克重/备注不要求新锁。
- 种子数据：一间帆布间、零锁。

API：`GET/POST /api/locks/`（`state=active|voided`、`available=1`、`loftId` 筛选）、`POST /api/locks/{id}/void/`。

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`、切换固化状态；架下为浸渍流水次要信息流
- **`/locks` 铅封锁**：筛未作废/已作废、落锁、（管理员）作废
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径；新建布卷前读取将绑定的未作废锁，无锁中文拦截

API 契约不变（JWT、`/api/lofts|rolls|dips|locks|dashboard/`）。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
