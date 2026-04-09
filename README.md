# Japan News ETL

[English](#english) | [日本語](#日本語) | [中文](#中文)

---

## English

### Overview

`japan-news-etl` is an end-to-end news data pipeline:

- Python ETL ingests RSS feeds and performs normalization, deduplication, classification, and summarization
- Airflow orchestrates scheduled runs
- PostgreSQL stores article data and ETL run logs
- Redis caches query results
- Spring Boot API serves multilingual natural-language queries

### Architecture

```text
RSS Sources -> [Python ETL] -> PostgreSQL <- [Spring Boot API] <- User Query
                   |                              |
                   v                              v
                Airflow                        Redis Cache
```

### Main Entry Points

- Airflow DAG: `dags/news_etl_dag.py`
- API app: `api/src/main/java/com/japannews/JapanNewsApiApplication.java`
- CLI demo: `demo.py`
- E2E smoke: `scripts/e2e_smoke.py`

### Quick Start

```bash
git clone <your-repo-url>
cd japan-news-etl
cp .env.example .env
docker compose up --build -d
```

### Recommended LLM Settings (Kimi)

```env
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_INTENT_MODEL=kimi-k2-0905-preview
LLM_ANSWER_MODEL=kimi-k2-0905-preview
LLM_CLASSIFIER_MODEL=kimi-k2-0905-preview
```

Notes:
- Spring Boot does not automatically load `.env.local`. Set environment variables in the terminal before `bootRun`, or define them in system env.
- API default port: `8081`
- Airflow UI default port: `8090`

### Run Demo

```bash
uv sync
uv run python demo.py
```

Commands:
- Ask directly (sent to `http://localhost:8081/api/query`)
- `run` (manual ETL)
- `stats` (today's ETL summary)
- `exit`

### Tests and Verification

```bash
uv run pytest etl/tests/test_transform.py
gradle -p api test
uv run python scripts/test_idempotency.py
uv run python scripts/e2e_smoke.py
uv run python scripts/check_llm_config.py
```

### Data Model

- `news_articles`: structured news records
- `etl_run_log`: ETL run-level metrics and status
- Categories: `immigration`, `ai_tech`, `language_learning`

---

## 日本語

### 概要

`japan-news-etl` は、日本ニュース向けのエンドツーエンド ETL プロジェクトです。

- Python ETL が RSS を収集し、正規化・重複排除・分類・要約を実行
- Airflow が定期実行をオーケストレーション
- PostgreSQL に記事データと実行ログを保存
- Redis で問い合わせ結果をキャッシュ
- Spring Boot API で自然言語クエリに回答

### アーキテクチャ

```text
RSS Sources -> [Python ETL] -> PostgreSQL <- [Spring Boot API] <- User Query
                   |                              |
                   v                              v
                Airflow                        Redis Cache
```

### 主なエントリポイント

- Airflow DAG: `dags/news_etl_dag.py`
- API エントリ: `api/src/main/java/com/japannews/JapanNewsApiApplication.java`
- CLI デモ: `demo.py`
- E2E スモーク: `scripts/e2e_smoke.py`

### クイックスタート

```bash
git clone <your-repo-url>
cd japan-news-etl
cp .env.example .env
docker compose up --build -d
```

### 推奨 LLM 設定（Kimi）

```env
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_INTENT_MODEL=kimi-k2-0905-preview
LLM_ANSWER_MODEL=kimi-k2-0905-preview
LLM_CLASSIFIER_MODEL=kimi-k2-0905-preview
```

注意:
- Spring Boot API は `.env.local` を自動読込しません。`bootRun` 前に環境変数を設定してください。
- API デフォルトポート: `8081`
- Airflow UI デフォルトポート: `8090`

### デモ実行

```bash
uv sync
uv run python demo.py
```

コマンド:
- 直接質問入力（`http://localhost:8081/api/query` へ送信）
- `run`（ETL 手動実行）
- `stats`（当日の実行統計）
- `exit`

### テスト・検証

```bash
uv run pytest etl/tests/test_transform.py
gradle -p api test
uv run python scripts/test_idempotency.py
uv run python scripts/e2e_smoke.py
uv run python scripts/check_llm_config.py
```

### データモデル

- `news_articles`: ニュース本体データ
- `etl_run_log`: ETL 実行ログ
- カテゴリ: `immigration` / `ai_tech` / `language_learning`

---

## 中文

### 项目简介

`japan-news-etl` 是一个端到端日本新闻数据工程项目：

- Python ETL 从多源 RSS 抓取新闻，做标准化、去重、分类与摘要
- Airflow 负责调度任务（按东京时区）
- PostgreSQL 存储结构化新闻与运行日志
- Redis 缓存查询结果
- Spring Boot API 提供自然语言问答（中/英/日）

### 架构

```text
RSS Sources -> [Python ETL] -> PostgreSQL <- [Spring Boot API] <- User Query
                   |                              |
                   v                              v
                Airflow                        Redis Cache
```

### 目录结构

```text
japan-news-etl/
├── api/                  # Spring Boot API
├── dags/                 # Airflow DAG
├── etl/                  # Python ETL modules
├── scripts/              # Validation / smoke scripts
├── sql/                  # DB init SQL
├── demo.py               # CLI demo
├── docker-compose.yml
└── README.md
```

### 核心流程

1. `etl/fetch.py`：从 RSS 抓取新闻条目  
2. `etl/transform.py`：字段标准化、去重、LLM 分类和摘要  
3. `etl/load.py`：写入 `news_articles`，并记录 `etl_run_log`  
4. `etl/validate.py`：执行日数据质量检查  
5. `api/`：解析查询意图、检索新闻、生成回答

### 主要入口

- Airflow DAG：`dags/news_etl_dag.py`
- API 服务入口：`api/src/main/java/com/japannews/JapanNewsApiApplication.java`
- 本地 CLI 演示：`demo.py`
- 端到端冒烟：`scripts/e2e_smoke.py`

### 快速开始

```bash
git clone <your-repo-url>
cd japan-news-etl
cp .env.example .env
docker compose up --build -d
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

### 推荐 LLM 配置（Kimi）

在 `.env` 或运行环境中设置：

```env
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_INTENT_MODEL=kimi-k2-0905-preview
LLM_ANSWER_MODEL=kimi-k2-0905-preview
LLM_CLASSIFIER_MODEL=kimi-k2-0905-preview
```

说明：
- Spring Boot API 不会自动读取 `.env.local`，请在启动 API 的终端中显式设置环境变量，或写入系统环境变量。
- API 默认端口：`8081`
- Airflow UI 默认端口：`8090`

### Demo 使用

```bash
uv sync
uv run python demo.py
```

可用命令：
- 直接输入问题：调用 `http://localhost:8081/api/query`
- `run`：手动跑一轮 ETL
- `stats`：查看当日运行统计
- `exit`：退出

### 验证与测试

```bash
uv run pytest etl/tests/test_transform.py
gradle -p api test
uv run python scripts/test_idempotency.py
uv run python scripts/e2e_smoke.py
uv run python scripts/check_llm_config.py
```

### 数据模型

- `news_articles`：新闻主表（包含分类、摘要、时间、来源）
- `etl_run_log`：每日运行日志
- 分类集合：`immigration` / `ai_tech` / `language_learning`
