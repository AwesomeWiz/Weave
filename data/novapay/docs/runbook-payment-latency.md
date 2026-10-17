# Runbook: Payment Service Latency & Degradation

**Document ID:** doc:runbook-payment-latency
**Version:** 1.2
**Last Updated:** 2026-05-22
**Target Service:** service:payment-service
**Related Incident:** incident:INC-17
**Architecture Reference:** doc:ADR-7

## 1. Trigger Conditions

Alert `PaymentServiceP99LatencyHigh` fires when p99 API response latency exceeds 250ms for 3 consecutive minutes, or when HTTP 504 Gateway Timeout responses surpass 1% of total transaction volume.

## 2. Diagnostic Steps

1. **Verify Redis Cache Cluster Health**:
   - Check Redis cluster CPU utilization and memory fragmentation via Grafana dashboard `Redis / Payments Cache`.
   - Verify cache-hit ratio is maintained above 80% (target nominal: 87%).
   - If cache-hit ratio drops below 50%, inspect Payment Service logs for Redis connection pool exhaustion or network partition.

2. **Check Database Query Queue**:
   - Query pg_stat_activity on PostgreSQL primary to identify lock contention on transaction tables.
   - If Redis is healthy, database read pressure should remain below 40% of peak capacity.

3. **Cache Invalidation & Failover**:
   - In the event of primary Redis instance failure, the sentinel automatically promotes the replica within 15 seconds.
   - Payment Service falls back to direct PostgreSQL reads if Redis is completely unreachable, operating in degraded mode.
