"""V2-08: verify production infrastructure sources in a disposable tmpfs project.

No .env is loaded, no host ports or named volumes are created. Credentials exist
only in the child environment. Never run this against a user's existing project.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

PROBE_SQL = r"""
\set ON_ERROR_STOP on
BEGIN;
SET ROLE sopilot_migrator;
CREATE TABLE core.readiness_probe (workspace_id uuid NOT NULL);
ALTER TABLE core.readiness_probe ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.readiness_probe FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON core.readiness_probe
  USING (workspace_id = core.current_workspace())
  WITH CHECK (workspace_id = core.current_workspace());
CREATE FUNCTION core.readiness_private() RETURNS int LANGUAGE sql AS 'SELECT 1';
CREATE TABLE rag.readiness_probe (workspace_id uuid NOT NULL);
ALTER TABLE rag.readiness_probe ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.readiness_probe FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON rag.readiness_probe
  USING (workspace_id = rag.current_workspace())
  WITH CHECK (workspace_id = rag.current_workspace());
CREATE FUNCTION rag.readiness_private() RETURNS int LANGUAGE sql AS 'SELECT 1';
RESET ROLE;
INSERT INTO core.readiness_probe VALUES
 ('00000000-0000-0000-0000-000000000001'),
 ('00000000-0000-0000-0000-000000000002');
INSERT INTO rag.readiness_probe VALUES
 ('00000000-0000-0000-0000-000000000001'),
 ('00000000-0000-0000-0000-000000000002');
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN
   ('sopilot_migrator','sopilot_core_app','sopilot_ai_app') AND (rolsuper OR rolbypassrls))
 THEN RAISE EXCEPTION 'unsafe application/migrator role'; END IF;
 IF has_schema_privilege('sopilot_ai_app','core','USAGE') OR
    has_schema_privilege('sopilot_core_app','rag','USAGE') OR
    has_schema_privilege('sopilot_core_app','core','CREATE') OR
    has_schema_privilege('sopilot_ai_app','rag','CREATE')
 THEN RAISE EXCEPTION 'schema isolation failure'; END IF;
 IF has_function_privilege('sopilot_core_app','core.readiness_private()','EXECUTE') OR
    has_function_privilege('sopilot_ai_app','rag.readiness_private()','EXECUTE')
 THEN RAISE EXCEPTION 'new functions are executable without explicit grant'; END IF;
END $$;
SET ROLE sopilot_core_app;
DO $$ BEGIN
 IF (SELECT count(*) FROM core.readiness_probe) <> 0
 THEN RAISE EXCEPTION 'unset tenant did not fail closed'; END IF;
END $$;
SELECT set_config('app.workspace_id','00000000-0000-0000-0000-000000000001',true);
DO $$ BEGIN
 IF (SELECT count(*) FROM core.readiness_probe) <> 1
 THEN RAISE EXCEPTION 'tenant filtering failure'; END IF;
 BEGIN
  INSERT INTO core.readiness_probe VALUES ('00000000-0000-0000-0000-000000000002');
  RAISE EXCEPTION 'cross-tenant insert unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
RESET ROLE;
SELECT set_config('app.workspace_id','',true);
SET ROLE sopilot_ai_app;
DO $$ BEGIN
 IF (SELECT count(*) FROM rag.readiness_probe) <> 0
 THEN RAISE EXCEPTION 'unset AI tenant did not fail closed'; END IF;
END $$;
SELECT set_config('app.workspace_id','00000000-0000-0000-0000-000000000002',true);
DO $$ BEGIN
 IF (SELECT count(*) FROM rag.readiness_probe) <> 1
 THEN RAISE EXCEPTION 'AI tenant filtering failure'; END IF;
 BEGIN
  INSERT INTO rag.readiness_probe VALUES ('00000000-0000-0000-0000-000000000001');
  RAISE EXCEPTION 'AI cross-tenant insert unexpectedly succeeded';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
