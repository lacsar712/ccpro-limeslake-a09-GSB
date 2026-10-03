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
| `worker2` | `123456` | 操作工（用于演示两人抢挂同一池） |

登录页已预填 `admin` / `123456`。启动时 entrypoint 会建表并写入种子数据（示范厂区：**东湾石灰厂**）。

## 主界面

- **熟化池平面图**（`/board/`）：CSS 网格池位瓦片，按状态着色（注水中 / 熟化中 / 已出灰），瓦片显示挂牌人缩写（无牌显示「无牌」）
- 顶部厂区切换芯片（多厂时切换）
- 点击瓦片 → 右侧抽屉展示当班码牌与最近 `SlakeBatch`，持牌人可登记峰值温度并变更池状态
- **码牌台**（`/tags/`）：现行挂牌列表、挂牌、摘牌
- 主导航不再挂「熟化池列表 / 批次列表」；旧 `/ponds/`、`/batches/` 路由仍保留但不作为作业入口（同样受码牌核对约束）

## 业务规则

### 当班码牌

每口**熟化中或注水中**的池须挂一张当班码牌（`ShiftTag`：熟化池、挂牌人、挂牌时刻、摘牌时刻可空）。

- 同一池未摘牌最多一张 —— 由 PostgreSQL 部分唯一索引 `uq_shift_tag_active_per_pond`（`WHERE removed_at IS NULL`）在数据库层兜底，两名操作工并发抢挂只落一张。
- 操作工只能给自己挂牌（服务端忽略表单里的 `holder_id`）；管理员可代挂、可摘任何人的牌；摘牌可由挂牌人本人或管理员。
- 已出灰池**旧牌未摘时**禁止新挂；旧牌摘除后可重新挂牌，开启下一熟化周期。
- **改池态与登记批次的统一入口核对**：该池须有未摘牌，且当前登录用户是挂牌人本人或管理员，否则中文拒绝。出灰峰值门槛（最近批次峰值 ≥ 60℃）照旧，并与码牌核对收进同一作业入口（`board.pond_ops`）。

入口：顶栏「平面图」「码牌台」（`/tags/`，含现行挂牌列表、挂牌、摘牌）。瓦片右上角显示挂牌人缩写；无牌显示「无牌」。种子里 P-01 是一口熟化中无牌的池。

### 出灰峰值门槛

熟化池状态不可设为「已出灰」（`drawn`），除非该池**最近一条** `SlakeBatch` 的 `peakTempC` 已记录且 **≥ 60℃**。

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
│   └── blueprints/{auth,board,ponds,batches}
├── templates/
│   └── board/floor.html     # 平面图 + 抽屉
└── static/
```
