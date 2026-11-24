# MinIO storage context — checkpoint 2026-10-15

Read this when changing document bucket configuration or applying SQL migration 011.

- Domain owner: knowledge-service. Ingestion reads raw files and writes knowledge chunks; review the ownership ADR before changing that data path.
- Docker Compose uses network `sopilot-network`, container `sopilot-minio`, endpoint `http://minio:9000`, console port 9001.
- Compose supplies document bucket `sopilot-documents` via `MINIO_BUCKET_NAME`. Java MinioConfig retains its legacy fallback `poliwise-documents` for executions without that environment variable; these are different configuration paths.
- Supply access/secret keys from environment; do not paste real credentials in commands, docs or commits.
- `infrastructure/init-db/011_document_bucket_default.sql` changes only the default for future document rows. It does not rewrite existing rows or move any object.
- New database bootstrap runs numbered SQL scripts in order. Existing databases need explicit application of pending additive scripts; container restart does not replay init scripts.
- Renaming database/user in Compose does not migrate an existing PostgreSQL volume. Check database identity and data first; do not reset a populated volume to make names match.

Before changing an existing bucket, inventory document row bucket references and object locations, propose a migration/rollback procedure, and verify on an isolated test database/storage. Never update old row references without moving and verifying their corresponding objects.

Checkpoint verification is recorded in `docs/archive/04-reports/HANDOFF-implementation-2026-10-15.md`; configuration validation is not proof that storage or ingestion ran successfully.
