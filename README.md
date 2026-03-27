# Japan News ETL

日本新闻 ETL 项目骨架，用于每天抓取与日本相关的新闻，按 `移民/外国人政策`、`AI/Tech`、`语言学习` 三类做清洗和入库，并为后续自然语言查询与向量检索打基础。

## 项目结构

```text
japan-news-etl/
├── docker-compose.yml
├── Dockerfile.airflow
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── dags/
│   └── news_etl_dag.py
├── etl/
│   ├── fetch.py
│   ├── transform.py
│   ├── load.py
│   └── validate.py
├── api/
├── logs/
├── plugins/
├── sql/
│   └── init.sql
└── README.md
```

## 开发方式

这个项目现在默认走 `docker compose` 开发：

- `postgres`: PostgreSQL 14 + pgvector
- `redis`: Redis 7
- `airflow-webserver`: Airflow UI
- `airflow-scheduler`: 定时调度
- `airflow-init`: 初始化数据库和管理员用户
- `airflow-cli`: 临时调试容器，用于执行 `airflow dags list`、手动触发 DAG、进入 shell

Python 依赖现在以 [pyproject.toml](/D:/news-agg/japan-news-etl/pyproject.toml) 和 [uv.lock](/D:/news-agg/japan-news-etl/uv.lock) 为主。 [requirements.txt](/D:/news-agg/japan-news-etl/requirements.txt) 由 `uv export` 生成，用于兼容 Docker 镜像构建。

## 本地 Python 开发

首次同步环境：

```bash
uv sync
```

查看依赖树：

```bash
uv tree
```

在项目环境中执行命令：

```bash
uv run python --version
uv run python -c "import airflow; print(airflow.__version__)"
```

如果只想直接使用项目虚拟环境，也可以：

```powershell
.\.venv\Scripts\Activate.ps1
python --version
```

## 快速开始

1. 复制环境变量模板

```bash
cp .env.example .env
```

2. 填写 `.env` 中的数据库、Airflow、OpenAI 配置

3. 同步本地 Python 依赖

```bash
uv sync
```

4. 构建并启动服务

```bash
docker compose up --build -d
```

5. 打开 Airflow UI

- URL: `http://localhost:8080`
- 用户名/密码：参考 `.env` 中的 `AIRFLOW_ADMIN_*`

## 常用开发命令

查看服务状态：

```bash
docker compose ps
```

查看 Airflow Scheduler 日志：

```bash
docker compose logs -f airflow-scheduler
```

列出 DAG：

```bash
docker compose run --rm airflow-cli airflow dags list
```

手动触发 DAG：

```bash
docker compose run --rm airflow-cli airflow dags trigger japan_news_daily_etl
```

进入 Airflow 容器调试：

```bash
docker compose run --rm airflow-cli bash
```

停止服务：

```bash
docker compose down
```

如果需要连同数据库卷一起清理：

```bash
docker compose down -v
```

## 依赖管理约定

- 本地开发以 `uv` 为准：修改依赖后执行 `uv lock`
- Docker 构建继续消费 [requirements.txt](/D:/news-agg/japan-news-etl/requirements.txt)
- 每次更新依赖后，执行：

```bash
uv export --format requirements-txt -o requirements.txt
```

## 代码热更新

以下目录都已挂载到容器中，修改后无需重建镜像即可生效：

- `dags/`
- `etl/`
- `sql/`
- `plugins/`
- `logs/`

只有在修改 [pyproject.toml](/D:/news-agg/japan-news-etl/pyproject.toml)、[uv.lock](/D:/news-agg/japan-news-etl/uv.lock)、[requirements.txt](/D:/news-agg/japan-news-etl/requirements.txt) 或 [Dockerfile.airflow](/D:/news-agg/japan-news-etl/Dockerfile.airflow) 时，才需要重新执行：

```bash
docker compose up --build -d
```

## ETL 流程

1. `fetch.py`
   从 RSS 源拉取原始新闻数据。

2. `transform.py`
   规范字段、生成 UUID 主键和 `url_hash`、做基础分类映射。

3. `validate.py`
   校验必填字段，过滤脏数据。

4. `load.py`
   写入 PostgreSQL、记录 `etl_run_log`，并把最近一次加载摘要写入 Redis。

## 数据模型

[init.sql](/D:/news-agg/japan-news-etl/sql/init.sql) 初始化 `news_articles` 表，包含：

- 结构化字段：标题、摘要、正文、分类、来源、时间
- `embedding VECTOR(1536)`：用于后续接 OpenAI embedding
- `llm_summary_ja` / `llm_summary_zh`：预留后续多语言摘要

## 下一步建议

- 在 `fetch.py` 中补充更多日本媒体 RSS/站点源。
- 在 `transform.py` 中接入更稳健的分类映射、发布时间解析和正文抽取。
- 在 `load.py` 中接入 OpenAI embedding，并把摘要结果写入 `llm_summary_ja` / `llm_summary_zh`。
- Day 2 再补 `api/` 的 Spring Boot REST API 和自然语言查询接口。
