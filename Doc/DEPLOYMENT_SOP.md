# Monitor System (Part 2) — 上線 SOP

**版本**: 1.0  
**最後更新**: 2025-04-27  
**適用環境**: Linux (生產/測試)  
**預估時間**: 30-45 分鐘(首次) / 15-20 分鐘(例行更新)

---

## 📋 快速檢查清單

部署前請確認以下事項已完成:

- [ ] 已取得本機代碼最新版本 (`git pull`)
- [ ] `.env` 已針對目標環境調整
- [ ] `SECRET_KEY` 已更換為 ≥32 字元的隨機值
- [ ] 目標機器已安裝 Docker + Docker Compose (≥3.9)
- [ ] 目標機器上 Redis / 資料庫有備份策略
- [ ] 運維團隊已收到本 SOP 副本
- [ ] 有回滾計劃(見§5.3)

---

## 1️⃣ 環境準備

### 1.1 目標機器基礎檢查

```bash
# 檢查 OS
uname -a
# 應為 Linux (Ubuntu 20.04 LTS+ 或 CentOS 8+ 推薦)

# 檢查 Docker
docker --version        # ≥ 20.10.0
docker-compose --version  # ≥ 1.29.0 (或用 docker compose v2)

# 檢查磁碟空間
df -h
# /data 至少預留 10GB(SQLite + artifacts)

# 檢查網路連線
ping 8.8.8.8
curl -I https://hub.docker.com  # 能拉 image
```

### 1.2 建立目錄結構

```bash
# 假設部署到 /opt/monitor
sudo mkdir -p /opt/monitor/data
sudo mkdir -p /opt/monitor/logs
sudo mkdir -p /opt/monitor/certs  # TLS 憑證用

# 權限設定(執行 Docker daemon 的使用者,通常 root 或 docker group)
sudo chown -R 1000:1000 /opt/monitor/data
sudo chmod 755 /opt/monitor/data
```

### 1.3 環境變數設定

```bash
cd /opt/monitor

# 複製範本並編輯
cp .env.example .env
# 以下為關鍵項(根據你的環境替換):

cat >> .env << 'EOF'
# ===== 應用基本 =====
APP_NAME=MonitorSystem
APP_ENV=production
DEBUG=false
SECRET_KEY=<YOUR-RANDOM-32-CHAR-STRING>  # !! 務必更換

# ===== 認證 =====
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=<CHANGE_ME_ON_FIRST_LOGIN>
DEFAULT_ADMIN_EMAIL=ops@company.com

# ===== DB (SQLite 路徑) =====
AUTH_DB_URL=sqlite+aiosqlite:///./data/auth.db

# ===== 外部資源路徑(根據實際情況調整) =====
FS_LOG_PATH=/var/log/monitor
FS_CONFIG_PATH=/etc/monitor
FS_ARTIFACT_PATH=/data/artifacts

# ===== Redis / Celery(Docker 內部通訊) =====
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# ===== 稽核日誌保留 =====
AUDIT_LOG_RETENTION_DAYS=180

# ===== CORS =====
CORS_ORIGINS=https://your-frontend-domain.com,http://localhost:3000

# ===== Flower (選填,監控 UI) =====
FLOWER_USER=monitor
FLOWER_PASSWORD=<STRONG_PASSWORD>
EOF
```

**⚠️ 重要提醒:**
- `SECRET_KEY` 用指令生成: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- 不要用預設的 `Admin1234` — 首次登入後立即更改
- 若使用 HTTPS,需自行設定 TLS 證書(見 §4.5)

### 1.4 驗證環境變數

```bash
# 測試環境變數載入
python3 -c "from app.config import settings; print(settings.APP_ENV, settings.SECRET_KEY[:10]+'***')"
```

---

## 2️⃣ 代碼部署

### 2.1 拉取代碼

```bash
cd /opt/monitor

# 若已是 git repo
git fetch origin main
git checkout main
git reset --hard origin/main

# 或直接複製檔案(非 git 環境)
# scp -r /local/path/monitor/* user@server:/opt/monitor/
```

### 2.2 驗證代碼完整性

