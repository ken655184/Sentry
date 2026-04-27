# Monitor System (Part 1 + 2 完整版)

PHP 測試監控系統重構為 Python 版本 — **Part 1 + Part 2 合併後的完整骨架**。

## 完成範圍

### Part 1(基礎層)
- ✅ 專案設定、核心工具(日誌、例外、回應格式)
- ✅ 認證模組完整版:User / Role / Permission / AuditLog、JWT、bcrypt、`require_permission()`、5 個角色 seed

### Part 2(非同步執行層)— 本次新增
- ✅ **Celery Workers**(`app/workers/`)
  - `celery_app.py`:App 設定、3 個 queue(default / heavy / audit)、生命週期 signal
  - `progress.py`:ProgressReporter + Redis Pub/Sub 廣播
  - `base.py`:AuditedTask — 自動帶稽核、ctx 注入、reporter
  - `jobs/business_jobs.py`:業務模組 dispatch(run_job / batch)
  - `jobs/resource_jobs.py`:檔案掃描 / metadata 讀取
  - `jobs/audit_jobs.py`:非同步稽核寫入 + 批次 flush
  - `jobs/system_jobs.py`:heartbeat / cleanup / ping
  - `celery_beat.py`:heartbeat(30s)+ 稽核清理(每日凌晨 3 點)
- ✅ **WebSocket**(`app/websocket/`)
  - `manager.py`:ConnectionManager — 多連線 / 多 room / permission 過濾
  - `pubsub_bridge.py`:Redis Pub/Sub → WS manager 橋接
  - `routes.py`:WS endpoint + JWT 驗證 + client op 協議
  - `metrics.py`:Prometheus 指標(連線數、task 計數)
- ✅ **Repository 層存根**
  - `app/repositories/db/business_registry.py`:業務 handler registry(留空介面)
  - `app/repositories/filesystem/loader.py`:檔案路徑掃描 / metadata 讀取
- ✅ **API**:`app/api/v1/tasks.py` — Task 觸發 / 狀態查詢 / 取消 / ping
- ✅ **Docker Compose** — api / worker-default / worker-heavy / worker-audit / beat / flower(可選)
- ✅ **Dockerfile**
- ✅ Tests:progress、ws manager、fs loader、ws routes 驗證

---

## 快速啟動

### 本機開發

```bash
# 1. 安裝依賴
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. 設定 env
cp .env.example .env
# 至少改 SECRET_KEY(≥32 字元)

# 3. 啟動 Redis
brew services start redis       # macOS
# 或
sudo systemctl start redis      # Linux

# 4. 四個 terminal 分別啟動
uvicorn app.main:app --reload --port 8000          # API
celery -A app.workers worker -Q default --loglevel=info   # worker(default)
celery -A app.workers worker -Q heavy,audit --loglevel=info  # worker(heavy+audit)
celery -A app.workers beat --loglevel=info                # beat(排程)
```

驗證:
- API docs: http://localhost:8000/docs
- 健康: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

### Docker Compose

```bash
cp .env.example .env
# 編輯 .env,設定 SECRET_KEY

docker compose up -d

# 包含 Flower 監控 UI (port 5555)
docker compose --profile monitoring up -d
```

---

## WebSocket 使用方式

**URL**: `ws://localhost:8000/ws?token=<access_token>`

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws?token=${accessToken}`);

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);

  if (msg.type === "welcome") {
    console.log("已連線", msg.username);
  }

  if (msg.type === "task_event") {
    const { task_id, event, payload } = msg;
    // event: started | progress | finished | failed | log
    if (event === "progress") {
      updateProgressBar(task_id, payload.percent);
    }
  }
};

// 訂閱某個 task 的進度
ws.send(JSON.stringify({ op: "subscribe", room: `task:${taskId}` }));

// 管理員訂閱全域 task 面板(需 audit:view 權限)
ws.send(JSON.stringify({ op: "subscribe", room: "admin:tasks" }));

// 定期心跳
setInterval(() => ws.send(JSON.stringify({ op: "ping" })), 30000);
```

---

## Celery Task 觸發

