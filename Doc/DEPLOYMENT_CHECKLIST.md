# Monitor System — 部署前檢查清單 (Pre-Deployment Checklist)

日期: ____________  
部署者: ____________  
環境: ☐ 測試  ☐ 生產  ☐ 預發布

---

## 1️⃣ 代碼準備

- [ ] Git 代碼已更新到最新 (`git pull origin main`)
- [ ] `app/`, `tests/`, `Dockerfile`, `docker-compose.yml` 都存在
- [ ] `.env.example` 已複製為 `.env`
- [ ] 沒有未 commit 的改動 (`git status` 乾淨)

## 2️⃣ 環境設定

| 項目 | 檢查項 | 簽核 |
|------|--------|------|
| SECRET_KEY | ≥32 字元的隨機值(非預設) | ☐ |
| APP_ENV | 設為 `production` (非 development) | ☐ |
| DEBUG | 設為 `false` (非 true) | ☐ |
| DEFAULT_ADMIN_PASSWORD | 已更改為強密碼 | ☐ |
| REDIS_URL | 指向正確的 Redis(非 localhost) | ☐ |
| CORS_ORIGINS | 只包含自家域名 | ☐ |
| AUTH_DB_URL | SQLite 或 PostgreSQL 路徑正確 | ☐ |

## 3️⃣ 系統環境

### 機器資源

| 資源 | 最小要求 | 實際值 | 簽核 |
|------|---------|-------|------|
| 磁碟空間 | 20GB | _______ | ☐ |
| 可用記憶體 | 4GB | _______ | ☐ |
| CPU 核心 | 2 核 | _______ | ☐ |

### 軟體版本

| 軟體 | 最小版本 | 實際版本 | 簽核 |
|------|---------|---------|------|
| Docker | 20.10.0 | _________ | ☐ |
| Docker Compose | 1.29.0 | _________ | ☐ |
| Linux | 4.x | _________ | ☐ |
| Python | 3.11+ | _________ | ☐ |

### 網路連線

- [ ] DNS 可解析 (測試: `nslookup 8.8.8.8`)
- [ ] 可連接 Docker Hub (測試: `curl https://hub.docker.com`)
- [ ] 防火牆開放 80, 443 (測試: `telnet 80; telnet 443`)
- [ ] Redis 埠未被佔用 (測試: `netstat -ln | grep 6379`)

## 4️⃣ 數據備份

- [ ] SQLite 資料庫已備份到 `/backup/`
- [ ] Redis RDB 已備份到 `/backup/`
- [ ] 稽核紀錄已匯出/備份(可選)
- [ ] 備份媒體可恢復(已驗證)

## 5️⃣ 依賴構建

- [ ] Docker image 已成功構建 (`docker-compose build` 無 error)
- [ ] Image size 合理(< 500MB)
- [ ] 沒有過期或不安全的套件版本

```bash
# 快速檢查
docker image ls | grep monitor
pip install safety && safety check
```

## 6️⃣ 預啟動檢查

- [ ] `/opt/monitor/data/` 目錄存在且可寫
- [ ] `/opt/monitor/logs/` 目錄存在且可寫
- [ ] `.env` 檔案存在且內容合法

```bash
# 驗證 env
python3 -c "from app.config import settings; print(f'OK: {settings.APP_ENV}')"
```

---

## 7️⃣ 啟動驗證(啟動後檢查)

| 項目 | 預期結果 | 實際 | 簽核 |
|------|---------|------|------|
| API health | `{"status":"ok"}` | _______ | ☐ |
| Worker ping | `{'ok': 'pong'}` | _______ | ☐ |
| Admin login | token 回傳成功 | _______ | ☐ |
| Task dispatch | task_id 產生 | _______ | ☐ |
| WebSocket 連線 | `welcome` 訊息回傳 | _______ | ☐ |

```bash
# 快速驗證指令
curl http://localhost:8000/health
docker-compose exec api celery -A app.workers.celery_app inspect ping
```

---

## 8️⃣ 安全檢查

- [ ] SECRET_KEY 已妥善保管(不在 git 中)
- [ ] 預設帳密已改(admin → 強密碼)
- [ ] 防火牆已設定(Redis 6379 未向外開放)
- [ ] TLS/HTTPS 已啟用(生產)
- [ ] 稽核日誌已啟用

```bash
# 快速檢查
grep -E "SECRET_KEY|ADMIN_PASSWORD" .env
# 應該都不是預設值
```

---

## 9️⃣ 文檔與交接

- [ ] 運維團隊已收到本 SOP 副本
- [ ] 故障聯絡人已確認(見 SOP §聯絡與支援)
- [ ] 回滾計劃已準備好
- [ ] 監控告警已設定(可選)

---

## 🔟 最終簽核

| 角色 | 姓名 | 簽名 | 日期 |
|------|------|------|------|
| 部署工程師 | _______ | _______ | _______ |
| 運維經理 | _______ | _______ | _______ |
| 產品/專案負責人 | _______ | _______ | _______ |

---

## 注意事項

1. **務必備份** — 部署前一定要備份 SQLite 資料庫
2. **環境分離** — 測試環境和生產環境用不同的 `.env`
3. **逐步上線** — 先在測試環境驗證,再上生產
4. **監控待命** — 上線後 1 小時內有人值守
5. **文檔更新** — 部署完後更新此清單的實際值

---

**備註欄**:

_________________________________________________________________

_________________________________________________________________

_________________________________________________________________
