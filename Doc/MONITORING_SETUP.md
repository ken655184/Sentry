# Monitor System — 監控告警設定 (Prometheus + AlertManager)

## 📊 概述

本文件提供 Prometheus 和 AlertManager 的設定範本,用於監控 Monitor System 的:
- API 可用性與響應時間
- Celery worker 狀態
- Redis 記憶體與連線
- SQLite 鎖定事件
- WebSocket 連線數量

---

## 1️⃣ Prometheus 設定

### 1.1 `prometheus.yml`

```yaml
global:
  scrape_interval: 30s       # 每 30 秒抓一次指標
  evaluation_interval: 30s   # 每 30 秒評估告警規則
  external_labels:
    monitor: 'monitor-system'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - '/etc/prometheus/rules/*.yml'

scrape_configs:
  # ── Monitor System API ────────────────────────────────────────
  - job_name: 'monitor-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
    scrape_timeout: 10s
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance

  # ── Redis (需要 redis_exporter) ───────────────────────────────
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:6379']
    metrics_path: '/metrics'
    scrape_interval: 15s

  # ── Node Exporter (機器指標:CPU、記憶體、磁碟) ─────────────────
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 30s

  # ── cAdvisor (Docker 容器指標,可選) ──────────────────────────
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### 1.2 啟動 Prometheus

```bash
# Docker 方式(推薦)
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v /opt/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v /opt/prometheus/rules:/etc/prometheus/rules \
  -v prometheus_data:/prometheus \
  prom/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=30d

# 訪問: http://localhost:9090
```

---

## 2️⃣ 告警規則

### 2.1 `monitor-system-alerts.yml`

建立檔案 `/opt/prometheus/rules/monitor-system-alerts.yml`:

```yaml
groups:
  - name: monitor_system_alerts
    interval: 30s
    rules:

      # ── API 告警 ──────────────────────────────────────────────

      - alert: MonitorAPIDown
        expr: up{job="monitor-api"} == 0
        for: 2m
        labels:
          severity: critical
          service: api
        annotations:
          summary: "Monitor API 無回應"
          description: "API at {{ $labels.instance }} 已離線超過 2 分鐘"
          runbook: "https://wiki.company.com/monitor/api-down"

      - alert: MonitorAPIHighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1.0
        for: 5m
        labels:
          severity: warning
          service: api
        annotations:
          summary: "API 響應時間過長"
          description: "99% 請求耗時 > 1s (現在: {{ $value | humanizeDuration }})"

      - alert: MonitorAPIHighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
          service: api
        annotations:
          summary: "API 錯誤率過高"
          description: "5xx 錯誤比例 > 5% (現在: {{ $value | humanizePercentage }})"

      # ── WebSocket 告警 ───────────────────────────────────────

      - alert: WebSocketConnectionDrop
        expr: rate(monitor_ws_active_connections[5m]) < -1
        for: 2m
        labels:
          severity: warning
          service: websocket
        annotations:
          summary: "WebSocket 連線大量斷開"
          description: "短時間內連線數下降,可能有客戶端問題"

      # ── Celery Task 告警 ──────────────────────────────────────

      - alert: CeleryTaskQueueTooLong
        expr: celery_queue_length > 1000
        for: 10m
        labels:
          severity: warning
          service: celery
        annotations:
          summary: "Celery 隊列堆積"
          description: "待執行 task > 1000 個 (現在: {{ $value }})"
          action: "檢查 worker 是否卡住;若是,重啟 worker"

      - alert: CeleryWorkerDown
        expr: count(rate(celery_task_total[5m])) < 3
        for: 5m
        labels:
          severity: critical
          service: celery
        annotations:
          summary: "Celery Worker 可能宕機"
          description: "活躍 worker 數量異常,可能低於預期"
          action: "執行: docker-compose ps worker-*"

      - alert: CeleryTaskFailureRate
        expr: rate(celery_task_total{state="failure"}[5m]) / rate(celery_task_total[5m]) > 0.1
        for: 10m
        labels:
          severity: warning
          service: celery
        annotations:
          summary: "Task 失敗率過高"
          description: "失敗 task 比例 > 10% (現在: {{ $value | humanizePercentage }})"

      # ── Redis 告警 ────────────────────────────────────────────

      - alert: RedisMemoryAlmostFull
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.9
        for: 5m
        labels:
          severity: warning
          service: redis
        annotations:
          summary: "Redis 記憶體使用率過高"
          description: "記憶體已用 > 90% (現在: {{ $value | humanizePercentage }})"
          action: "檢查 CELERY_RESULT_BACKEND 是否洩漏;執行: redis-cli FLUSHDB"

      - alert: RedisConnectionsFull
        expr: redis_connected_clients / redis_config_maxclients > 0.8
        for: 5m
        labels:
          severity: warning
          service: redis
        annotations:
          summary: "Redis 連線數接近上限"
          description: "已連線 > 80% 最大連線 (現在: {{ $value | humanizePercentage }})"

      - alert: RedisKeyspaceAlmostFull
        expr: redis_db_avg_ttl_seconds < 3600
        for: 10m
        labels:
          severity: info
          service: redis
        annotations:
          summary: "Redis 鍵即將過期"
          description: "平均 TTL < 1 小時,可能大量鍵在短期內過期"

      # ── 磁碟和系統告警 ────────────────────────────────────────

      - alert: DiskSpaceLowOnDataPartition
        expr: node_filesystem_avail_bytes{mountpoint="/data"} / node_filesystem_size_bytes{mountpoint="/data"} < 0.1
        for: 10m
        labels:
          severity: warning
          service: system
        annotations:
          summary: "/data 分區空間不足"
          description: "可用空間 < 10% (現在: {{ $value | humanizePercentage }})"
          action: "清理舊檔案或擴容"

      - alert: DiskSpaceFillingFast
        expr: rate(node_filesystem_size_bytes - node_filesystem_avail_bytes[1h]) > 104857600
        for: 30m
        labels:
          severity: warning
          service: system
        annotations:
          summary: "磁碟空間填充速度過快"
          description: "1 小時內磁碟占用增加 > 100MB/min"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.85
        for: 5m
        labels:
          severity: warning
          service: system
        annotations:
          summary: "機器記憶體使用率過高"
          description: "可用記憶體 < 15% (現在: {{ $value | humanizePercentage }})"

      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
          service: system
        annotations:
          summary: "CPU 使用率過高"
          description: "平均 CPU 使用率 > 80% (現在: {{ $value | humanize }}%)"

      # ── 資料庫告警 ────────────────────────────────────────────

      - alert: SQLiteDatabaseLocked
        expr: increase(sqlite_lock_timeout_errors_total[5m]) > 5
        for: 5m
        labels:
          severity: warning
          service: database
        annotations:
          summary: "SQLite 資料庫頻繁鎖定"
          description: "5 分鐘內鎖定錯誤 > 5 次"
          action: "考慮遷移到 PostgreSQL;見 SOP §7.2"

      # ── 自訂業務告警 ──────────────────────────────────────────

      - alert: AuditLogWriteFailure
        expr: increase(audit_write_errors_total[10m]) > 10
        for: 5m
        labels:
          severity: warning
          service: audit
        annotations:
          summary: "稽核紀錄寫入失敗"
          description: "10 分鐘內寫入失敗 > 10 次"
          action: "檢查資料庫連線和磁碟空間"