```bash
# 觸發業務 job
POST /api/v1/tasks/dispatch
{ "job_key": "example.echo", "params": {"msg": "hello"} }
# → { "task_id": "abc-...", "ws_room": "task:abc-..." }

# 查詢狀態
GET /api/v1/tasks/<task_id>/status

# 取消(只對還在 queue 的 task 有效)
POST /api/v1/tasks/<task_id>/cancel

# 確認 worker 活著
GET /api/v1/tasks/ping
```

---

## 接入你的業務模組

在你們的業務 Python 模組啟動時呼叫:

```python
from app.repositories.db.business_registry import register

def run_daily_report(*, params, reporter, ctx):
    reporter.log("開始產報表...")
    reporter.update(50, note="處理中")
    # ... 你的邏輯 ...
    return {"report_url": "..."}

register("report.daily", run_daily_report)
```

之後前端就可以觸發 `POST /api/v1/tasks/dispatch` with `job_key: "report.daily"`。

---

## 目錄結構

```
monitor/
├── app/
│   ├── main.py                       # FastAPI 進入點(含 bridge lifespan)
│   ├── config.py                     # 設定
│   ├── core/                         # 日誌、例外、安全、回應
│   ├── auth/                         # ★ 認證模組(完整)
│   ├── api/v1/
│   │   └── tasks.py                  # ★ Part 2: Task API
│   ├── repositories/
│   │   ├── db/business_registry.py   # ★ Part 2: 業務模組接口(留空)
│   │   └── filesystem/loader.py      # ★ Part 2: 檔案掃描接口
│   ├── workers/                      # ★ Part 2: Celery
│   │   ├── celery_app.py
│   │   ├── progress.py
│   │   ├── base.py
│   │   ├── celery_beat.py
│   │   └── jobs/
│   │       ├── business_jobs.py
│   │       ├── resource_jobs.py
│   │       ├── audit_jobs.py
│   │       └── system_jobs.py
│   └── websocket/                    # ★ Part 2: WebSocket
│       ├── routes.py                 # ws_router (main.py import 的)
│       ├── manager.py
│       ├── pubsub_bridge.py
│       └── metrics.py
├── tests/
│   ├── test_workers_progress.py
│   ├── test_ws_manager.py
│   ├── test_ws_routes.py
│   └── test_fs_loader.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## 預設 admin 帳號

第一次啟動自動建立:帳號 `admin` / 密碼 `Admin1234`(會被強制要求改密碼)。

## Part 3 預計補充

- Vue 3 + Vite + Pinia + Element Plus 前端完整骨架
- WebSocket composable + task 進度元件
- Nginx 反向代理設定


PHP 測試監控系統重構為 Python 版本的專案骨架。

## 這個壓縮檔的範圍 (Part 1/3:基礎層)

這是分三次產出的**第一部分**,涵蓋:

- ✅ 專案設定 (`pyproject.toml`, `.env.example`, `config.py`)
- ✅ 核心工具 (`app/core/`):日誌、例外、安全、回應格式
- ✅ **認證模組完整版** (`app/auth/`):
  - SQLite + SQLAlchemy (User / Role / Permission / AuditLog)
  - JWT (access + refresh)
  - bcrypt 密碼 + 中等強度驗證
  - `require_permission()` 相依注入
  - 5 個角色的自動 seed
  - 稽核日誌工具
- ✅ FastAPI 主進入點 (`app/main.py`)

## 還沒有的 (Part 2, Part 3 會補)

- ⏳ **Part 2**:API 路由層、Service 層、Repository 空框(DB + Filesystem)、Celery workers、WebSocket
- ⏳ **Part 3**:Vue 3 前端完整骨架 + Docker Compose + Dockerfile + 部署文件

⚠️ **注意:現在這個狀態還不能直接啟動**,因為 `app/main.py` 會 import 還沒產出的路由檔案(`app.api.v1.auth`、`users`、`tests` 等)。需要等 Part 2 完成才能跑。

---

## 怎麼組合三次的產出

三次都會產出到同一個專案根目錄,彼此不會衝突。做法:

1. 下載 Part 1 → 解壓到某個資料夾,例如 `~/monitor/`
2. 下一個對話產出 Part 2 後,把檔案**合併進同一個 `~/monitor/`** (Part 2 只會新增檔案,不會覆蓋 Part 1)
3. Part 3 同樣合併進去
4. 合併完成後,整個專案就可以啟動

建議用 `git` 管理:
```bash
cd ~/monitor
git init
git add -A && git commit -m "Part 1: foundation + auth"
# 收到 Part 2 後覆蓋檔案,再 commit
# 收到 Part 3 後同上
```

---

## 部署策略(三種選擇)

你沒決定部署環境,我給三種階段性選項,建議從上往下升級:

### 選項 A:本機開發 (馬上就能跑 — 等 Part 2 完成)

最快看到東西的方式。只需要本機 Python 3.11+ 和 Redis。

```bash
# 1. 安裝 uv (現代 Python 套件管理)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 建立虛擬環境並安裝
cd ~/monitor
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 3. 設定環境
cp .env.example .env
# 編輯 .env,至少改 SECRET_KEY 跟 DEFAULT_ADMIN_PASSWORD

