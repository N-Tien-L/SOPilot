import os
import sys
from pathlib import Path
from minio import Minio

# Configure path to recognize src module
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

from src.config.settings import settings

BASE_DATASET_PATH = "/app/base_dataset/handbook"
BUCKET_NAME = "poliwise-documents"

def migrate():
    # 1. Initialize Minio Client
    print(f"Connecting to MinIO at {settings.minio_endpoint}...")
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )

    # 2. Check if bucket exists, create if not
    if not client.bucket_exists(BUCKET_NAME):
        print(f"Creating bucket {BUCKET_NAME}...")
        client.make_bucket(BUCKET_NAME)
    else:
        print(f"Bucket {BUCKET_NAME} already exists.")

    # 3. Find files
    base_path = Path(BASE_DATASET_PATH)
    if not base_path.exists():
        print(f"Error: {BASE_DATASET_PATH} does not exist.")
        return

    files = list(base_path.rglob("*.md"))
    print(f"Found {len(files)} markdown files in {BASE_DATASET_PATH}.")

    # 4. Upload files
    uploaded_count = 0
    skipped_count = 0
    error_count = 0

    for path in files:
        # Calculate relative path (no handbook/ prefix because base_path is "/app/base_dataset/handbook")
        rel_path = str(path.relative_to(base_path)).replace("\\", "/")
        
        try:
            # Check if file already exists in MinIO to avoid re-uploading if they match size
            file_size = path.stat().st_size
            exists = False
            try:
                stat = client.stat_object(BUCKET_NAME, rel_path)
                if stat.size == file_size:
                    exists = True
            except Exception:
                pass
            
            if exists:
                skipped_count += 1
                continue

            # Upload
            client.fput_object(
                BUCKET_NAME,
                rel_path,
                str(path),
                content_type="text/markdown"
            )
            uploaded_count += 1
            if uploaded_count % 100 == 0:
                print(f"Uploaded {uploaded_count}/{len(files)} files...")
        except Exception as e:
            print(f"Error uploading {rel_path}: {e}")
            error_count += 1

    print(f"Migration completed! Uploaded: {uploaded_count}, Skipped: {skipped_count}, Errors: {error_count}")

if __name__ == "__main__":
    migrate()
