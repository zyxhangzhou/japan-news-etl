# Japan News ETL

日本新闻 ETL 项目骨架，用于每天抓取与日本相关的新闻，按 `移民/外国人政策`、`AI/Tech`、`语言学习` 三类做清洗和入库，并为后续自然语言查询与向量检索打基础。

## 项目结构

```text
japan-news-etl/
├── docker-compose.yml
├── Dockerfile.airflow
├── .env.example
├── .gitignore
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

Airflow 镜像会通过 [Dockerfile.airflow](/D:/news-agg/japan-news-etl/Dockerfile.airflow) 本地构建，并在构建时安装 [requirements.txt](/D:/news-agg/japan-news-etl/requirements.txt) 中的依赖，不再每次容器启动时重复安装。

## 快速开始

1. 复制环境变量模板

```bash
cp .env.example .env
```

2. 填写 `.env` 中的数据库、Airflow、OpenAI 配置

3. 构建并启动服务

```bash
docker compose up --build -d
```

4. 打开 Airflow UI

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

## 代码热更新

以下目录都已挂载到容器中，修改后无需重建镜像即可生效：

- `dags/`
- `etl/`
- `sql/`
- `plugins/`
- `logs/`

只有在修改 [requirements.txt](/D:/news-agg/japan-news-etl/requirements.txt) 或 [Dockerfile.airflow](/D:/news-agg/japan-news-etl/Dockerfile.airflow) 时，才需要重新执行：

```bash
docker compose up --build -d
```

## ETL 流程

1. `fetch.py`
   从 RSS 源拉取原始新闻数据。

2. `transform.py`
   规范字段、生成 `article_id`、做基础分类映射。

3. `validate.py`
   校验必填字段，过滤脏数据。

4. `load.py`
   写入 PostgreSQL，并把最近一次加载摘要写入 Redis。

## 数据模型

[init.sql](/D:/news-agg/japan-news-etl/sql/init.sql) 初始化 `news_articles` 表，包含：

- 结构化字段：标题、摘要、正文、分类、来源、时间
- `embedding VECTOR(1536)`：用于后续接 OpenAI embedding
- `metadata JSONB`：预留原始抓取信息或额外标签

## 下一步建议

- 在 `fetch.py` 中补充更多日本媒体 RSS/站点源。
- 在 `transform.py` 中接入摘要抽取、去重和更稳健的分类逻辑。
- 在 `load.py` 中接入 OpenAI embedding 写入 `embedding` 字段。
- Day 2 再补 `api/` 的 Spring Boot REST API 和自然语言查询接口。
