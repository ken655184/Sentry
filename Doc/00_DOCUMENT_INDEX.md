# 📦 部署文件包 — 完整清單

## 📂 文件清單與用途

```
.
├── README_DEPLOYMENT_DOCS.md ⭐ 【必讀】文件索引與使用指南
│   └─ 告訴你怎麼用下面的 4 份文件
│
├── DEPLOYMENT_SOP.md 📖 【完整上線流程】
│   ├─ 1️⃣  環境準備 (系統檢查、目錄建立、環境變數)
│   ├─ 2️⃣  代碼部署 (拉代碼、驗證、清理舊版本)
│   ├─ 3️⃣  構建與啟動 (docker-compose build/up)
│   ├─ 4️⃣  上線驗證 (health check、task dispatch、WebSocket)
│   ├─ 5️⃣  上線後監控 (日誌、Flower、備份、metrics)
│   ├─ 6️⃣  故障排查 (API down、Worker down、DB locked…)
│   ├─ 7️⃣  升級與擴展 (版本升級、PostgreSQL 遷移、水平擴展)
│   ├─ 8️⃣  安全檢查清單 (SECRET_KEY、CORS、TLS…)
│   ├─ 9️⃣  常見問題 FAQ (密碼改、清理日誌、查 task…)
│   └─ 🔟 回滾計劃 (故障時如何恢復)
│   💾 大小: ~50KB | ⏱  讀完時間: 30-45 分鐘
│
├── DEPLOYMENT_CHECKLIST.md ✅ 【部署前檢查清單】
│   ├─ 📋 10 大檢查區段(代碼、環境、系統、備份…)
│   ├─ 📊 資源需求表 (磁碟、記憶體、CPU、版本)
│   ├─ ✔️  啟動驗證項目 (可打勾)
│   ├─ 🔐 安全檢查項目
│   ├─ 📝 文檔與簽核欄位
│   └─ 🖨️  可列印 (A4 × 2 頁)
│   💾 大小: ~15KB | ⏱  用時: 20-30 分鐘(部署前)
│
├── TROUBLESHOOTING_TREE.md 🌳 【故障診斷決策樹】
│   ├─ 樹 #1: API 無法啟動
│   ├─ 樹 #2: Worker 無法連接 Broker
│   ├─ 樹 #3: Task 卡在 PENDING
│   ├─ 樹 #4: WebSocket 連線失敗
│   ├─ 樹 #5: 資料庫被鎖定
│   ├─ 樹 #6: 高記憶體使用
│   ├─ 🔧 每棵樹配有: 決策圖 + 快速修復 + 深層診斷
│   └─ 📞 緊急聯絡表
│   💾 大小: ~40KB | ⏱  查詢時間: 2-5 分鐘(故障排查)
│
├── MONITORING_SETUP.md 📊 【監控告警完整設定】
│   ├─ 1️⃣  Prometheus 設定 (prometheus.yml 範本)
│   ├─ 2️⃣  告警規則 (monitor-system-alerts.yml)
│   │   └─ 預設 30+ 條告警規則涵蓋:
│   │      - API 可用性 (宕機、延遲、錯誤率)
│   │      - Celery (Worker 宕機、隊列堆積)
│   │      - Redis (記憶體、連線、鍵值)
│   │      - 系統 (磁碟、CPU、記憶體)
│   │      - 資料庫 (鎖定、寫入失敗)
│   ├─ 3️⃣  AlertManager 設定 (alertmanager.yml)
│   ├─ 4️⃣  Docker Compose 整合 (完整 stack)
│   ├─ 5️⃣  Grafana 儀表板 (匯入 dashboard)
│   ├─ 6️⃣  告警通知整合 (Slack / PagerDuty / Email)
│   ├─ 7️⃣  監控最佳實踐
│   ├─ 8️⃣  HA 設定 (高級)
│   └─ 9️⃣  常見問題 FAQ
│   💾 大小: ~60KB | ⏱  設定時間: 30 分鐘
│
└── QUICK_REFERENCE.md 🚀 【日常快速參考卡】
    ├─ 🚀 基本指令 (up/down/ps/logs)
    ├─ 🔍 健康檢查 (API/Redis/Worker/Status)
    ├─ 🆘 常見故障快速修復表
    ├─ 📊 監控指令 (docker stats / redis / celery)
    ├─ 🔑 認證相關 (登入、取 token)
    ├─ 🐛 日誌查詢 (grep ERROR、時間範圍)
    ├─ 🔄 更新部署流程
    ├─ 💾 備份相關
    ├─ ⚙️  性能調整
    ├─ 🔐 安全相關
    ├─ 🚨 緊急操作 (強制殺死、清除)
    └─ 📞 聯絡資訊表
    💾 大小: ~20KB | ⏱  用時: 快速查詢 (< 1 分鐘)
```

---

## 🎯 快速導航

### 「我第一次部署,不知道從何開始」

```
第 1 步: 讀 README_DEPLOYMENT_DOCS.md
        └─ 了解 5 份文件的用途

第 2 步: 讀 DEPLOYMENT_SOP.md 第 1-2 節
        └─ 了解部署流程

第 3 步: 用 DEPLOYMENT_CHECKLIST.md 檢查環境
        └─ 確保所有前置條件都滿足

第 4 步: 執行 DEPLOYMENT_SOP.md 第 3-4 節
        └─ 部署 & 驗證

第 5 步: 簽核 DEPLOYMENT_CHECKLIST.md
        └─ 存檔紀錄
```

