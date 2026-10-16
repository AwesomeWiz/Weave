# Handoff: Data → Frontend/Demo (Arnold)

## Expected Redis Decision Chain

The ground-truth evidence path for "Why does Payment Service use Redis?":

```
incident:INC-17  "Payment requests timing out during peak traffic"
       │ LED_TO
       ▼
issue:PAY-42  "Reduce payment latency under burst traffic"
       │ SUPPORTED_BY (reverse)
       ▼
decision:D-007  "Introduce Redis caching"  (status: accepted)
       │
       ├── AFFECTS → service:payment-service
       ├── INTRODUCES → tech:redis
       ├── SUPPORTED_BY → issue:PAY-42
       ├── SUPPORTED_BY → message:payment-perf-7
       ├── IMPLEMENTED_BY → commit:8fae2
       ├── DOCUMENTED_IN → doc:ADR-7
       ├── PARTICIPATED_IN ← person:alice, person:ravi, person:maya
       └── APPROVED ← person:alice

commit:8fae2  →  BELONGS_TO  →  repo:novapay/payments-api
                                       │ IMPLEMENTS
                                       ▼
                               service:payment-service  ←  USES  ←  tech:redis
                                       │
                                 DEPENDS_ON (reverse)
                                       │
                               service:checkout-service
```

## Key entities for evidence display

| ID                        | Label                        | Type       |
|--------------------------|------------------------------|------------|
| `incident:INC-17`        | Payment requests timing out  | Incident   |
| `issue:PAY-42`           | Reduce payment latency       | Issue      |
| `message:payment-perf-7` | Payment perf discussion      | Message    |
| `decision:D-007`         | Introduce Redis caching      | Decision   |
| `commit:8fae2`           | Redis cache implementation   | Commit     |
| `doc:ADR-7`              | ADR-7                        | Document   |
| `service:payment-service`| Payment Service              | Service    |
| `tech:redis`             | Redis                        | Technology |
| `person:alice`           | Alice Menon (approver)       | Person     |

## Timeline for freshness demo

- Architecture Overview: May 1 → stale candidate
- INC-17: May 10
- PAY-42: May 11
- Discussion: May 15
- D-007 accepted: May 18
- Commit: May 19
- ADR-7 updated: May 20 → current

## Causality demo edge

`service:checkout-service -[:DEPENDS_ON]-> service:payment-service`

Remove this edge → impact analysis result changes. Re-seed to restore.
