# MemeClaw — 网络梗智能检索与分析系统

基于多智能体（Multi-Agent）+ LLM 的中文互联网迷因研究工具。自动搜索梗的来源、寻找代表视频、生成深度文化分析报告，并每日监控各平台新梗动态。

## 功能

- **梗百科** — 搜索梗的定义、别名、起源平台、关键时间线
- **视频猎人** — 跨平台（B站、抖音、YouTube）寻找最具代表性的视频
- **文化人类学家** — 基于模因学理论生成深度分析报告（溯源、变异分析、社会心理映射、生命周期预测）
- **梗情报局** — 每日定时扫描抖音/B站/微博/小红书，LLM 判定新热梗并推送简报
- **HTTP API** — FastAPI 服务，支持搜索、分析、订阅、流式推送接口
- **定时调度** — 内置 cron 定时任务，每日自动运行热梗扫描

## 架构

```
[ 用户交互 ]  CLI / HTTP API
      ↓
[ 主控 Workflow ]  LangGraph 编排，意图识别 → 任务分发
      ↓
[ 专项 Agent 集群 ]
├── 梗百科 Agent      搜索 + LLM 结构化提取
├── 视频猎人 Agent    多平台视频检索
├── 文化人类学家 Agent RAG 增强的学术报告生成
└── 梗情报局 Agent    每日热梗扫描 + LLM 判定
      ↓
[ 工具层 ]  搜索引擎 (DuckDuckGo/SerpAPI) | 视频平台 API | LLM (OpenAI 兼容)
      ↓
[ 存储层 ]  MongoDB | 本地文件导出 (Markdown / Excel)
```

## 快速开始

### 环境要求

- Python 3.10+
- MongoDB（可选，订阅和缓存功能需要）

### 安装

```bash
git clone https://github.com/YOUR_USER/memeclaw.git
cd memeclaw
pip install -r memeclaw/requirements.txt
```

### 配置

通过环境变量配置：

| 变量 | 说明 | 默认值 |
|:---|:---|:---|
| `OPENAI_API_KEY` | LLM API Key | `sk-xxx` |
| `OPENAI_BASE_URL` | LLM API 地址 | `https://api.deepseek.com` |
| `MEMECLAW_LLM_MODEL` | 主模型 | `deepseek-v4-pro` |
| `MEMECLAW_LONG_CTX_MODEL` | 长文本模型（分析报告用） | `deepseek-v4-pro` |
| `SEARCH_API` | 搜索引擎 (`duckduckgo` / `serpapi`) | `serpapi` |
| `SERPAPI_KEY` | SerpAPI Key（使用 serpapi 时必填） | — |
| `MONGO_URI` | MongoDB 连接地址 | `mongodb://localhost:27017` |
| `MEMECLAW_EXPORT_DIR` | 报告导出目录 | `./data/reports` |

LLM 后端使用 OpenAI 兼容接口，支持 DeepSeek、OpenAI、或其他兼容服务。

### CLI 使用

```bash
# 搜索梗的基本信息和视频
python -m memeclaw.main search "这很开门"

# 生成深度文化分析报告
python -m memeclaw.main analyze "这很开门"

# 订阅每日新梗推送
python -m memeclaw.main subscribe

# 手动触发每日热梗扫描
python -m memeclaw.main daily

# 启动 HTTP API 服务
python -m memeclaw.main serve

# 启动每日情报局定时任务
python -m memeclaw.main cron

# 查看系统配置
python -m memeclaw.main info
```

### API 接口

启动服务后访问 `http://localhost:8000`：

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/search?q=梗名` | GET | 搜索梗，返回百科信息 + 视频 |
| `/analyze?q=梗名` | GET | 生成深度文化分析报告 |
| `/subscribe` | POST | 订阅每日新梗推送 |
| `/daily-briefing` | GET | 触发每日热梗扫描（返回 JSON） |
| `/daily-briefing/stream` | GET | 流式热梗扫描（NDJSON，实时进度） |
| `/health` | GET | 健康检查 |

## 项目结构

```
memeclaw/
├── main.py              # CLI 入口
├── api.py               # FastAPI HTTP 服务
├── config.py            # 全局配置（环境变量 + dataclass）
├── agents/
│   ├── encyclopedia.py  # 梗百科 Agent — 搜索 + LLM 结构化提取
│   ├── video_hunter.py  # 视频猎人 Agent — 多平台视频检索
│   ├── anthropologist.py # 文化人类学家 Agent — RAG 深度分析报告
│   └── intelligence.py  # 梗情报局 Agent — 每日热梗扫描 + LLM 判定
├── workflows/
│   └── master.py        # LangGraph 主控工作流
├── models/
│   └── schemas.py       # Pydantic 数据模型
├── tools/
│   ├── search.py        # 搜索工具（DuckDuckGo / SerpAPI / 多平台）
│   ├── video_search.py  # 视频搜索（B站/抖音/YouTube）
│   └── json_repair.py   # JSON 修复 Agent（LLM 输出容错）
├── storage/
│   └── database.py      # MongoDB 异步存储层
└── static/
    └── index.html       # Web 前端页面
```

## 依赖

主要依赖见 [memeclaw/requirements.txt](memeclaw/requirements.txt)：

- **langgraph** — Agent 工作流编排
- **openai** — LLM 调用（OpenAI 兼容接口）
- **fastapi + uvicorn** — HTTP API 服务
- **pydantic** — 数据模型
- **duckduckgo_search** — 免 API Key 搜索引擎
- **aiohttp** — 异步 HTTP 客户端
- **motor** — MongoDB 异步驱动
- **apscheduler** — 定时任务调度
- **json-repair** — LLM JSON 输出修复

## License

MIT
