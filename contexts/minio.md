# Context: MinIO Configuration & Usage

This document provides technical context for the MinIO Object Storage implementation within the Poliwise monorepo. 

## 1. Overview
MinIO is used as an S3-compatible object storage service to store raw document files (PDF, DOCX, XLSX, images, etc.). It is primarily utilized by the **knowledge-service**.

## 2. Technical Implementation

### 2.1 Code Architecture
The **knowledge-service** integrates MinIO using the official Java SDK:

- **Dependency**: `io.minio:minio:8.5.14`
- **Core Components**:
    - `config/MinioConfig.java`: Handles `MinioClient` initialization and automatic bucket creation.
    - `service/StorageService.java`: Low-level wrapper for upload, download, delete, and pre-signed URL generation.
    - `service/DocumentService.java`: Orchestrates storage operations during document processing.

### 2.2 Configuration Defaults
Settings are managed via `@Value` annotations in `MinioConfig.java`:

| Property | Environment Variable | Default Value |
|----------|----------------------|---------------|
| Endpoint | `MINIO_ENDPOINT` | `http://localhost:9000` |
| Access Key | `MINIO_ACCESS_KEY` | `minioadmin` |
| Secret Key | `MINIO_SECRET_KEY` | `minioadmin` |
| Bucket Name | `MINIO_BUCKET_NAME` | `poliwise-documents` |

### 2.3 Storage Hierarchy
Files are stored using the following structure:
```
poliwise-documents/ (Bucket)
└── documents/
    └── {documentId}/ (Folder per document)
        └── {timestamp}.{extension} (Original file)
```

## 3. Infrastructure (Docker)

### 3.1 Docker Compose Integration
As of current audit, MinIO is **fully integrated** into the root `docker-compose.yml`.

- **Service Name**: `minio`
- **API Port**: `9000`
- **Console Port**: `9001`
- **Network**: `poliwise-network`

### 3.2 Manual Management (CLI)
If manual intervention is needed, use the `mc` (MinIO Client) inside the container:

```bash
# Setup alias
docker exec poliwise-minio mc alias set local http://localhost:9000 minioadmin minioadmin

# Create bucket manually
docker exec poliwise-minio mc mb local/poliwise-documents
```

## 4. Agent Best Practices & Constraints

- **Connectivity**: When running services in Docker, use `http://minio:9000` as the endpoint. For local development outside Docker, use `http://localhost:9000`.
- **Bucket Creation**: The application is designed to check for and create the `poliwise-documents` bucket on startup. Do not manually create it unless troubleshooting.
- **Pre-signed URLs**: Use these for temporary frontend access to private objects to avoid exposing MinIO credentials.
- **Large Files**: For documents >100MB, ensure the `MultipartUpload` thresholds are correctly configured in `StorageService`.

## 5. Development Verification Checklist
- [ ] MinIO container is healthy (`docker ps`)
- [ ] Bucket `poliwise-documents` exists (`mc ls`)
- [ ] `knowledge-service` logs show successful connection: "MinIO client initialized successfully"
- [ ] Uploaded files are visible in the Console at `http://localhost:9001`
