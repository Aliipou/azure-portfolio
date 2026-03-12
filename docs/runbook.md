# On-Call Runbook

## Contacts

| Role | Contact |
|------|---------|
| Platform Owner | Ali Pourrahim |
| Azure Subscription | Beamex Azure Subscription |
| Pager | GitHub Metric Alert → email action group |

---

## Alerts

### Alert: High Anomaly Rate (>10%)

**Symptom**: `anomaly_rate_pct` exceeds 10% over a 1-hour window

**Possible causes**:
1. Batch of measurements from a malfunctioning device
2. Reference value configuration error (wrong standard)
3. Anomaly threshold set too low

**Investigation**:
```bash
# Check anomaly list
curl -H "Authorization: Bearer $TOKEN" \
  https://<fqdn>/api/v1/analytics/anomalies

# Query Log Analytics
az monitor log-analytics query \
  --workspace $LA_WORKSPACE_ID \
  --analytics-query "
    AppDependencies
    | where Name == 'process_measurement'
    | where Properties.is_anomaly == 'true'
    | summarize count() by Properties.device_id
    | order by count_ desc
  "
```

**Resolution**: If single device → quarantine device in registry (Admin role). If threshold issue → adjust `ANOMALY_THRESHOLD` env var via `az containerapp update`.

---

### Alert: Worker Queue Depth > 1000

**Symptom**: Service Bus queue depth exceeds 1000 messages

**Possible causes**:
1. Worker scaled to zero and KEDA trigger delay
2. Worker crash-looping (check dead-letter queue)
3. Database connection exhausted

**Investigation**:
```bash
# Check worker replica count
az containerapp show \
  --name ca-calibration-worker-prod \
  --resource-group rg-calibration-compute-prod \
  --query "properties.template.scale"

# Check dead-letter queue depth
az servicebus queue show \
  --name calibration-measurements \
  --namespace-name <namespace> \
  --resource-group rg-calibration-messaging-prod \
  --query "countDetails.deadLetterMessageCount"

# Force worker scale up
az containerapp update \
  --name ca-calibration-worker-prod \
  --resource-group rg-calibration-compute-prod \
  --min-replicas 2
```

---

### Alert: API 5xx Rate > 1%

**Symptom**: HTTP 500/502/503 responses exceed 1% over 5 minutes

**Investigation**:
```bash
# Check App Insights failures
az monitor app-insights query \
  --app <app-insights-name> \
  --resource-group rg-calibration-monitoring-prod \
  --analytics-query "
    requests
    | where resultCode >= 500
    | where timestamp > ago(30m)
    | summarize count() by resultCode, url
  "

# Check container logs
az containerapp logs show \
  --name ca-calibration-api-prod \
  --resource-group rg-calibration-compute-prod \
  --follow
```

---

## Deployments

### Standard Deployment

Push to `main` → CI runs → CD Deploy triggers automatically after CI succeeds.

### Emergency Rollback

```bash
# List recent revisions
az containerapp revision list \
  --name ca-calibration-api-prod \
  --resource-group rg-calibration-compute-prod \
  --query "[].{name:name, image:properties.template.containers[0].image, active:properties.active}"

# Rollback to specific revision
az containerapp update \
  --name ca-calibration-api-prod \
  --resource-group rg-calibration-compute-prod \
  --image <registry>/calibration-api:<previous-sha>
```

### Run Database Migration

```bash
# One-off migration job via az containerapp exec
az containerapp exec \
  --name ca-calibration-api-prod \
  --resource-group rg-calibration-compute-prod \
  --command "alembic upgrade head"
```

---

## Dead-Letter Queue Processing

Messages land in the dead-letter queue after 3 failed processing attempts.

```bash
# List dead-letter messages (requires Service Bus Explorer or SDK)
# Reprocess a specific measurement manually:
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"measurement_id": "<id>"}' \
  https://<fqdn>/api/v1/measurements/<id>/reprocess
```

---

## Database Operations

### Connect to PostgreSQL

```bash
# Via Azure CLI (uses AAD token — no password needed)
az postgres flexible-server connect \
  --name pg-calibration-prod \
  --admin-user $MI_CLIENT_ID \
  --database-name calibration_db
```

### Check Table Sizes

```sql
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```
