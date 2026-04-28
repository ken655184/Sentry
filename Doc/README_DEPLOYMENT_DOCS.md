# 📚 Monitor System 部署文件索引

這個資料夾包含完整的上線 SOP、檢查清單、故障排查樹和監控設定。

---

## 📄 文件清單

### 1️⃣ **DEPLOYMENT_SOP.md** ⭐ 從這裡開始
**用途**: 完整的上線標準作業流程  
**適合**: DevOps 工程師、運維團隊 (首次部署必讀)  
**長度**: ~500 行  
**主要內容**:
- ✅ 環境準備 (第1節)
- ✅ 代碼部署 (第2節)
- ✅ 構建與啟動 (第3節)
- ✅ 上線驗證 (第4節)
- ✅ 上線後監控 (第5節)
- ✅ 故障排查 (第6節)
- ✅ 升級與擴展 (第7節)

**快速查詢**:
```bash
grep -n "^## " DEPLOYMENT_SOP.md  # 看所有章節標題
```

---

### 2️⃣ **DEPLOYMENT_CHECKLIST.md** ✅ 用於簽核
**用途**: 部署前檢查清單 (可列印)  
**適合**: 部署前的最後驗證  
**長度**: ~2 頁 (可列印)  
**主要內容**:
- ☐ 代碼準備 (第1節)
- ☐ 環境設定 (第2節)
- ☐ 系統環境 (第3節)
- ☐ 數據備份 (第4節)
- ☐ 依賴構建 (第5節)
- ☐ 預啟動檢查 (第6節)
- ☐ 啟動驗證 (第7節)
- ☐ 安全檢查 (第8節)
- ☐ 文檔與交接 (第9節)
- ☐ 最終簽核 (第10節)

**使用方式**:
1. 列印本檔案
2. 部署前逐項檢查 (打 ☐ 符號)
3. 簽核並存檔

---

### 3️⃣ **TROUBLESHOOTING_TREE.md** 🌳 故障診斷
**用途**: 決策樹式的故障排查流程  
**適合**: 生產環境故障快速定位  
**長度**: ~400 行  
**包含 6 棵故障樹**:

| 故障樹 | 症狀 | 根因 |
|--------|------|------|
| #1 | API 無法啟動 | 環境配置、依賴問題 |
| #2 | Worker 無法連接 Broker | Redis 問題 |
| #3 | Task 卡在 PENDING | Worker 不執行 |
| #4 | WebSocket 連線失敗 | JWT 驗證、網路 |
| #5 | 資料庫被鎖定 | SQLite 並發問題 |
| #6 | 高記憶體使用 | 記憶體洩漏 |

**使用方式**:
```bash
# 線上查詢(範例)
grep -A 30 "故障樹 #2" TROUBLESHOOTING_TREE.md
```

每棵樹都配有:
- 樹狀決策圖
- 快速修復指令
- 完整診斷步驟

---

### 4️⃣ **MONITORING_SETUP.md** 📊 監控告警
**用途**: Prometheus + AlertManager + Grafana 設定  
**適合**: 上線後的持續監控  
**長度**: ~600 行  
**主要內容**:
- 📈 Prometheus 設定 (第1節)
- 🚨 告警規則 (第2節 - 預設 30+ 條規則)
- 📱 AlertManager 設定 (第3節)
- 🐳 Docker Compose 整合 (第4節)
- 📊 Grafana 儀表板 (第5節)
- 📢 告警通知 (第6節 - Slack / PagerDuty / Mail)
- 🎯 最佳實踐 (第7節)

**預設告警包括**:
- API 可用性 (宕機、高延遲、高錯誤率)
- Celery Worker 狀態 (宕機、隊列堆積)
- Redis 狀態 (記憶體滿、連線滿)
- 系統資源 (磁碟、CPU、記憶體)
- 資料庫狀態 (鎖定、寫入失敗)

**啟動監控**:
```bash
docker-compose --profile monitoring up -d
# 訪問: http://localhost:9090 (Prometheus)
#      http://localhost:9093 (AlertManager)
#      http://localhost:3000  (Grafana)
```

---

### 5️⃣ **QUICK_REFERENCE.md** 🚀 快速參考卡
**用途**: 常用指令速查 (可貼在機房!)  
**適合**: 運維人員日常操作  
**長度**: ~2 頁  
**快速查詢**:
- 🚀 基本指令
- 🔍 健康檢查
- 🆘 常見故障快速修復
- 📊 監控指令
- 🔑 認證相關
- 🐛 日誌查詢
- 🔄 更新部署
- 💾 備份相關
- ⚙️ 性能調整
- 🔐 安全相關
- 🚨 緊急操作

**列印使用**:
```bash
# 列印成 PDF (macOS)
wc -l QUICK_REFERENCE.md  # 檢查行數
lpr QUICK_REFERENCE.md     # 列印

# 或轉成 HTML 貼在內部 Wiki
pandoc QUICK_REFERENCE.md -o quick_ref.html
```

---

## 🎯 使用場景

### 場景 A: 首次線上部署 (預計 45 分鐘)

```
1. 讀完 DEPLOYMENT_SOP.md (第1-4節) ─────→ 了解流程
2. 逐項檢查 DEPLOYMENT_CHECKLIST.md ───→ 準備就緒
3. 執行 DEPLOYMENT_SOP.md (第3-4節) ───→ 部署 & 驗證
4. 簽核 DEPLOYMENT_CHECKLIST.md ────────→ 存檔紀錄
5. 部署後,設定監控 (MONITORING_SETUP.md) → 上線後監控
```

### 場景 B: 線上故障排查 (預計 5-15 分鐘)

