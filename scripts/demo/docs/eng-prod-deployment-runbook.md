# SOP-ENG-01: Production Deployment & Rollback Runbook

- **Document Code:** `SOP-ENG-01`
- **Revision:** `2.1`
- **Effective Date:** `2026-10-01`
- **Owner Department:** Engineering (`Kỹ thuật`)
- **Audience:** Engineering team members only (restricted)

## 1. Purpose

This procedure defines the mandatory deployment checklist, approval chain, and rollback SLA for all production releases of SOPilot services.

## 2. Deployment Window & Approvals

1. Standard production releases are permitted **Tuesday to Thursday, 09:00–16:00 ICT**.
2. Friday deployments are prohibited unless approved in writing by the **VP of Engineering** as an emergency hotfix (`SEV-1`).
3. Every release requires:
   - Green CI pipeline (`build`, `unit`, `tenant-isolation`).
   - At least **2 peer approvals** from Senior Engineers in the Engineering department.
   - Change ticket linked to a verified staging smoke run.

## 3. Rollback SLA & Trigger Conditions

An immediate rollback **must** be executed within **15 minutes** if any of the following occur after release:

- HTTP `5xx` error rate exceeds **1.0%** over a 5-minute window.
- P95 API latency exceeds **2,500 ms** for 5 consecutive minutes.
- Any cross-tenant data access anomaly is detected in security telemetry.

## 4. Rollback Command & Escalation

1. Run `kubectl rollout undo deployment/<service>` or revert the release tag in the deployment controller.
2. Notify the `#eng-incidents` channel within **5 minutes** of initiating rollback.
3. File a blameless post-mortem within **48 hours** of service restoration.
