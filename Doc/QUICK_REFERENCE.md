# Monitor System 快速參考卡 (Quick Reference Card)

**可列印貼在你的機房!**

---

## 🚀 基本指令

```bash
# 啟動所有服務
docker-compose up -d

# 停止所有服務
docker-compose down

# 檢查狀態
docker-compose ps

# 查看日誌(即時)
docker-compose logs -f api

# 進入容器 shell
docker-compose exec api bash
```

---

## 🔍 健康檢查

```bash
# ✅ 快速健康檢查(執行此指令)
for check in api redis worker status; do
  case $check in
    api)
      echo "🔍 API Health:"
      curl -s http://localhost:8000/health | jq .
      ;;
    redis)
      echo "🔍 Redis Ping:"
      docker-compose exec redis redis-cli ping
      ;;
    worker)
      echo "🔍 Celery Workers:"
      docker-compose exec api celery -A app.workers inspect ping 2>/dev/null | jq .
      ;;
    status)
      echo "🔍 Container Status:"
      docker-compose ps --quiet | wc -l
      echo "containers running"
      ;;
  esac
done
```

---

## 🆘 常見故障快速修復

| 故障 | 快速修復 |
|------|---------|
| **API 不回應** | `docker-compose restart api` |
| **Worker 卡住** | `docker-compose restart worker-default worker-heavy worker-audit` |
| **Redis 連線失敗** | `docker-compose restart redis` |
| **Task 堆積** | `docker-compose exec redis redis-cli FLUSHDB 1` |
| **磁碟滿** | `docker system prune -a` (清理舊 image) |
| **記憶體洩漏** | `docker stats` + `docker-compose restart <service>` |

---

## 📊 監控指令

```bash
# 監看容器資源
watch -n 2 'docker stats --no-stream'

# 查看 Redis 記憶體
docker-compose exec redis redis-cli INFO memory | grep used_memory_human

# 查看 Celery 隊列
docker-compose exec redis redis-cli LLEN celery

# 查看活躍 task
docker-compose exec api celery -A app.workers inspect active

# 查看 worker 統計
docker-compose exec api celery -A app.workers inspect stats
```

---

## 🔑 認證相關

```bash
# 登入並取得 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"PASSWD"}' | jq -r '.tokens.access_token')

echo $TOKEN

# 測試 token 有效性
curl -s http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

## 🐛 日誌查詢

```bash
# 最近 50 行日誌
docker-compose logs api --tail 50

# 過去 1 小時的日誌
docker-compose logs --since 1h api

# 只看 ERROR 級別
docker-compose logs api | grep ERROR

# 保存日誌到檔案
docker-compose logs > /tmp/logs_$(date +%Y%m%d_%H%M%S).txt
```

---

## 🔄 更新部署

```bash
# 最安全的部署流程

# 1. 備份資料
docker-compose exec api cp /data/auth.db /data/auth.db.bak

# 2. 拉取新代碼
git pull origin main

# 3. 重建 image
docker-compose build

# 4. 無停機更新(逐個重啟)
docker-compose up -d api
sleep 30
docker-compose up -d worker-default
docker-compose up -d worker-heavy
docker-compose up -d worker-audit

# 5. 驗證
curl http://localhost:8000/health
```

---

## 💾 備份相關

```bash
# 備份資料庫
docker-compose exec api cp \
  /data/auth.db \
  /data/auth.db.$(date +%Y%m%d_%H%M%S)

# 備份整個 /data 目錄
tar czf backup-$(date +%Y%m%d).tar.gz /opt/monitor/data

# 恢復資料庫
docker-compose exec api cp \
  /data/auth.db.20250427_120000 \
  /data/auth.db
docker-compose restart api
```

---

## ⚙️ 環境變數修改

```bash
# 修改 .env
nano .env
# 改完後保存 (Ctrl+O, Ctrl+X)

# 重新載入環境變數
docker-compose down
docker-compose up -d

# 驗證
docker-compose exec api python3 -c \
  "from app.config import settings; print(settings.APP_ENV)"
```

---

## 📈 性能調整

```bash
# 增加 worker 並發度
# 在 docker-compose.yml 修改:
# concurrency: 8  (改大數字)

docker-compose up -d --scale worker-default=2  # 啟動 2 個 worker

# 監看效果
watch -n 2 'docker-compose ps'
```

---

## 🔐 安全相關

```bash
# 修改 admin 密碼(緊急修復)
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
        await db.commit()
        print("✓ Password changed to: NewPassword123")

asyncio.run(change())
EOF

# 檢查 SECRET_KEY 是否合適
grep SECRET_KEY .env | cut -d'=' -f2 | wc -c
# 應 ≥ 33 (32 + 換行符)
```

---

## 🚨 緊急操作

```bash
# 完全清除(⚠️ 會刪除所有資料!)
docker-compose down -v
docker system prune -a
rm -rf /opt/monitor/data/*
docker-compose up -d

# 強制殺死 hung 容器
docker kill $(docker-compose ps -q api)

# 看不到某個 container 的日誌?
docker logs <container_id> --tail 100
```

---

## 📞 聯絡資訊

| 項目 | 聯絡人 | 電話 | 信箱 |
|------|--------|------|------|
| API/應用 | Dev | _____ | dev@company.com |
| 基礎設施 | Ops | _____ | ops@company.com |
| 資料庫 | DBA | _____ | dba@company.com |
| 24/7 值班 | Oncall | _____ | oncall@company.com |

---

## 📚 完整文件

- 📖 **DEPLOYMENT_SOP.md** — 完整部署步驟
- ✅ **DEPLOYMENT_CHECKLIST.md** — 上線前檢查清單
- 🌳 **TROUBLESHOOTING_TREE.md** — 故障診斷樹
- 📊 **MONITORING_SETUP.md** — 監控告警設定

---

**最後更新**: 2025-04-27  
**版本**: Monitor System Part 2 (Celery + WebSocket)