```bash
# 檢查關鍵檔案是否存在
test -f docker-compose.yml && echo "✓ docker-compose.yml"
test -f Dockerfile && echo "✓ Dockerfile"
test -f pyproject.toml && echo "✓ pyproject.toml"
test -f .env && echo "✓ .env"
test -d app/auth && echo "✓ app/ structure"
test -d app/workers && echo "✓ app/workers/"
test -d tests && echo "✓ tests/"
```

### 2.3 清理舊的 container 和 image(首次或大版本更新)

```bash
# 停止舊 container
docker-compose down

# 移除舊 image(可選,保留可加快重建)
docker image rm monitor-app 2>/dev/null || true

# 清理懸空 image(占用空間)
docker image prune -f
```

---

## 3️⃣ 構建與啟動

### 3.1 構建 image

```bash
cd /opt/monitor

# 方式 1: Docker Compose 自動構建(推薦)
docker-compose build

# 方式 2: 手動 Docker 構建
docker build -t monitor-app:latest -f Dockerfile .
```

**預期時間**: 3-5 分鐘(首次) / 1 分鐘(有 layer cache)

### 3.2 啟動所有服務

```bash
# 方式 1: 後台啟動(推薦生產)
docker-compose up -d

# 方式 2: 前台啟動(調試用)
docker-compose up

# 查看啟動進度
docker-compose logs -f api
```

### 3.3 驗證服務已啟動

```bash
# 等待 30 秒讓服務穩定
sleep 30

# 檢查容器狀態
docker-compose ps
# 預期:api、redis、worker-default、worker-heavy、worker-audit 都是 Up

# 檢查各服務網路
docker-compose exec api curl -s http://localhost:8000/health | jq .
# 應回傳: {"status":"ok","app":"MonitorSystem","env":"production"}

# 檢查 Celery worker 連接
docker-compose exec api celery -A app.workers.celery_app inspect ping
# 應回傳: {'worker-default@...': {'ok': 'pong'}, ...}
```

---

## 4️⃣ 上線驗證

### 4.1 健康檢查

```bash
# 1. API health endpoint
curl -s http://localhost:8000/health | jq .

# 2. OpenAPI docs 可訪問
curl -I http://localhost:8000/docs

# 3. Metrics endpoint (Prometheus)
curl -s http://localhost:8000/metrics | head -20
```

### 4.2 認證功能驗證

```bash
# 1. 登入
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin1234"}')

# 提取 token
TOKEN=$(echo $RESPONSE | jq -r '.tokens.access_token')
echo "Token: $TOKEN"

# 2. 用 token 查詢當前使用者
curl -s http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### 4.3 Task 排隊驗證

```bash
# 1. 觸發一個簡單的 task
TASK_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/tasks/dispatch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"job_key":"example.echo","params":{"msg":"hello"}}')

TASK_ID=$(echo $TASK_RESPONSE | jq -r '.task_id')
echo "Task ID: $TASK_ID"

# 2. 查詢 task 狀態(等 5 秒)
sleep 5
curl -s http://localhost:8000/api/v1/tasks/$TASK_ID/status \
  -H "Authorization: Bearer $TOKEN" | jq .
# 應見 "state": "SUCCESS"
```

### 4.4 WebSocket 驗證(可選,需 wscat)

```bash
# 安裝 wscat
npm install -g wscat

# 連線到 WebSocket
wscat -c "ws://localhost:8000/ws?token=$TOKEN"
# 輸入:
# {"op":"ping"}
# 預期回覆: {"type":"pong"}