### 「系統上線後,要設定監控」

```
第 1 步: 讀 MONITORING_SETUP.md 第 1-3 節
        └─ 了解 Prometheus / AlertManager 概念

第 2 步: 複製 MONITORING_SETUP.md 中的設定檔
        └─ prometheus.yml / alertmanager.yml

第 3 步: docker-compose --profile monitoring up -d
        └─ 啟動整個監控 stack

第 4 步: 訪問 http://localhost:3000
        └─ 設定 Grafana dashboard

第 5 步: 修改 alertmanager.yml 的通知 URL (Slack / PagerDuty)
        └─ 收到告警通知
```

### 「線上出現故障,需要快速診斷」

```
第 1 步: 打開 TROUBLESHOOTING_TREE.md
        └─ 尋找症狀相符的故障樹

第 2 步: 沿著決策樹往下走
        └─ 樹枝會引導你診斷根因

第 3 步: 執行「快速修復」區段的指令
        └─ 若無效,執行「深層診斷」

第 4 步: 問題解決後,記錄根因
        └─ 便於日後預防
```

### 「我是運維新手,要快速上手」

```
第 1 步: 列印 QUICK_REFERENCE.md
        └─ 貼在你的工作區

第 2 步: 熟悉「基本指令」和「常見故障快速修復」
        └─ 日常 90% 的操作

第 3 步: 遇到不懂的,查 DEPLOYMENT_SOP.md 對應章節
        └─ 深入理解原理
```

---

## 📊 使用統計

| 使用場景 | 主要文件 | 輔助文件 | 預計時間 |
|---------|---------|---------|---------|
| 首次部署 | SOP | Checklist | 45 分 |
| 定期更新 | SOP §升級 | Quick Ref | 20 分 |
| 故障排查 | Troubleshooting | Quick Ref | 5-15 分 |
| 監控設定 | Monitoring | Checklist | 30 分 |
| 日常維護 | Quick Ref | 無 | < 5 分 |

---

## 🔐 安全提示

⚠️ 部署前必檢查:
- [ ] `.env` 中 `SECRET_KEY` 已改為隨機 32+ 字元
- [ ] `DEBUG=false` (生產環境)
- [ ] `DEFAULT_ADMIN_PASSWORD` 已改
- [ ] `CORS_ORIGINS` 不包含 `*`
- [ ] TLS/HTTPS 已啟用 (生產環境)
- [ ] 防火牆已設定 (Redis 6379 禁止外部訪問)

---

## 📞 問題與反饋

若文件有誤或遺漏:
1. 記錄具體位置 (文件名 + 行號 + 症狀)
2. 提交給維護團隊: `devops@company.com`
3. 文件會定期更新

---

## 📈 文件版本控制

```
文件版本: 1.0
生成日期: 2025-04-27
適用系統: Monitor System Part 2 (Celery + WebSocket)
Python 版本: 3.11+
Docker 版本: 20.10+
Docker Compose: 1.29+
```

---

## 🎓 建議閱讀順序

### For DevOps / 運維人員:

1. **README_DEPLOYMENT_DOCS.md** (5 分) — 了解文件體系
2. **DEPLOYMENT_SOP.md** 第 1-5 節 (30 分) — 完整流程
3. **DEPLOYMENT_CHECKLIST.md** (20 分) — 部署前檢查
4. **MONITORING_SETUP.md** (20 分) — 監控告警
5. **TROUBLESHOOTING_TREE.md** (10 分) — 故障排查
6. **QUICK_REFERENCE.md** (5 分) — 日常速查

### For 開發人員:

1. **README_DEPLOYMENT_DOCS.md** (5 分)
2. **DEPLOYMENT_SOP.md** 第 1-2 節 (15 分)
3. **QUICK_REFERENCE.md** (10 分)
4. **TROUBLESHOOTING_TREE.md** (10 分 - 瀏覽)

### For 產品 / 專案經理:

1. **README_DEPLOYMENT_DOCS.md** (5 分)
2. **DEPLOYMENT_CHECKLIST.md** 第 10 節 (簽核) (5 分)
3. **MONITORING_SETUP.md** 概述 (10 分 - 了解指標)

---

## 💾 備份與離線使用

所有文件均為 Markdown 格式,可:
- ✅ 用任何文字編輯器開啟
- ✅ 用 `pandoc` 轉換成 HTML / PDF / Word
- ✅ 上傳到 Wiki / Confluence / 內部知識庫
- ✅ 用 Markdown viewer 離線查看

```bash
# 轉換成 HTML
pandoc DEPLOYMENT_SOP.md -o deployment.html

# 轉換成 PDF (需要 pandoc + LaTeX)
pandoc DEPLOYMENT_SOP.md -o deployment.pdf

# 打包成單個檔案
tar czf deployment-docs-v1.0.tar.gz *.md
```

---

**最後更新**: 2025-04-27  
**文件版本**: 1.0  
**維護者**: DevOps Team