RESET ROLE;
ROLLBACK;
SELECT version FROM core.flyway_schema_history WHERE success;
SELECT version FROM rag.flyway_schema_history WHERE success;
"""


def disposable_config(source: dict, project: str, directory: Path) -> dict:
    """Retain source images/commands/env, replace only storage/host integration."""
    model = json.loads(json.dumps(source))
    model["name"] = project
    model.pop("volumes", None)
    model["networks"] = {"sopilot-v2": {}}
    for name, service in model["services"].items():
        service.pop("container_name", None)
        service.pop("ports", None)
        service.pop("volumes", None)
        if name == "postgres":
            service["tmpfs"] = ["/var/lib/postgresql/data"]
            service["volumes"] = [
                f"{(directory / 'init').as_posix()}:/docker-entrypoint-initdb.d:ro"
            ]
        elif name == "minio":
            service["tmpfs"] = ["/data"]
        elif name == "minio-init":
            # The shared MinIO image declares VOLUME /data even for this one-shot.
            service["tmpfs"] = ["/data"]
            service["volumes"] = [f"{(directory / 'storage').as_posix()}:/init:ro"]
        elif name.startswith("flyway-"):
            schema = name.removeprefix("flyway-")
            service["volumes"] = [
                f"{(ROOT / 'infrastructure/db/migrations' / schema).as_posix()}:/flyway/sql:ro"
            ]
    return model


def verify() -> dict:
    project = "sopilot-v2-readiness-" + uuid.uuid4().hex[:8]
    directory = ROOT / "eval/.cache" / project
    directory.mkdir(parents=True)
    for src, dest in [
        ("infrastructure/db/init/01-roles.sh", "init/01-roles.sh"),
        ("infrastructure/storage/minio-init.sh", "storage/minio-init.sh"),
    ]:
        target = directory / dest
        target.parent.mkdir(exist_ok=True)
        target.write_text(
            (ROOT / src).read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
        )
    env_file = directory / "empty.env"
    env_file.write_text("", encoding="utf-8")
    compose = directory / "compose.json"
    source = yaml.safe_load(
        (ROOT / "docker-compose.v2.yml").read_text(encoding="utf-8")
    )
    compose.write_text(
        json.dumps(disposable_config(source, project, directory)), encoding="utf-8"
    )
    env = os.environ.copy()
    for key in (
        "V2_POSTGRES_SUPERUSER_PASSWORD",
        "V2_DB_MIGRATOR_PASSWORD",
        "V2_DB_CORE_APP_PASSWORD",
        "V2_DB_AI_APP_PASSWORD",
        "V2_MINIO_ROOT_PASSWORD",
        "SOPILOT_S3_SECRET_KEY",
        "SOPILOT_S3_AI_SECRET_KEY",
    ):
        env[key] = secrets.token_urlsafe(24)
    env.update(
        V2_MINIO_ROOT_USER="readiness-root",
        SOPILOT_S3_ACCESS_KEY="readiness-core",
        SOPILOT_S3_AI_ACCESS_KEY="readiness-ai",
        SOPILOT_S3_BUCKET="readiness-documents",
    )
    base = [
        "docker",
        "compose",
        "--env-file",
        str(env_file),
        "-p",
        project,
        "-f",
        str(compose),
    ]

    def call(args: list[str], input_text: str | None = None) -> str:
        result = subprocess.run(
            args,
            input=input_text,
            text=True,
            capture_output=True,
            env=env,
            timeout=180,
            check=False,
        )
        if result.returncode:
            # Container setup output may contain credentials. Keep it out of logs.
            detail = (
                result.stderr[-1200:]
                if input_text == PROBE_SQL or ("run" in args and "minio-init" in args)
                else "output suppressed"
            )
            for key, value in env.items():
                if key in {
                    "V2_POSTGRES_SUPERUSER_PASSWORD",
                    "V2_DB_MIGRATOR_PASSWORD",
                    "V2_DB_CORE_APP_PASSWORD",
                    "V2_DB_AI_APP_PASSWORD",
                    "V2_MINIO_ROOT_PASSWORD",
                    "SOPILOT_S3_SECRET_KEY",
                    "SOPILOT_S3_AI_SECRET_KEY",
                }:
                    detail = detail.replace(value, "[redacted]")
            raise RuntimeError(
                f"infrastructure check failed (exit {result.returncode}): {detail}"
            )
        return result.stdout

    try:
        # Render the unmodified production Compose with disposable credentials.
        # Keep the result in memory: it contains interpolated test credentials.
        production = json.loads(
            call(
                [
                    "docker",
                    "compose",
                    "--env-file",
                    str(env_file),
                    "-f",
                    str(ROOT / "docker-compose.v2.yml"),
                    "config",
                    "--format",
                    "json",
                ]
            )
        )
        planned_volumes = production["volumes"]
        if production["name"] != "sopilot-v2" or any(
            entry.get("external") or not entry["name"].startswith("sopilot-v2_")
            for entry in planned_volumes.values()
        ):
            raise RuntimeError("production V2 volumes are not isolated")
        if (
            production["networks"]["sopilot-v2"].get("external")
            or production["networks"]["sopilot-v2"]["name"] != "sopilot-v2-network"
        ):
            raise RuntimeError("production V2 network is not isolated")
        for name, key in (("postgres", "postgres_data"), ("minio", "minio_data")):
            data_mounts = [
                m
                for m in production["services"][name]["volumes"]
                if m["type"] == "volume"
            ]
            if len(data_mounts) != 1 or data_mounts[0]["source"] != key:
                raise RuntimeError("production service uses an unexpected data volume")
        for service in production["services"].values():
            if any(p.get("host_ip") != "127.0.0.1" for p in service.get("ports", [])):
                raise RuntimeError(
                    "production infrastructure port is not loopback-only"
                )
        call(base + ["up", "-d"])
        for name in ("flyway-core", "flyway-rag", "minio-init"):
            container = call(base + ["ps", "-aq", name]).strip()
            if call(["docker", "wait", container]).strip() != "0":
                detail = call(["docker", "logs", container])[-1400:]
                for key in (
                    "V2_POSTGRES_SUPERUSER_PASSWORD",
                    "V2_DB_MIGRATOR_PASSWORD",
                    "V2_DB_CORE_APP_PASSWORD",
                    "V2_DB_AI_APP_PASSWORD",
                    "V2_MINIO_ROOT_PASSWORD",
                    "SOPILOT_S3_SECRET_KEY",
                    "SOPILOT_S3_AI_SECRET_KEY",
                ):
                    detail = detail.replace(env[key], "[redacted]")
                raise RuntimeError(f"one-shot service failed: {name}: {detail}")
        call(
            base
            + ["exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "sopilot"],
            PROBE_SQL,
        )
        call(base + ["run", "--rm", "--no-deps", "minio-init"])
        ids = call(base + ["ps", "-aq"]).split()
        inspections = json.loads(call(["docker", "inspect", *ids]))
        if any(m["Type"] == "volume" for item in inspections for m in item["Mounts"]):
            raise RuntimeError(
                "disposable infrastructure unexpectedly mounted a named volume"
            )
        storage_check = r"""