# Ctrl+C 退出
```

### 4.5 TLS/HTTPS 設定(生產環境)

若需 HTTPS,在 API container 前加 Nginx 反向代理:

```nginx
# /opt/monitor/nginx.conf
upstream api {
    server api:8000;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/certs/cert.pem;
    ssl_certificate_key /etc/certs/key.pem;

    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

在 `docker-compose.yml` 中加入:

```yaml
nginx:
  image: nginx:latest
  ports:
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf
    - ./certs:/etc/certs
  depends_on:
    - api
```

---

## 5️⃣ 上線後監控

### 5.1 日誌監控

```bash
# 即時日誌
docker-compose logs -f api

# 只看 ERROR
docker-compose logs api | grep ERROR

# 保存到檔案(運維查檔)
docker-compose logs api > /opt/monitor/logs/api.log 2>&1
```

### 5.2 Celery 監控(Flower 可選)

```bash
# 啟用 Flower 監控 UI
docker-compose --profile monitoring up -d flower

# 訪問 http://localhost:5555
# 預設帳密: admin / admin (已在 .env 設定)
```

Flower 可查看:
- 活躍 worker 數
- Task 隊列狀態
- Task 執行歷史
- Worker 資源使用

### 5.3 資料庫備份

```bash
# SQLite 備份(每日凌晨 2 點)
0 2 * * * cp /opt/monitor/data/auth.db /backup/auth.db.$(date +\%Y\%m\%d)

# Redis RDB 備份(docker-compose 已內含 persist)
# 檢查 redis persistent 狀態
docker-compose exec redis redis-cli BGSAVE

# 備份 RDB 檔案
docker cp monitor-redis-1:/data/dump.rdb /backup/redis.dump
```

### 5.4 Prometheus metrics 收集

若有監控系統(Prometheus/Grafana),訂閱:

```bash
# Prometheus job 設定範例
scrape_configs:
  - job_name: 'monitor-system'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

重點指標:
- `monitor_ws_active_connections` — 活躍 WS 連線數
- `monitor_task_dispatched_total` — 投遞的 task 累計數
- `monitor_task_result_total` — task 執行結果(成功/失敗)

---

## 6️⃣ 故障排查

### 6.1 API 無法啟動

**症狀**: `docker-compose logs api` 顯示 error

```bash
# 檢查 .env 語法
python3 -c "from app.config import settings; print('OK')"

# 檢查 DB 連線
docker-compose exec api python3 -c "from app.auth.database import engine; print('OK')"

# 檢查依賴完整性
docker-compose exec api pip list | grep -E "fastapi|sqlalchemy|celery"
```

### 6.2 Celery worker 無法連接 Redis

**症狀**: `docker-compose logs worker-default` 顯示 `ConnectionError`

```bash
# 測試 Redis 連線
docker-compose exec redis redis-cli ping
# 應回傳: PONG

# 檢查 Redis 負載
docker-compose exec redis redis-cli INFO stats

# 清理 Redis(⚠️ 會清除所有 queue,謹慎!)
docker-compose exec redis redis-cli FLUSHALL
```

### 6.3 Task 卡在 PENDING

**症狀**: 投遞的 task 一直處於 `PENDING` 狀態

```bash
# 檢查 worker 是否真的在跑
docker-compose exec api celery -A app.workers.celery_app inspect active

# 檢查佇列長度
docker-compose exec redis redis-cli LLEN celery

# 手動重試 task
docker-compose exec api celery -A app.workers.celery_app revoke <task_id> --terminate
```

### 6.4 記憶體洩漏(worker OOM)

**症狀**: worker 容器逐漸消耗更多記憶體

```bash
# 監看 worker 記憶體
docker stats monitor-worker-default-1

# 重啟該 worker(自動重建)
docker-compose restart worker-default

# 或限制容器記憶體(在 docker-compose.yml)
services:
  worker-default:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

### 6.5 SQLite 資料庫被鎖定

**症狀**: 多筆寫入操作出現 `database is locked` error

```bash
# 檢查誰在持有 lock
lsof /opt/monitor/data/auth.db

# 臨時方案:重啟 API container
docker-compose restart api

# 永久方案:改用 PostgreSQL(見 §7.2)
```

---

## 7️⃣ 升級與擴展

### 7.1 版本升級步驟

```bash
# 1. 備份現有資料
docker-compose exec api cp /data/auth.db /data/auth.db.backup

# 2. 停止服務
docker-compose down

# 3. 拉取新代碼
git pull origin main

# 4. 重建 image
docker-compose build

# 5. 啟動新版本
docker-compose up -d

# 6. 驗證
curl http://localhost:8000/health
```

### 7.2 遷移到 PostgreSQL(生產推薦)

若 SQLite 在高併發下頻繁鎖定,遷移步驟:

```bash
# 1. 在 .env 修改 DB URL
AUTH_DB_URL=postgresql+asyncpg://user:pass@postgres:5432/monitor

# 2. docker-compose.yml 加入 postgres
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: monitor
      POSTGRES_PASSWORD: <strong_password>
      POSTGRES_DB: monitor
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U monitor"]
      interval: 10s
      timeout: 5s
      retries: 5

# 3. 更新依賴
# 在 pyproject.toml 加入:
# "psycopg[binary]>=3.1.0",

# 4. 重建與遷移
docker-compose build
docker-compose up -d postgres
sleep 10
docker-compose up -d api
```

### 7.3 水平擴展 worker(高負載)

```bash
# docker-compose.yml 改為:
worker-default:
  <<: *app-base
  command: >
    celery -A app.workers.celery_app worker
      --queues default
      --concurrency 8    # ⬆️ 增加 concurrency
      --loglevel info
      --hostname worker-default-1@%h
  deploy:
    replicas: 2         # ⬆️ 啟動 2 個 instance

# 或用 docker-compose scale
docker-compose up -d --scale worker-default=3
```

---

## 8️⃣ 安全檢查清單

上線前務必完成:

- [ ] **SECRET_KEY** — 已更換為隨機 32+ 字元
- [ ] **預設帳密** — admin 帳號已強制改密(首次登入)
- [ ] **CORS** — 只允許自家域名,不用 `*`
- [ ] **TLS/HTTPS** — 生產環境已啟用
- [ ] **防火牆** — 只開放 80/443,關閉 5555(Flower) 和 6379(Redis)
- [ ] **備份策略** — SQLite / Redis 有自動化備份
- [ ] **日誌保留** — 稽核日誌有 180 天保留期(可調整)
- [ ] **更新檢查** — 依賴套件無重大漏洞

```bash
# 檢查已知漏洞
pip install safety
safety check
```

---

## 9️⃣ 常見問題 (FAQ)

### Q: 如何更改預設 admin 密碼?

```bash
# 登入 API,在使用者管理頁面改密碼
# 或直接修改資料庫:
docker-compose exec api python3 << 'EOF'
from app.core.security import hash_password
from app.auth.database import AsyncSessionLocal
from app.auth.models import User
from sqlalchemy import select
import asyncio

async def change():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one()
        user.hashed_password = hash_password("NewPassword123")
        user.must_change_password = False
        await db.commit()
        print("Password changed!")

asyncio.run(change())
EOF
```

### Q: 如何清理舊的稽核紀錄?

```bash
# 方式 1: Celery beat 會自動清理(每日凌晨 3 點)
# 方式 2: 手動觸發
docker-compose exec api python3 -c \
  "from app.workers.jobs.system_jobs import cleanup_old_audit_logs; cleanup_old_audit_logs(days=90)"
```

### Q: 如何查看所有執行中的 task?

```bash
docker-compose exec api celery -A app.workers.celery_app inspect active
```

### Q: 如何備份整個系統狀態?

```bash
# 完整備份
tar czf /backup/monitor-$(date +%Y%m%d-%H%M%S).tar.gz \
  /opt/monitor/data \
  /opt/monitor/.env

# 只備份資料庫
docker-compose exec api cp /data/auth.db /data/auth.db.backup
```

### Q: 如何在不停機的情況下部署新版本?

```bash
# 1. 只重啟無狀態 container(API)
docker-compose up -d api

# 2. worker 會逐個重啟,現有 task 會重試
docker-compose up -d worker-default worker-heavy worker-audit
```

---

## 🔟 回滾計劃

若新版本出現嚴重問題:

```bash
# 1. 立即停止新版本
docker-compose down

# 2. 恢復舊版本代碼
git revert HEAD
# 或
git checkout <previous-tag>

# 3. 重建
docker-compose build
docker-compose up -d

# 4. 驗證
curl http://localhost:8000/health

# 5. 還原資料(若有備份)
cp /backup/auth.db.backup /opt/monitor/data/auth.db
docker-compose restart api
```

---

## 聯絡與支援

- **運維團隊**: ops@company.com
- **開發團隊**: dev@company.com
- **應急電話**: (待補充)

---

**簽核**:  
部署人員: _________________ 日期: _________________  
主管核准: _________________ 日期: _________________  