```
1. 打開 TROUBLESHOOTING_TREE.md
2. 找到對應故障樹 (症狀相符)
3. 執行該樹下的快速修復指令
4. 未解決 → 深入診斷步驟
5. 問題解決 → 記錄於事後檢討會
```

### 場景 C: 日常監控與維護

```
1. 定期參考 QUICK_REFERENCE.md
2. 用 MONITORING_SETUP.md 的指令監控系統健康
3. 根據 Grafana 儀表板調整資源配置
4. 定期執行備份指令
```

### 場景 D: 版本升級 (預計 20 分鐘)

```
1. 參考 DEPLOYMENT_SOP.md 第7節 (升級步驟)
2. 用 QUICK_REFERENCE.md 中的備份指令
3. 執行部署
4. 用 DEPLOYMENT_CHECKLIST.md 驗證
```

---

## 🔑 關鍵概念回顧

### 系統架構

```
┌─────────────────────────────────────┐
│   用戶 (Vue 3 前端)                  │
└────────────┬────────────────────────┘
             │ REST + WebSocket + JWT
┌────────────▼────────────────────────┐
│   FastAPI (Port 8000)                │
│   - 認證 / 授權                       │
│   - 路由與驗證                        │
│   - WebSocket bridge                 │
└─┬──────────────────────────────────┬─┘
  │                                  │
  │ 同步                              │ 非同步
  │                                  │
  ▼                                  ▼
┌──────────────────┐        ┌─────────────────┐
│   SQLite (DB)    │        │  Redis          │
│   - 使用者       │        │  ├─ Broker      │
│   - 稽核日誌     │        │  ├─ Cache       │
│   - 權限         │        │  └─ Pub/Sub     │
└──────────────────┘        └────────┬────────┘
                                     │
                        ┌────────────┼────────────┐
                        ▼            ▼            ▼
                   ┌────────┐  ┌────────┐  ┌─────────┐
                   │Worker  │  │Worker  │  │  Beat   │
                   │Default │  │Heavy   │  │Scheduler│
                   └────────┘  └────────┘  └─────────┘
```

### 資源需求

| 元件 | 最小配置 | 推薦配置 | 備註 |
|------|---------|---------|------|
| API | 1C 1G | 2C 2G | FastAPI 高效 |
| Worker | 1C 1G | 2C 2G | 可多個 instance |
| Redis | - | 2G 可用 | 結果 backend 容易滿 |
| SQLite | - | 10GB | 高併發考慮遷移 PostgreSQL |
| 磁碟 | 20GB | 50GB | 審計日誌增長快 |

### 重要埠位

| 埠 | 服務 | 用途 | 對外 |
|----|------|------|------|
| 8000 | FastAPI | 公開 API / WebSocket | ✅ 是 |
| 5555 | Flower | Worker 監控 UI | ❌ 否 (內部) |
| 9090 | Prometheus | 指標採集 | ❌ 否 (內部) |
| 9093 | AlertManager | 告警管理 | ❌ 否 (內部) |
| 3000 | Grafana | 監控儀表板 | ❓ 可選 |
| 6379 | Redis | 訊息隊列 / 快取 | ❌ 否 (禁止) |

---

## 📋 部署前最終檢查

在執行部署前,請確認:

- [ ] 讀過 DEPLOYMENT_SOP.md 第 1-3 節
- [ ] 完成 DEPLOYMENT_CHECKLIST.md 的檢查
- [ ] `.env` 已配置且 SECRET_KEY ≥ 32 字元
- [ ] 資料庫已備份
- [ ] 有人待命(部署後 1 小時)
- [ ] 有回滾計劃(DEPLOYMENT_SOP.md 第 10 節)

---

## 🚀 立即開始

### 第一次部署?

```bash
# 1. 閱讀簡介(5 分鐘)
head -30 DEPLOYMENT_SOP.md

# 2. 檢查環境(10 分鐘)
cat DEPLOYMENT_CHECKLIST.md | head -40

# 3. 準備好了?
# 按照 DEPLOYMENT_SOP.md 第 2-4 節執行

# 4. 遇到問題?
# 查看 TROUBLESHOOTING_TREE.md
```

### 已經上線,想要監控?

```bash
# 1. 快速監控設定(20 分鐘)
grep -A 5 "1.2 啟動 Prometheus" MONITORING_SETUP.md

# 2. 設定告警(15 分鐘)
grep -A 10 "2.1 monitor-system-alerts.yml" MONITORING_SETUP.md

# 3. 訪問儀表板
# http://localhost:3000 (Grafana)
```

### 遇到故障需要快速修復?

```bash
# 打開故障樹
cat TROUBLESHOOTING_TREE.md | grep "故障樹"

# 快速參考
grep "快速修復" QUICK_REFERENCE.md
```

---

## 📞 需要幫助?

| 問題 | 查詢位置 |
|------|---------|
| 部署步驟不清楚 | DEPLOYMENT_SOP.md |
| 部署前檢查 | DEPLOYMENT_CHECKLIST.md |
| 故障排查 | TROUBLESHOOTING_TREE.md + QUICK_REFERENCE.md |
| 監控設定 | MONITORING_SETUP.md |
| 常用指令 | QUICK_REFERENCE.md |

---

## 📊 文件更新歷史

| 版本 | 日期 | 變更 |
|------|------|------|
| 1.0 | 2025-04-27 | 初版:SOP + 檢查清單 + 故障樹 + 監控 + 快速參考 |

---

## ⚖️ 免責聲明

本文件為部署指南,不構成法律或技術保證。實際部署前:
- 在測試環境驗證
- 備份所有關鍵資料
- 有人值守與回滾計劃
- 遵守公司的變更管理流程

---

**文件生成於**: 2025-04-27  
**適用版本**: Monitor System Part 2 (Celery + WebSocket 完整版)  
**維護者**: DevOps Team

