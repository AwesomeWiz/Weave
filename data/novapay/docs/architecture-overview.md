# NovaPay Core Architecture Overview

**Document ID:** doc:architecture-overview
**Version:** 2.4
**Last Updated:** 2026-05-01
**Author:** Platform & Architecture Working Group
**Target Service:** service:payment-service

## 1. System Overview

NovaPay provides a distributed transaction processing platform designed for high-availability payment routing, card authorization, and merchant settlement.

### Core Components

- **Checkout Service (`service:checkout-service`)**: Customer-facing web checkout orchestration layer.
- **Payment Service (`service:payment-service`)**: Core transaction authorization and processing backend.
- **Database Layer**: Primary PostgreSQL cluster serving relational transaction records and merchant account configurations.

## 2. Transaction Flow & Data Access

1. Checkout Service submits payment requests to Payment Service over internal gRPC/REST APIs.
2. Payment Service validates transaction requests against merchant configuration tables in PostgreSQL.
3. Idempotency keys are queried directly from the `payment_idempotency_records` table in PostgreSQL before gateway dispatch.
4. Successful authorizations are committed to PostgreSQL, and status receipts are returned downstream to Checkout Service.

## 3. Storage and Scaling Constraints

All configuration reads, merchant rules, and idempotency lookups are executed as synchronous queries against the PostgreSQL primary database. Under elevated traffic surges, database connection pools must be scaled vertically to avoid queue saturation.