```

### 2.2 啟動告警規則

```bash
# 檢查規則語法
docker run -it --rm \
  -v /opt/prometheus/rules:/etc/prometheus/rules \
  prom/prometheus \
  promtool check rules /etc/prometheus/rules/monitor-system-alerts.yml

# Prometheus 容器會自動熱載入規則(無需重啟)
```

---

## 3️⃣ AlertManager 設定

### 3.1 `alertmanager.yml`

建立檔案 `/opt/alertmanager/config.yml`:

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'

# 告警路由樹 (routing tree)
route:
  # 根路由:所有告警先來這裡
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s         # 等 10s 彙整同類告警再發送
  group_interval: 10m     # 同類告警 10min 才重發一次
  repeat_interval: 4h     # 未解決的告警 4h 提醒一次

  # 子路由:分流不同告警到不同接收方
  routes:
    # ── 關鍵告警 → Slack + PagerDuty ─────────────────────────
    - match:
        severity: critical
      receiver: 'critical-alert'
      group_wait: 0s       # 立即發送,不等待
      continue: true       # 同時匹配下面的規則

    # ── 警告告警 → Slack only ────────────────────────────────
    - match:
        severity: warning
      receiver: 'warning-alert'
      group_wait: 30s

    # ── API 相關告警 → 發給開發團隊 ──────────────────────────
    - match:
        service: api
      receiver: 'dev-team'

    # ── 基礎設施告警 → 發給運維團隊 ──────────────────────────
    - match:
        service: 'system'
      receiver: 'ops-team'

# 抑制規則 (inhibition rules)
# 若下列條件滿足,則抑制(隱藏)該告警
inhibit_rules:
  # 若 API Down,則隱藏 High Latency 告警(因為原因已知)
  - source_match:
      alertname: 'MonitorAPIDown'
    target_match:
      alertname: 'MonitorAPIHighLatency'
    equal: ['instance']

  # 若有磁碟滿告警,則隱藏"填充速度快"告警
  - source_match:
      alertname: 'DiskSpaceLowOnDataPartition'
    target_match:
      alertname: 'DiskSpaceFillingFast'

# 接收方定義 (receivers)
receivers:
  - name: 'default'
    slack_configs:
      - channel: '#monitor-alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        color: '{{ if eq .Status "firing" }}danger{{ else }}good{{ end }}'

  - name: 'critical-alert'
    slack_configs:
      - channel: '@oncall'   # 直接 @ 當值人員
        title: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ .Annotations.action }}\n{{ end }}'
        color: 'danger'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY'
        description: '{{ .GroupLabels.alertname }}'

  - name: 'warning-alert'
    slack_configs:
      - channel: '#monitor-alerts'
        title: '⚠️  WARNING: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
        color: 'warning'

  - name: 'dev-team'
    slack_configs:
      - channel: '#dev-team'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}\nRunbook: {{ .Annotations.runbook }}{{ end }}'

  - name: 'ops-team'
    slack_configs:
      - channel: '#ops-team'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}\nAction: {{ .Annotations.action }}{{ end }}'

# 郵件通知(可選)
    email_configs:
      - to: 'ops@company.com'
        from: 'alertmanager@company.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alerts@company.com'
        auth_password: 'APP_PASSWORD'
        headers:
          Subject: '{{ .GroupLabels.alertname }}'

# Webhook (自訂整合,例如自動修復腳本)
    webhook_configs:
      - url: 'http://localhost:5001/alert-webhook'
        send_resolved: true
```

