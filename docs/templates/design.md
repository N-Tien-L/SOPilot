---
id: TECH-NNN # optional for new designs; existing TECH-V2-* ids are preserved
title: "<Subsystem> design"
status: draft # draft | approved | superseded | archived
created: YYYY-MM-DD
updated: YYYY-MM-DD
author: "Owner"
affected_services: [] # core-api | ai-service | web | infra | eval
affected_schemas: []  # core | rag
refs: [] # PRD / ADR paths, root-relative
---

# <Title>

> **Implementation status:** list which sections are implemented (ticket ids) and which are planned.
> Section numbers are stable once code cites them. Append new sections; never renumber.

## 1. Scope and responsibilities

## 2. Data model
Point to the migration files. Show only the shape that matters for the design.

## 3. Interfaces
Endpoints, events, callbacks. The endpoint table lives in the service README; link it.

## 4. Flows
Mermaid sequence diagrams for the non-obvious paths, including failure handling.

## 5. Security and tenancy
How `workspace_id` is bound (`TenantTx` / `tenant_tx`) and filtered; what returns 404.

## 6. Configuration
Settings and where they are declared (`config/models.yaml`, `.env.example`).

## 7. Testing
Which suites prove the design (unit, integration, tenant isolation, eval).