# 4. 啟動 Redis (需要)
# macOS: brew install redis && brew services start redis
# Linux: sudo apt install redis-server && sudo systemctl start redis

# 5. 啟動 API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. 啟動 Celery worker (另一個終端)
celery -A app.workers.celery_app worker --loglevel=info

# 7. 啟動 Celery Beat (定時任務,另一個終端)
celery -A app.workers.celery_app beat --loglevel=info
```

驗證:打開 http://localhost:8000/docs 看 Swagger UI。

### 選項 B:Docker Compose (推薦 — Part 3 會產出)

一台 Linux 機器就能跑,所有服務容器化。

```bash
cd ~/monitor
cp .env.example .env
# 編輯 .env

docker compose up -d              # 啟動所有服務
docker compose logs -f api        # 看 API 日誌
docker compose down               # 停止
```

服務清單:
- `api` : FastAPI (port 8000)
- `worker` : Celery worker
- `beat` : Celery 排程
- `redis` : Redis
- `frontend` : Vue 3 dev server (port 5173)

正式上線時前面加 Nginx 反向代理 + HTTPS (Let's Encrypt)。

### 選項 C:Kubernetes (未來擴充,不急著做)

如果未來需要橫向擴充(多個 worker 跑多地區測試),容器直接推到 K8s,程式碼不用改。每個服務變成一個 Deployment:
- `api-deployment` (可多 replica + HPA)
- `worker-deployment` (可多 replica)
- `beat-deployment` (只能 1 replica,避免重複排程)
- `redis` 用 Helm chart 裝

---

## 對你的建議(根據你的情境)

- **現在**:Part 2 產出後先用**選項 A(本機)**驗證邏輯跑得通
- **第一次上線**:用**選項 B(Docker Compose)**放在你們內部 Linux Server
- **未來擴充**:規模大了再考慮選項 C

PHP 專案通常踩的坑是「環境不一致、上線前才發現相依壞掉」,容器化就是為了根治這個。

---

## 預設 admin 帳號

第一次啟動會自動建立(從 `.env` 讀):
- 帳號: `admin`
- 密碼: `Admin1234` (請立刻改)

`must_change_password=True`,登入後會被要求改密碼。

## 目錄結構

```
monitor/
├── app/
│   ├── main.py              # FastAPI 進入點
│   ├── config.py            # 設定
│   ├── core/                # 日誌、例外、安全、回應
│   ├── auth/                # ★ 認證模組 (完整)
│   ├── api/v1/              # (Part 2)
│   ├── schemas/             # (Part 2)
│   ├── services/            # (Part 2)
│   ├── repositories/        # ★ DB + Filesystem 空框 (Part 2)
│   ├── workers/             # Celery (Part 2)
│   └── websocket/           # WebSocket (Part 2)
├── frontend/                # Vue 3 (Part 3)
├── tests/
├── data/                    # SQLite 檔案放這
├── pyproject.toml
└── .env.example
```