### 3.2 啟動 AlertManager

```bash
docker run -d \
  --name alertmanager \
  -p 9093:9093 \
  -v /opt/alertmanager/config.yml:/etc/alertmanager/config.yml \
  -v alertmanager_data:/alertmanager \
  prom/alertmanager \
  --config.file=/etc/alertmanager/config.yml \
  --storage.path=/alertmanager

# 訪問: http://localhost:9093
```

---

## 4️⃣ Docker Compose 整合

新增監控 stack 到 `docker-compose.yml`:

```yaml
version: "3.9"

services:
  # ... 原有的 api, redis, workers ...

  # ── Prometheus ───────────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./rules:/etc/prometheus/rules
      - prometheus_data:/prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=30d
    depends_on:
      - api
    profiles:
      - monitoring

  # ── AlertManager ─────────────────────────────────────────
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/config.yml
      - alertmanager_data:/alertmanager
    command:
      - --config.file=/etc/alertmanager/config.yml
      - --storage.path=/alertmanager
    depends_on:
      - prometheus
    profiles:
      - monitoring

  # ── Grafana (可視化,可選) ───────────────────────────────
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: 'admin'
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    profiles:
      - monitoring

  # ── Redis Exporter (Redis 指標) ──────────────────────────
  redis-exporter:
    image: oliver006/redis_exporter:latest
    ports:
      - "9121:9121"
    command: -redis-addr=redis:6379
    depends_on:
      - redis
    profiles:
      - monitoring

  # ── Node Exporter (系統指標) ──────────────────────────────
  node-exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - --path.procfs=/host/proc
      - --path.rootfs=/rootfs
      - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
    profiles:
      - monitoring

volumes:
  prometheus_data:
  alertmanager_data:
  grafana_data:
```

### 4.3 啟動監控 stack

```bash
# 啟用監控(包含 Prometheus, AlertManager, Grafana)
docker-compose --profile monitoring up -d

# 檢查狀態
docker-compose ps

# 訪問
# - Prometheus: http://localhost:9090
# - AlertManager: http://localhost:9093
# - Grafana: http://localhost:3000 (admin / admin)
```

---

## 5️⃣ Grafana 儀表板設定

### 5.1 新增資料來源

