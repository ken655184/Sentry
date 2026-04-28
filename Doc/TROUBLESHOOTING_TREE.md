# Monitor System — 故障排查決策樹

```
┌─────────────────────────────────────────────────────────────────┐
│           系統故障 → 先執行快速自檢                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┬──────────────────┐
        │                         │                  │
        ▼                         ▼                  ▼
   所有服務都DOWN         僅部分服務DOWN         個別功能異常
        │                         │                  │
        └─────────────┬───────────┴──────────────────┘
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
    檢查容器狀態          查看服務日誌
    docker ps -a        docker-compose logs
           │                     │
      ┌────┴────┐          ┌─────┴─────┐
      │ 有       │          │ Error?    │
      │ Exited   │          │           │
      ▼          ▼          ▼           ▼
   重啟容器   網路問題   解析 error  排查根因
   restart              (見下方樹)
```

---

## 🌳 故障樹 #1: API 無法啟動

```
API 容器 Exited
│
├─ 檢查日誌 ──────────────────────┐
│  docker-compose logs api       │
│                                │
└────────┬───────────────────────┘
         │
    ┌────┴──────┬──────────┬──────────┐
    ▼           ▼          ▼          ▼
  Syntax    Module      Database   Network
  Error     Import      Error      Error
    │       Error         │          │
    ▼       │             ▼          ▼
  檢查      ▼          SQLite      Redis
  .env    缺少        連接失敗     連接失敗
  語法    依賴         │            │
    │     │           ▼            ▼
    ▼     ▼        檢查 .env      檢查
  驗證    運行      AUTH_DB_URL   REDIS_URL
  改正    以下         │            │
    │    檢查   ┌──────┘────────┐   ▼
    │     │     ▼              ▼  改正
    │     │  路徑對?  權限對?   .env
    ▼     ▼   是 ──→  是 ──→   或
  重啟    pip list   否  否      重啟
  api     | grep      │  │      redis
          -E fastapi  ▼  ▼
              │     手動建立  chmod
              ▼     目錄      755
          缺少?
              │
         ✓是 ▼
            重建
            image
```

**快速修復**:

```bash
# 步驟 1: 檢查 .env
python3 -c "from app.config import settings; print('✓')" 2>&1

# 步驟 2: 檢查依賴
docker-compose exec api pip list | grep -E "fastapi|sqlalchemy|celery"

# 步驟 3: 看完整日誌
docker-compose logs api --tail 100

# 步驟 4: 清理重啟
docker-compose down
docker system prune -f
docker-compose up -d api
```

---

## 🌳 故障樹 #2: Worker 無法連接 Celery Broker

```
Worker 容器卡在 Connecting to Redis
│
├─ 檢查 Redis 狀態 ────────────┐
│  docker-compose ps redis    │
│                             │
└──────┬──────────────────────┘
       │
   ┌───┴───┐
   ▼       ▼
  Up?    Exited?
   │       │
   ├YES─→  ├NO──→ 檢查 Redis 日誌
   │       │      docker-compose logs redis
   │       ▼      │
   │     檢查:    ├─ 磁碟滿?
   │     - 埠     │  df -h
   │       6379   │  清理 /tmp
   │     - 記憶   ├─ 記憶體不足?
   │       體     │  free -h
   │     - 磁碟   │  重啟 Redis
   │             └─ 重新構建
   ▼                 image
  Docker
  network?    ┌─────────────────┐
   │          │ 可連接 Redis?   │
   │          │ docker exec api │
   │          │  redis-cli ping │
   ▼          └────────┬────────┘
  檢查:              ✓
  docker           PONG
  network    ┌──────┐  │
  ls         │      ▼  ▼
   │         No   檢查
   │         │    CELERY_
   │         │    BROKER_
   │         │    URL
   └─────────┘
```

**快速修復**:

