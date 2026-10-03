# LimeSlake-01 · 石灰熟化池作业板

厂区熟化池平面图作业基线（Flask + Jinja + Stimulus）。主界面是按厂区排布的池位瓦片，点选后在右侧抽屉登记峰值温度并改状态——不是侧栏双列表 CRUD。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Web | Flask 3 · Blueprints · Flask-Login · Jinja2 · Stimulus CDN |
| 数据 | SQLAlchemy · PostgreSQL 15 |
| 部署 | Docker Compose · Gunicorn |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\LimeSlake\LimeSlake-01`
- **Web**：http://localhost:4730
- **PostgreSQL**：localhost:6130

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `worker` | `123456` | 操作工 |
| `worker2` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。启动时 entrypoint 会建表并写入种子数据（示范厂区：**东湾石灰厂**）。

## 主界面

- **熟化池平面图**（`/board/`）：CSS 网格池位瓦片，按状态着色（注水中 / 熟化中 / 已出灰）；已挂牌的池在瓦片右上角显示挂牌人缩写
- **码牌台**（`/badges/`）：现行挂牌列表、挂牌、摘牌
- 顶部厂区切换芯片（多厂时切换）
- 点击瓦片 → 右侧抽屉展示当班码牌与最近 `SlakeBatch`，可登记峰值温度并变更池状态
- 主导航不再挂「熟化池列表 / 批次列表」；旧 `/ponds/`、`/batches/` 路由仍保留但不作为作业入口

## 业务规则

### 当班码牌（ShiftBadge）

- 每口「熟化中 / 注水中」的池须挂一张当班码牌；牌字段：熟化池、挂牌人、挂牌时刻、摘牌时刻（可空）
- 同一池未摘牌最多一张（数据库部分唯一索引兜底，两人同挂一池只落一张）
- 操作工只能给自己挂牌；管理员可代挂；摘牌可由本人或管理员
- 已出灰池禁止新挂；同池已有未摘牌须先摘旧牌
- **改池态 / 登记批次**统一入口校验：该池须有未摘牌，且当前用户是挂牌人或管理员，否则中文拒绝
- 种子数据特意留一口「熟化中」池（P-04）无牌，用于演示无牌拒绝

### 出灰峰值门槛

熟化池状态不可设为「已出灰」（`drawn`），除非该池**最近一条** `SlakeBatch` 的 `peakTempC` 已记录且 **≥ 60℃**。该门槛与码牌核对收在同一入口 `assert_can_set_pond_status`。

规则实现：`app/services/rules.py`

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\LimeSlake\LimeSlake-01
docker compose up --build
```

浏览器打开 http://localhost:4730

停止：

```bash
docker compose down
```

## 目录结构

```
LimeSlake-01/
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── wsgi.py
├── app/
│   ├── __init__.py          # 工厂 + seed
│   ├── models.py
│   ├── services/rules.py
│   └── blueprints/{auth,board,badges,ponds,batches}
├── templates/
│   ├── board/floor.html     # 平面图 + 抽屉
│   └── badges/list.html     # 码牌台
└── static/
```
