# Modal Ingestion Guide

Guide to run the Poliwise base dataset ingestion on Modal (free GPU) or generate SQL seed files.

## Two Approaches

### Approach 1: Generate SQL Seed File (RECOMMENDED)

```
┌──────────┐                     ┌─────────────────┐
│  Modal   │ ──► seed_data.sql ──►│  Any Postgres   │
│  (Cloud) │                     │  Database       │
└──────────┘                     └─────────────────┘
```

**Advantages:**
- No database connection needed from Modal
- SQL file is portable and version-controlled
- Can be committed to git
- Anyone can run `psql < seed_data.sql`

### Approach 2: Direct Ingestion to PostgreSQL

```
┌──────────┐                     ┌─────────────────┐
│  Modal   │ ───────────────►  │  Remote Postgres │
│  (Cloud) │   TCP Connection    │  (Supabase/etc) │
└──────────┘                     └─────────────────┘
```

**Requires:**
- Expose local Postgres (via ngrok/tunnel)
- Or use cloud Postgres (Supabase, Neon, Railway)

---

## Quick Start: Generate SQL Seed File

### Option A: Local with GPU (if you have one)

```bash
cd services/ingestion-service

# Install dependencies
pip install tiktoken torch transformers

# Run locally
python src/scripts/generate_seed_sql.py --output-path ./seed_data.sql
```

### Option B: On Modal (free GPU)

```bash
# Install Modal
pip install modal
modal setup

# Upload dataset to Modal volume
modal volume put poliwise-data ./base_dataset /base_dataset

# Run with GPU
modal run src/scripts/ingest_modal.py \
  --mode sql \
  --output-path /data/seed_data.sql

# Download the result
modal volume get poliwise-data /data/seed_data.sql ./seed_data.sql
```

---

## Running the SQL Seed File

### Option 1: Local Docker Postgres

```bash
# Ensure Flyway migrations ran first
docker compose run --rm flyway migrate

# Run the seed file
docker compose exec -T postgres psql -U poliwise -d poliwise < seed_data.sql
```

### Option 2: Direct psql

```bash
psql -h localhost -U poliwise -d poliwise < seed_data.sql
```

### Option 3: Supabase/Neon CLI

```bash
# Supabase
psql "postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres" < seed_data.sql

# Neon
psql "postgresql://user:password@ep-cool-name-123456.us-east-2.aws.neon.tech/poliwise?sslmode=require" < seed_data.sql
```

---

## GPU Options on Modal

| GPU | VRAM | Cost | Speed |
|-----|------|------|-------|
| **T4** | 16GB | **Free (30h/month)** | Medium |
| A10G | 24GB | Pay-as-you-go | Fast |
| A100 | 40GB | Pay-as-you-go | Fastest |

---

## Options Reference

### generate_seed_sql.py

```bash
python src/scripts/generate_seed_sql.py [options]

Options:
  --base-path PATH           Path to base dataset (default: /data/base_dataset/handbook)
  --output-path PATH         Output SQL file (default: ./seed_data.sql)
  --no-embeddings            Skip embeddings (faster, smaller file)
  --test-limit N             Limit files for testing (0 = all)

Examples:
  # Test with 10 files
  python src/scripts/generate_seed_sql.py --test-limit 10

  # Skip embeddings (much faster, no GPU needed)
  python src/scripts/generate_seed_sql.py --no-embeddings

  # Custom output path
  python src/scripts/generate_seed_sql.py --output-path ./my_seed.sql
```

### ingest_modal.py

```bash
# Generate SQL on Modal
modal run src/scripts/ingest_modal.py --mode sql

# Ingest directly to database (requires DATABASE_URL)
modal run src/scripts/ingest_modal.py --mode ingest --database-url "postgresql://..."

# With options
modal run src/scripts/ingest_modal.py \
  --mode sql \
  --test-limit 50 \
  --output-path /data/my_seed.sql
```

---

## Troubleshooting

### "Dataset path not found"

Make sure the base_dataset is at:
```
./base_dataset/handbook/
├── company/
├── engineering/
├── marketing/
├── sales/
└── ...
```

### "CUDA out of memory"

The script processes embeddings in batches of 4. If you still get OOM:
```python
# In generate_seed_sql.py, change:
batch_size = 2  # Reduce from 4
```

### "Module not found: tiktoken"

```bash
pip install tiktoken
```

### "Model download too slow"

Modal volumes persist cached models. First run will be slow, subsequent runs faster.

---

## Cost Estimate

### Modal Free Tier

| Resource | Limit | Cost |
|----------|-------|------|
| GPU (T4) | 30 hours/month | **$0** |
| Storage (volume) | 5 GB | **$0** |
| Bandwidth | 5 GB/month | **$0** |

**Full dataset ingestion: ~$0** (within free tier)

---

## File Structure

```
services/ingestion-service/src/scripts/
├── ingest_base_dataset.py      # Original Docker script
├── ingest_modal.py             # Modal script (SQL generation + direct ingest)
├── generate_seed_sql.py        # Standalone SQL generator
└── clear_and_reingest.py       # Clear DB and re-ingest
```

---

## Output SQL File Structure

```sql
-- Header
SET statement_timeout = 0;
...

-- =============================================================================
-- SECTION: Users
-- =============================================================================
INSERT INTO core.users ...;

-- =============================================================================
-- SECTION: Departments
-- =============================================================================
INSERT INTO core.departments ...;

-- =============================================================================
-- SECTION: Categories
-- =============================================================================
INSERT INTO metadata.categories ...;

-- =============================================================================
-- DOCUMENT: ...
-- =============================================================================
INSERT INTO knowledge.documents ...;
INSERT INTO metadata.document_metadata ...;
INSERT INTO knowledge.document_versions ...;
INSERT INTO metadata.document_tags ...;
INSERT INTO knowledge.chunks ...;

-- ... repeat for each document
```

---

## Verification Queries

After running the seed file:

```sql
-- Check counts
SELECT 
  (SELECT COUNT(*) FROM knowledge.documents) as documents,
  (SELECT COUNT(*) FROM knowledge.chunks) as chunks,
  (SELECT COUNT(*) FROM metadata.categories) as categories,
  (SELECT COUNT(*) FROM metadata.tags) as tags;

-- Sample documents
SELECT dm.title, c.name as category, d.status
FROM knowledge.documents d
JOIN metadata.document_metadata dm ON d.id = dm.document_id
LEFT JOIN metadata.categories c ON dm.category_id = c.id
LIMIT 5;

-- Check embeddings
SELECT id, chunk_type, content_length, embedding_dimension
FROM knowledge.chunks
LIMIT 5;
```