```bash
# 步驟 1: Redis 有沒有起來
docker-compose ps redis

# 步驟 2: 手動 ping Redis
docker-compose exec redis redis-cli ping
# 預期: PONG

# 步驟 3: 檢查 Broker URL
grep CELERY_BROKER_URL .env

# 步驟 4: 檢查 worker 日誌
docker-compose logs worker-default --tail 50

# 步驟 5: 重啟 worker
docker-compose restart worker-default
```

---

## 🌳 故障樹 #3: Task 卡在 PENDING

```
Task 狀態一直 PENDING (沒有執行)
│
├─ Worker 有沒有在跑? ──────────┐
│  celery -A app.workers       │
│   inspect active_queues      │
│                              │
└────────┬─────────────────────┘
         │
    ┌────┴─────┬──────────┐
    ▼           ▼          ▼
   無 Worker   有 Worker  隊列滿/
   (空)        但無       不動
              活躍
    │          task
    │          │
    ▼          ▼
  為什麼沒   為什麼沒
  啟動?      執行?
    │          │
    │      ┌───┴──────┐
    │      ▼          ▼
    │    優先級   Worker
    │    問題?   CPU 滿?
    │      │          │
    │      ▼          ▼
    │    檢查隊列  檢查:
    │    routing  docker stats
    │      │       │
    │      │      是──→ 增加
    │      │          concurrency
    │      └─→ 重啟
    │         worker
    ▼
  檢查:
  docker
  ps | grep
  worker
   │
  是否都
  Exited?
   │
   ├NO──→ 重啟
   │      docker
   │      restart
   │      worker-*
   │
   └YES─→ 查日誌
         並參照
         故障樹 #2
```

**快速修復**:

```bash
# 步驟 1: 檢查活躍 worker
docker-compose exec api celery -A app.workers.celery_app inspect active

# 步驟 2: 檢查隊列長度
docker-compose exec redis redis-cli LLEN celery

# 步驟 3: 檢查 worker 是否真的在跑
docker-compose ps worker-*

# 步驟 4: 重新投遞 task
docker-compose exec api celery -A app.workers.celery_app revoke <task_id> --terminate

# 步驟 5: 檢查 worker 資源
docker stats
```

---

## 🌳 故障樹 #4: WebSocket 連線失敗

```
WS 連線立即斷開 (disconnect before welcome)
│
├─ 檢查 Token ──────────────────┐
│  URL: ws://host/ws?token=X   │
│  Token 是有效的 JWT token?    │
│                              │
└────────┬─────────────────────┘
         │
    ┌────┴─────┐
    ▼           ▼
  有 Token   無 Token
   │          │
   ▼          ▼
 確認:      錯誤碼
 - 非空     4008
 - 非過期   (JWT 失敗)
   │
   ├NO──→ 重新登入取 token
   │      POST /api/v1/auth/login
   │
   └YES─→ 檢查 API 日誌
         docker logs api
           │
        ┌──┴────┐
        ▼       ▼
      JWT    其他
     驗證    錯誤
     失敗
        │
        └─→ 見下方 JWT 樹
```

**JWT 驗證失敗樹**:

```
JWT decode error
│
├─ 檢查 SECRET_KEY ────┐
│  grep SECRET_KEY   │
│  .env              │
│                    │
└──────┬─────────────┘
       │
   ┌───┴────────────────┐
   ▼                    ▼
 與登入時    不同
 的值?      SECRET_KEY?
   │          │
   │          ▼
   ▼      重新登入
 已過期?  或重啟 API
   │    (SECRET_KEY
   ▼     變了)
 檢查
 token
 的
 "exp"
 欄位
 (用
 jwt.io
 解碼)
```

**快速修復**:

```bash
# 步驟 1: 獲取新 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"..."}' | jq -r '.tokens.access_token')

# 步驟 2: 用 wscat 測試 WS
wscat -c "ws://localhost:8000/ws?token=$TOKEN"

# 步驟 3: 檢查 token 是否過期(用 jwt.io 解碼)
echo $TOKEN | cut -d. -f2 | base64 -d | jq .

# 步驟 4: 檢查 SECRET_KEY 是否改變
docker-compose exec api python3 -c "from app.config import settings; print(settings.SECRET_KEY[:10])"
```

