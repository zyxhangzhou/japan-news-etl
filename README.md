# Japan News ETL

## Project Overview

一个自动抓取日本新闻的 ETL Pipeline，每日定时从 NHK World、Japan Times 等来源采集移民政策、AI/Tech、语言学习三类新闻。数据经过抓取、清洗、分类、去重和入库后，统一存入 PostgreSQL。最终通过 Spring Boot API 提供自然语言查询接口，支持中文、英文、日文提问。

## Architecture

```text
RSS Sources -> [Python ETL] -> PostgreSQL <- [Spring Boot API] <- User Query
                   |                              |
                   v                              v
                Airflow                        Redis Cache
                (调度)                         (1hr TTL)
```

## Tech Stack Choices

- Airflow DAG：任务依赖管理清晰，单个 Task 失败后可以独立重跑，不需要整条链路重复执行。
- PostgreSQL：既能承载结构化新闻数据，也能通过 pgvector 支持后续向量检索，减少系统拆分成本。
- Redis：缓存高频查询结果，避免对同一问题重复调用 LLM API，降低延迟和调用成本。
- 幂等性设计：基于 `url_hash` 做 upsert，保证 ETL 重跑时不会写入重复文章。

## Repository Layout

```text
japan-news-etl/
├── api/                  # Spring Boot query API
├── dags/                 # Airflow DAG definitions
├── etl/                  # Python ETL modules
├── scripts/              # Demo and validation scripts
├── sql/                  # PostgreSQL initialization
├── docker-compose.yml
├── Dockerfile.airflow
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── demo.py               # Interactive CLI demo
├── test.sh               # End-to-end test runner
└── README.md
```

## Pipeline Flow

1. `fetch.py`
   从 RSS 源抓取原始新闻条目。
2. `transform.py`
   统一字段结构，补齐 `id` / `url_hash`，做 LLM 分类和中文摘要。
3. `validate.py`
   执行每日数据质量检查，识别异常抓取量。
4. `load.py`
   将文章 upsert 到 PostgreSQL，并写入 `etl_run_log` 与 Redis 摘要缓存。
5. `api/`
   接收自然语言问题，解析意图、查询新闻、生成中文回答。

## Quick Start

```bash
git clone <your-repo-url>
cd japan-news-etl
cp .env.example .env
```

填写 `.env` 中的 `LLM_API_KEY`（或 `OPENAI_API_KEY`）、`DATABASE_URL`、Redis/Airflow 相关配置后，启动服务：

```bash
docker compose up --build -d
```

本地运行交互式演示：

```bash
uv sync
uv run python demo.py
```

Airflow UI 默认建议使用 http://localhost:8090，这样不会和 Spring Boot API 的 http://localhost:8081 冲突。

如果你在 Windows PowerShell 中复制环境文件，也可以使用：

```powershell
Copy-Item .env.example .env
```

## Demo Commands

启动 [demo.py](/D:/news-agg/japan-news-etl/demo.py) 后，支持以下交互：

- 直接输入问题：调用本地 Spring Boot API `localhost:8081/api/query`
- `stats`：查看今天的 ETL 运行统计
- `run`：直接调用 Python 函数手动执行一轮 ETL
- `exit`：退出演示工具

## Testing

Python 测试：

```bash
uv run pytest etl/tests/test_transform.py
```

Spring Boot 测试：

```bash
gradle -p api test
```

一键验证：

```bash
bash test.sh
```

幂等性演示脚本：

```bash
uv run python scripts/test_idempotency.py
```

最小端到端冒烟脚本（启动服务 -> 执行一轮 ETL -> 调用 API）：

```bash
uv run python scripts/e2e_smoke.py
```

## Data Model

核心表：

- `news_articles`：存储结构化新闻数据、LLM 摘要和后续向量检索字段
- `etl_run_log`：记录每日分来源、分分类的抓取/写入情况，用于质量监控与演示 upsert 行为

当前分类范围：

- `immigration`
- `ai_tech`
- `language_learning`

## Interview Notes

这个项目适合展示的不只是“抓到新闻”，而是完整的数据工程思路：定时编排、幂等写入、LLM 分类、缓存、自然语言查询和基础测试。除了常规单元测试，还提供了 [scripts/test_idempotency.py](/D:/news-agg/japan-news-etl/scripts/test_idempotency.py) 用于证明生产场景里的重复写入风险已经被显式考虑。对于面试演示，可以先运行 `demo.py` 展示问答，再运行幂等性脚本说明为什么 ETL 可以安全重跑。

## Design Decisions

### 中文版

1. 为什么用 5 个独立 Task 而不是一个大脚本
   我把抓取、转换、加载、校验、通知拆成独立 Task，是为了让失败定位更快、重跑粒度更细，也更符合后续扩展更多数据源和处理步骤的需求。

2. 为什么幂等性用 `url_hash` 而不是 `url` 本身
   我选择 `url_hash` 作为 upsert 键，是为了避免超长 URL、编码差异和索引成本问题，同时保留与原始 URL 解耦的稳定唯一键。

3. 为什么查询层不直接用 SQL 而要经过 LLM 意图解析
   我让用户问题先经过意图解析，是因为自然语言查询往往包含日期、类别、关键词等隐含条件，直接暴露 SQL 过滤逻辑既不友好，也不利于支持中英日三语输入。

### English Version

1. Why use five separate tasks instead of one large script
   I split fetch, transform, load, validate, and notify into separate tasks so failures are easier to isolate, reruns are more targeted, and the pipeline stays maintainable as new sources and steps are added.

2. Why use `url_hash` instead of the raw `url` for idempotency
   I chose `url_hash` as the upsert key to avoid issues with very long URLs, encoding inconsistencies, and index overhead, while keeping a stable deduplication key.

3. Why not query with SQL directly and instead use LLM-based intent parsing
   I added an intent parsing layer because natural-language queries usually hide filters such as date, category, and keywords, and translating those into structured query parameters creates a much better multilingual user experience than exposing raw SQL rules.