set -eu
mc alias set core http://minio:9000 "$SOPILOT_S3_ACCESS_KEY" "$SOPILOT_S3_SECRET_KEY" >/dev/null
mc alias set ai http://minio:9000 "$SOPILOT_S3_AI_ACCESS_KEY" "$SOPILOT_S3_AI_SECRET_KEY" >/dev/null
echo readiness | mc pipe "core/$SOPILOT_S3_BUCKET/probe" >/dev/null
mc cat "ai/$SOPILOT_S3_BUCKET/probe" >/dev/null
if echo denied | mc pipe "ai/$SOPILOT_S3_BUCKET/forbidden" >/dev/null 2>&1; then exit 1; fi
if mc rm "ai/$SOPILOT_S3_BUCKET/probe" >/dev/null 2>&1; then exit 1; fi
mc rm "core/$SOPILOT_S3_BUCKET/probe" >/dev/null
"""
        call(
            base
            + [
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "/bin/sh",
                "minio-init",
                "-c",
                storage_check,
            ]
        )
        status = call(
            base
            + [
                "exec",
                "-T",
                "minio",
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "http://localhost:9000/readiness-documents/probe",
            ]
        ).strip()
        if status != "403":
            raise RuntimeError("anonymous object access must return 403")
        report = {
            "project": project,
            "passed": True,
            "storage": "tmpfs, no named volumes",
            "checks": [
                "production Compose volume/network isolation and loopback ports",
                "Flyway",
                "role/schema isolation",
                "RLS read/write",
                "explicit function grants",
                "core S3 write",
                "AI S3 read-only",
                "anonymous S3 denied",
                "MinIO initialization idempotent",
            ],
            "limit": "Persistent owner volumes and real .env intentionally not exercised",
        }
        (directory / "result.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        return report
    finally:
        call(base + ["down", "--remove-orphans"])


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    sys.stdout.write(json.dumps(verify(), indent=2) + "\n")


if __name__ == "__main__":
    main()