1. 登入 Grafana (http://localhost:3000)
2. 左側菜單 → Configuration → Data Sources
3. 新增:
   - **Name**: Prometheus
   - **Type**: Prometheus
   - **URL**: http://prometheus:9090
   - **Save & Test**

### 5.2 匯入現成 Dashboard

Grafana 已有許多現成的 dashboard,可直接匯入:

```bash
# 匯入 Prometheus 官方 dashboard (ID: 1860)
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Authorization: Bearer $TOKEN" \
  -d @- << 'EOF'
{
  "dashboard": {
    "title": "Node Exporter Full",
    "uid": "rYdddlPWz"
  },
  "overwrite": true
}
EOF
```

或手動匯入(於 Grafana UI):
- 左側 + 按鈕 → Import
- 輸入 Dashboard ID (例: `1860` / `6417` / `3662`)
- 選擇 Prometheus 資料來源 → Import

### 5.3 客製化 Dashboard

建議新增的面板:

```
行 1: API 狀態
  ├─ API Response Time (99th percentile)
  ├─ Request Rate (req/s)
  └─ Error Rate (%)

行 2: Celery Worker
  ├─ Active Tasks
  ├─ Queue Depth
  └─ Task Success Rate (%)

行 3: 資源使用
  ├─ CPU Usage (%)
  ├─ Memory Usage (%)
  └─ Disk Free (GB)

行 4: Redis
  ├─ Memory Used (MB)
  ├─ Connected Clients
  └─ Commands/sec
```

---

## 6️⃣ 告警通知設定

### 6.1 Slack 整合

1. 建立 Slack Webhook:
   - 進入 Slack Workspace → Settings → Apps
   - 搜尋 **Incoming Webhooks** → Add
   - 選擇頻道(例: `#monitor-alerts`)
   - 複製 Webhook URL

2. 更新 `alertmanager.yml`:
   ```yaml
   global:
     slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
   ```

3. 測試:
   ```bash
   docker-compose exec alertmanager \
     amtool alert add TestAlert severity=warning
   # 應該在 Slack 看到通知
   ```

### 6.2 PagerDuty 整合(可選)

1. 在 PagerDuty 建立 Service
2. 複製 **Integration Key**
3. 更新 `alertmanager.yml`:
   ```yaml
   pagerduty_configs:
     - service_key: 'YOUR_SERVICE_KEY'
   ```

### 6.3 郵件告警(可選)

更新 `alertmanager.yml`:

```yaml
email_configs:
  - to: 'ops@company.com'
    from: 'alertmanager@company.com'
    smarthost: 'smtp.gmail.com:587'
    auth_username: 'alerts@company.com'
    auth_password: 'YOUR_APP_PASSWORD'
```

---

## 7️⃣ 監控最佳實踐

### ✅ DO

- [ ] 設定多個通知渠道(Slack + 郵件 + PagerDuty)
- [ ] 定期檢查告警的準確性(減少誤報)
- [ ] 為每個告警編寫 runbook(例: 如何修復)
- [ ] 監控自身(Prometheus HA 設定,見下)
- [ ] 定期清理舊指標資料(TSDB 成長控制)

### ❌ DON'T

- [ ] 不要所有告警都設 critical(會導致警報疲勞)
- [ ] 不要將告警直接 CC 給太多人
- [ ] 不要使用過長的 group_wait(會延遲關鍵告警)
- [ ] 不要在告警規則中硬編碼 webhook URL(用 AlertManager 的 global)

---

## 8️⃣ Prometheus HA 設定(高級)

若需要 Prometheus 高可用,使用多個實例 + Alertmanager cluster:

```yaml
# prometheus-1.yml
global:
  external_labels:
    prometheus: 'prometheus-1'
    replica: '1'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - 'alertmanager-1:9093'
          - 'alertmanager-2:9093'

# prometheus-2.yml
global:
  external_labels:
    prometheus: 'prometheus-1'
    replica: '2'
```

再用 PushGateway + Thanos 做長期儲存(見 Prometheus 官方文件)。

---

## 9️⃣ 常見問題

### Q: 告警規則沒有觸發?
```bash
# 檢查 Prometheus 有沒有採集到指標
curl http://localhost:9090/api/v1/query?query=up

# 檢查規則有沒有語法錯誤
docker-compose exec prometheus \
  promtool check rules /etc/prometheus/rules/monitor-system-alerts.yml
```

### Q: AlertManager 沒有發送 Slack 訊息?
```bash
# 檢查 Slack Webhook URL 是否正確
curl -X POST https://hooks.slack.com/services/YOUR/URL \
  -d '{"text":"Test message"}'

# 檢查 AlertManager 日誌
docker-compose logs alertmanager | grep -i slack
```

### Q: Grafana 無法連接 Prometheus?
```bash
# 檢查 Prometheus 是否運行
curl http://prometheus:9090/-/healthy

# 檢查網路連通性
docker-compose exec grafana curl http://prometheus:9090/graph
```

---

**版本**: 1.0  
**最後更新**: 2025-04-27

