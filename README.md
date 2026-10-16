# 四合一 AI 融合工作台（Fusion Workbench）

> 把 4 个独立 AI 项目融合进同一个单端口工作台：**RAG 智能智库 · AI 合同审批 · 电商小二智能客服 · AI 电商运营助手**。
> 一个 FastAPI 进程、一个 SQLite 数据库、一个 SPA 前端，36 个 API 开箱即用。

**在线演示**：https://fusion-workbench-confirm.app.workbuddy.host/

---

## 项目亮点

- **单端口聚合架构**：四个模块路由统一挂载（`/api/kb`、`/api/contract`、`/api/cs`、`/api/ops`），共享 SQLite 存储层（9 张表 + FTS5 全文索引 + WAL）
- **LLM 双链路降级**：配置 SiliconFlow（OpenAI 兼容）即开启真实 AI 能力；未配置 Key 时全系统自动降级为「规则 / 演示模式」，功能不残缺
- **客服三轨对话引擎**：TurnPlanner（LLM 意图路由）→ TurnPlanValidator（白名单校验防幻觉）→ task / knowledge / chitchat 三轨分发，`flows.yml` 配置驱动
- **合同数据驱动规则引擎**：keyword / regex / absence / custom 四种审查模式，11 条默认规则 + 5 个自定义 detector，LLM 可选语义增强
- **FTS5 中文 bigram 检索**：解决 SQLite `unicode61` 分词器不切分连续中文的问题（索引与查询双侧二元展开 + LIKE 降级兜底）
- **零构建前端**：原生 HTML/CSS/JS 单页应用（hash 路由 + 侧边栏导航），无 Node 依赖，`python main.py` 一键启动

## 功能模块

| 模块 | 路由前缀 | 核心功能 |
|---|---|---|
| RAG 智能智库 | `/api/kb` | 文档上传 / 文本入库、分块索引、FTS5 检索、带引用问答、历史记录 |
| AI 合同审批 | `/api/contract` | 合同上传、规则审查、LLM 语义研判、审批决定（approve / reject / rectify）、回写评论、Markdown 导出、审计日志 |
| 电商小二·智能客服 | `/api/cs` | 6 个对话 flow（ onboarding / 订单查询 / 物流跟踪 / 退款申请 / 相似推荐 / 人工客服）、LLM 意图路由、三轨分发、SQLite 会话状态持久化、演示订单数据 |
| AI 电商运营助手 | `/api/ops` | 商品 / 店铺 CRUD、经营看板统计、4 个预置 Agent 分步执行、工作流开关 |
| 工作台前端 | `/` | 侧边栏导航 SPA：总览 / 智库 / 合同 / 小二 / 运营五个视图 |

## 技术栈

Python 3.11+ · FastAPI · SQLite（WAL + FTS5）· httpx（OpenAI 兼容 LLM 客户端）· PyYAML（flows 配置驱动）· 原生 HTML / CSS / JavaScript

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 LLM（可选；不配置则进入规则 / 演示模式）
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

# 3. 启动
python main.py
# 或：uvicorn main:app --host 0.0.0.0 --port 8020

# 4. 浏览器打开 http://localhost:8020
```

## 环境变量

见 [`.env.example`](./.env.example)（`.env` 已在 `.gitignore` 中，不会提交，可安全存放 Key）：

| 变量 | 说明 |
|---|---|
| `LLM_API_KEY` | LLM 接口 Key；留空则 `DEMO_MODE=true`，全系统走规则 / 演示兜底 |
| `LLM_BASE_URL` | OpenAI 兼容端点，默认 `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | 模型名，默认 `deepseek-ai/DeepSeek-V3` |
| `APP_PORT` | 服务端口，默认 `8020`（云端沙箱读 `PORT`） |

## API 一览（36 个）

**RAG 智库 `/api/kb`**（6）：`GET /documents`、`POST /documents/text`、`POST /documents/upload`、`DELETE /documents/{id}`、`GET /ask`、`GET /history`

**合同审批 `/api/contract`**（8）：`GET /rules`、`GET /contracts`、`POST /contracts`、`GET /contracts/{id}`、`POST /contracts/{id}/decide`、`GET /contracts/{id}/writeback`、`GET /contracts/{id}/export`、`GET /audit`

**电商小二 `/api/cs`**（6）：`GET /flows`、`GET /intents`、`POST /chat`、`GET /history`、`POST /reset`、`GET /onboarding`

**电商运营 `/api/ops`**（14）：`GET /dashboard`、`GET/POST /products`、`PUT/DELETE /products/{id}`、`GET/POST /stores`、`PUT/DELETE /stores/{id}`、`GET /agents`、`POST /agents/run`、`GET /agents/runs`、`GET/POST /workflows`、`POST /workflows/{id}/toggle`、`DELETE /workflows/{id}`

**根路径**（2）：`GET /health`、`GET /`（SPA 首页）

## 目录结构

```
fusion-workbench/
├── main.py               # FastAPI 入口：健康检查 + 四模块路由挂载 + 静态资源
├── config.py             # 全局配置：LLM 环境变量 + .env 加载 + 演示模式开关
├── core/
│   ├── db.py             # SQLite 存储层：9 张表 + FTS5 中文 bigram 索引 + seed 演示数据
│   └── llm.py            # OpenAI 兼容 LLM 客户端：chat / chat_json / parse_json
├── modules/
│   ├── kb/               # RAG 智库：rag.py（分块 / 索引 / 检索 / 问答）+ router.py
│   ├── contract/         # 合同审批：rules.py（11 条规则 + 5 个 detector）+ review.py + router.py
│   ├── cs/               # 电商小二：flows.yml（6 个 flow）+ engine.py（三轨引擎）+ intents.py + router.py
│   └── ops/              # 电商运营：store.py（CRUD + 看板）+ agent.py（4 个 Agent）+ router.py
├── static/               # SPA 前端（原生 HTML/CSS/JS）
│   ├── index.html
│   └── assets/{app.css, app.js}
├── requirements.txt
└── .env.example          # 环境变量模板
```

## 说明

- 演示数据：数据库首次启动自动 seed（商品、店铺、合同、FAQ、演示订单）
- 无 Key 演示模式：合同走规则引擎、客服走关键词路由、智库走 FAQ 兜底，全部功能可交互
- 云端部署：启动命令 `python main.py`，端口固定 `3000`（`.env` 随目录上传生效）