---

## 🌳 故障樹 #5: 資料庫被鎖定 (Database Locked)

```
頻繁出現 "database is locked" 錯誤
│
├─ 因為 SQLite ────────────────┐
│  多進程/多線程寫入            │
│  同時競爭                    │
│                             │
└────────┬────────────────────┘
         │
     ┌───┴───┐
     ▼       ▼
   快速   永久
   修復   修復
    │      │
    ▼      ▼
 重啟   改用
 API   PostgreSQL
 container  (見 SOP §7.2)
    │      │
    │      ▼
    │    修改 .env
    │    AUTH_DB_URL=
    │    postgresql+asyncpg://...
    │      │
    │      ▼
    │    加入 postgres
    │    service
    │    docker-compose
    │    .yml
    │      │
    │      ▼
    │    重建 & 遷移
    │
    └──────────────→ 監看日誌,確認無鎖
```

**快速修復**:

```bash
# 步驟 1: 找出誰在持有 lock
lsof /opt/monitor/data/auth.db

# 步驟 2: 強制重啟 API
docker-compose restart api

# 步驟 3: 清理 -journal 檔案(SQLite 遺留的)
rm -f /opt/monitor/data/auth.db-journal

# 步驟 4: 驗證
curl http://localhost:8000/health
```

---

## 🌳 故障樹 #6: 高記憶體使用 (Memory Leak)

```
Worker 容器記憶體逐漸升高,最後 OOM killed
│
├─ 檢查記憶體使用 ──────────────┐
│  docker stats                │
│  或                          │
│  ps aux | grep worker       │
│                             │
└────────┬────────────────────┘
         │
    ┌────┴──────┐
    ▼           ▼
  穩定值   緩慢上升
  ≤512M    (洩漏)
   │          │
   ▼          ▼
  正常     ┌──┴──────────┐
        │ 啟動 Flower  │
        │ 監控細節    │
        │ (可選)     │
        │             │
        └─→ 檢查:
           - Task 堆積?
           - 結果 Backend
             滿了?
           - Pub/Sub
             訂閱未清理?
             │
            ┌┴─────────┐
            ▼          ▼
          是        否
           │          │
           ▼          ▼
        清理    檢查代碼
        Redis   是否有
        結果    global
        (見    變數
        下)    持續增長
             │
             ▼
           新增
           __del__()
           清理邏輯
```

**快速修復**:

```bash
# 步驟 1: 監看記憶體
watch -n 1 'docker stats --no-stream | grep worker'

# 步驟 2: 檢查結果 backend 佔用
docker-compose exec redis redis-cli INFO memory

# 步驟 3: 清理過期結果(保留 1 小時內)
docker-compose exec redis redis-cli EVAL \
  "return redis.call('del', 'celery-result-ttl')" 0

# 步驟 4: 重啟該 worker
docker-compose restart worker-default

# 步驟 5: 設定記憶體限制(docker-compose.yml)
services:
  worker-default:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

---

## 📊 決策樹使用指南

1. **遇到故障** → 先看對應的故障樹
2. **快速修復** → 執行樹下方的 bash 指令
3. **問題未解** → 往下一層樹深入診斷
4. **記錄每一步** → 便於日後追蹤根因

---

## 🚨 緊急聯絡

若以上都無法解決,請聯絡:

| 故障類型 | 聯絡人 | 電話 | 信箱 |
|---------|--------|------|------|
| API/應用 | Dev Team | _____ | dev@company.com |
| 基礎設施 | Ops Team | _____ | ops@company.com |
| 資料庫 | DBA | _____ | dba@company.com |
| 24/7 值班 | Oncall | _____ | oncall@company.com |

並提供:
- [ ] 故障開始時間
- [ ] 完整日誌 (`docker-compose logs --since 10m > logs.txt`)
- [ ] 系統狀態快照 (`docker ps; df -h; free -h`)
