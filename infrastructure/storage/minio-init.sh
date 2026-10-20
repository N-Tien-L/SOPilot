#!/bin/sh
# One-shot MinIO setup for V2: one bucket, a read/write user for core-api and a
# read-only user for ai-service (TECH-V2-core-api §8.3). Idempotent.
set -eu

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc mb --ignore-existing "local/$SOPILOT_S3_BUCKET"
mc anonymous set none "local/$SOPILOT_S3_BUCKET"

policy_dir=$(mktemp -d)
cat > "$policy_dir/core-rw.json" <<EOF
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["s3:ListBucket","s3:GetBucketLocation"],"Resource":["arn:aws:s3:::$SOPILOT_S3_BUCKET"]},
  {"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject"],"Resource":["arn:aws:s3:::$SOPILOT_S3_BUCKET/*"]}
]}
EOF
cat > "$policy_dir/ai-ro.json" <<EOF
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["s3:GetObject"],"Resource":["arn:aws:s3:::$SOPILOT_S3_BUCKET/*"]}
]}
EOF

mc admin policy create local sopilot-core-rw "$policy_dir/core-rw.json"
mc admin policy create local sopilot-ai-ro "$policy_dir/ai-ro.json"
mc admin user add local "$SOPILOT_S3_ACCESS_KEY" "$SOPILOT_S3_SECRET_KEY"
mc admin user add local "$SOPILOT_S3_AI_ACCESS_KEY" "$SOPILOT_S3_AI_SECRET_KEY"
mc admin policy attach local sopilot-core-rw --user "$SOPILOT_S3_ACCESS_KEY" || true
mc admin policy attach local sopilot-ai-ro --user "$SOPILOT_S3_AI_ACCESS_KEY" || true
rm -rf "$policy_dir"
echo "minio-init: bucket $SOPILOT_S3_BUCKET ready"
