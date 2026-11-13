# Poliwise System Flow Documentation
> **V1 LEGACY (frozen):** describes the eight-service V1 stack (gateway, RabbitMQ, `init-db`). For V2 work, the V2 tickets and `docs/02-architecture/designs/TECH-V2-*` win over this file until V2-17 rewrites it. Use it to read and port V1 behaviour, not as the V2 contract.

T├ái liß╗çu m├┤ tß║ú chi tiß║┐t c├íc luß╗ông ch├¡nh trong hß╗ç thß╗æng Poliwise.

---

## 1. Document Upload Flow (Nß║íp t├ái liß╗çu)

### 1.1 Tß╗òng quan luß╗ông

```mermaid
flowchart TD
    subgraph Frontend["Frontend (Client-side)"]
        A[User chß╗ìn file] --> B[T├¡nh SHA-256 checksum]
        B --> C{Has duplicate?}
        C -->|Duplicate| D[Hiß╗ân thß╗ï cß║únh b├ío cho user]
        C -->|Unique| E[Upload qua XHR vß╗¢i progress]
    end
    
    subgraph Backend["Backend (knowledge-service)"]
        E --> F[L╞░u file v├áo MinIO]
        F --> G[Tß║ío Document entity: status=STAGING]
        G --> H[Gß╗ìi AI metadata suggestion]
        H --> I[User ─æiß╗üu chß╗ënh & x├íc nhß║¡n]
        I --> J[POST /confirm ΓåÆ trigger ingestion]
    end
    
    subgraph Ingestion["Ingestion Service"]
        J --> K[3-Layer De-duplication]
        K --> L{Layer 1: File checksum}
        L -->|Match| M[BLOCK - Tr├╣ng file]
        L -->|No match| N{Layer 2: Content hash}
        N -->|Match| M
        N -->|No match| O{Layer 3: BGE-M3 similarity}
        O -->|ΓëÑ 0.98| M
        O -->|0.85-0.98| P[SUGGEST VERSION - Gß╗úi ├╜ phi├¬n bß║ún mß╗¢i]
        O -->|< 0.85| Q[INGEST - Xß╗¡ l├╜ document]
        Q --> R[Chunking document]
        R --> S[Tß║ío embeddings vß╗¢i BGE-M3]
        S --> T[L╞░u chunks + vectors v├áo pgvector]
        T --> U[Document status: READY]
    end
```

### 1.2 Chi tiß║┐t tß╗½ng b╞░ß╗¢c

#### B╞░ß╗¢c 1: User chß╗ìn file

Frontend cung cß║Ñp giao diß╗çn drag & drop hoß║╖c click ─æß╗â chß╗ìn file.

```typescript
// frontend/web/components/documents/UploadModal.tsx
const handleFileSelect = async (files: FileList) => {
  const file = files[0];
  
  // Validate file type
  const allowedTypes = [
    'application/pdf',           // PDF
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // DOCX
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // XLSX
    'text/plain',               // TXT
    'image/png',                // PNG (OCR)
    'image/jpeg',              // JPG (OCR)
    'text/markdown'            // MD
  ];
  
  if (!allowedTypes.includes(file.type)) {
    throw new Error('File type not supported');
  }
  
  // Validate file size (100MB)
  if (file.size > 100 * 1024 * 1024) {
    throw new Error('File size exceeds 100MB limit');
  }
  
  // Proceed to checksum calculation
  const computedChecksum = await computeFileChecksum(file);
};
```

#### B╞░ß╗¢c 2: T├¡nh SHA-256 checksum (Client-side)

Checksum ─æ╞░ß╗úc t├¡nh ph├¡a client ─æß╗â:

1. **Pre-check tr╞░ß╗¢c khi upload**: Tr├ính upload file ─æ├ú tß╗ôn tß║íi
2. **De-duplication Layer 1**: So s├ính file byte-by-byte
3. **Performance**: Nhanh h╞ín upload rß╗ôi mß╗¢i check

```typescript
// Utility function to compute SHA-256 checksum
async function computeFileChecksum(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
```

#### B╞░ß╗¢c 3: Pre-check duplicate (Layer 1 only)

```typescript
// frontend/web/services/document.service.ts
const checkDuplicate = async (checksum: string): Promise<DuplicateCheckResult> => {
  const response = await fetch(
    `${API_BASE}/api/v1/documents/check-duplicate?checksum=${checksum}`
  );
  return response.json();
};

// Response structure
interface DuplicateCheckResult {
  isDuplicate: boolean;
  action: 'BLOCK' | 'WARN' | 'ALLOW';
  existingDocument?: {
    id: string;
    title: string;
    uploadedAt: string;
    uploadedBy: string;
  };
  suggestion?: {
    existingVersionId: string;
    similarity: number;
    action: 'NEW_VERSION';
  };
}
```

#### B╞░ß╗¢c 4-6: Upload v├á tß║ío Document

```java
// knowledge-service/DocumentManagementService.java
@Service
public class DocumentManagementService {
    
    @Transactional
    public Document uploadDocument(MultipartFile file, String checksum, 
                                   String uploadedBy, UUID departmentId) {
        // 1. Validate file
        validateFile(file); // 100MB, allowed extensions
        
        // 2. Upload to MinIO (S3-compatible storage)
        String fileKey = minioService.uploadFile(file, checksum);
        
        // 3. Create Document entity with STAGING status
        Document document = Document.builder()
            .title(extractTitleFromFilename(file.getOriginalFilename()))
            .status(DocumentStatus.STAGING)
            .uploadedBy(uploadedBy)
            .departmentId(departmentId)
            .build();
        document = documentRepository.save(document);
        
        // 4. Create Version entity
        DocumentVersion version = DocumentVersion.builder()
            .documentId(document.getId())
            .versionNumber(1)
            .fileKey(fileKey)
            .fileChecksum(checksum)
            .fileSize(file.getSize())
            .mimeType(file.getContentType())
            .originalFilename(file.getOriginalFilename())
            .status(VersionStatus.PENDING)
            .build();
        versionRepository.save(version);
        
        // 5. Publish event to RabbitMQ
        rabbitMQTemplate.convertAndSend(
            "document.uploaded",
            new DocumentUploadedEvent(document.getId(), version.getId())
        );
        
        return document;
    }
    
    @Transactional
    public void confirmDocument(UUID documentId, DocumentConfirmRequest request) {
        // Update document metadata
        document.setTitle(request.getTitle());
        document.setDescription(request.getDescription());
        document.setCategoryId(request.getCategoryId());
        document.setLanguage(request.getLanguage());
        document.setIsPolicy(request.isPolicy());
        document.setStatus(DocumentStatus.CONFIRMED);
        documentRepository.save(document);
        
        // Trigger ingestion pipeline
        ingestionPublisher.publishConfirmEvent(documentId);
    }
}
```

#### B╞░ß╗¢c 7: X├íc nhß║¡n metadata (Confirm)

Sau khi upload th├ánh c├┤ng, AI service gß╗úi ├╜ metadata dß╗▒a tr├¬n nß╗Öi dung document:

| Field | Description | AI-generated |
|-------|-------------|--------------|
| `title` | Ti├¬u ─æß╗ü document | Γ£à (extracted from content) |
| `description` | M├┤ tß║ú ngß║»n | Γ£à (AI-generated summary) |
| `category` | Danh mß╗Ñc | Γ£à (based on content classification) |
| `tags` | Tags ph├ón loß║íi | Γ£à (keyword extraction) |
| `language` | Ng├┤n ngß╗» | Γ£à (auto-detected: vi/en) |
| `isPolicy` | C├│ phß║úi ch├¡nh s├ích kh├┤ng | Γ£à (policy detection) |

User c├│ thß╗â ─æiß╗üu chß╗ënh tr╞░ß╗¢c khi confirm.

---

### 1.3 De-duplication System

#### Tß║íi sao d├╣ng BGE-M3?

**BGE-M3 (BAAI General Embedding M3)** l├á embedding model state-of-the-art tß╗½ BAAI (Beijing Academy of Artificial Intelligence).

**1. ─Éa ng├┤n ngß╗» (Multilingual)**

BGE-M3 ─æ╞░ß╗úc train tr├¬n dß╗» liß╗çu ─æa ng├┤n ngß╗» vß╗¢i h╞ín 100 ng├┤n ngß╗», bao gß╗ôm:

- Tiß║┐ng Anh (English)
- Tiß║┐ng Viß╗çt (Vietnamese) 
- Tiß║┐ng Trung (Chinese)
- Tiß║┐ng Nhß║¡t (Japanese)
- Tiß║┐ng H├án (Korean)
- Tiß║┐ng Th├íi (Thai)
- ... v├á 95+ ng├┤n ngß╗» kh├íc

Vß╗¢i Poliwise - hß╗ç thß╗æng quß║ún l├╜ v─ân bß║ún ch├¡nh s├ích tß║íi Viß╗çt Nam - viß╗çc hß╗ù trß╗ú tiß║┐ng Viß╗çt l├á bß║»t buß╗Öc. BGE-M3 hiß╗âu ─æ╞░ß╗úc:
- C├íc k├╜ tß╗▒ c├│ dß║Ñu (├ó, ─â, ─æ, ├¬, ├┤, ╞í, ╞░)
- Cß║Ñu tr├║c c├óu tiß║┐ng Viß╗çt
- Thuß║¡t ngß╗» ch├¡nh s├ích tiß║┐ng Viß╗çt

**2. Dense + Sparse Embeddings**

BGE-M3 tß║ío ra 2 loß║íi embeddings:

| Type | Dimension | Use Case |
|------|-----------|----------|
| **Dense** | 1024 chiß╗üu | Semantic similarity search |
| **Sparse** | 2501 chiß╗üu | Keyword/BM25 matching |

Kß║┐t hß╗úp cß║ú 2 cho hybrid search tß╗æi ╞░u.

**3. Performance tr├¬n MTEB Benchmark**

MTEB (Massive Text Embedding Benchmark) l├á benchmark chuß║⌐n cho embedding models:

| Task | BGE-M3 Score | Description |
|------|--------------|-------------|
| Retrieval | **66.4** | Top performer |
| Clustering | **55.4** | Document classification |
| Pair Classification | **84.3** | Semantic similarity |
| Reranking | **60.0** | Cross-encoder tasks |
| STS (Semantic Textual Similarity) | **83.1** | Sentence similarity |

**4. Open Source & Self-hostable**

- **Miß╗àn ph├¡**: Kh├┤ng tß╗æn chi ph├¡ API nh╞░ OpenAI embeddings
- **Self-host**: C├│ thß╗â deploy tr├¬n HuggingFace TEI (Text Embeddings Inference)
- **Privacy**: Dß╗» liß╗çu kh├┤ng rß╗¥i khß╗Åi hß╗ç thß╗æng
- **Customizable**: C├│ thß╗â fine-tune nß║┐u cß║ºn

**5. Technical Specs**

```python
# Model configuration
BGE_M3_CONFIG = {
    "model_name": "BAAI/bge-m3",
    "max_seq_length": 8192,
    "dense_dimension": 1024,
    "sparse_dimension": 2501,
    "normalize_embeddings": True,
    "batch_size": 32,
}

# Example embedding output
{
    "dense": [0.123, -0.456, ..., 0.789],  # 1024 dims
    "sparse": {
        "indices": [0, 45, 123, ...],      # Word positions
        "values": [0.9, 0.7, 0.5, ...]     # Importance scores
    }
}
```

#### 3-Layer De-duplication

Poliwise sß╗¡ dß╗Ñng 3-layer deduplication ─æß╗â ─æß║úm bß║úo:

1. **Kh├┤ng upload tr├╣ng lß║╖p**: Tiß║┐t kiß╗çm storage
2. **Ph├ít hiß╗çn version mß╗¢i**: Cß║¡p nhß║¡t document khi c├│ thay ─æß╗òi
3. **Semantic detection**: Ph├ít hiß╗çn document t╞░╞íng tß╗▒ vß╗ü nß╗Öi dung

```mermaid
flowchart LR
    subgraph Layer1["Layer 1: File-level"]
        A1[File SHA-256] --> A2[Compare with existing files]
    end
    
    subgraph Layer2["Layer 2: Content-level"]
        B1[Extract text] --> B2[SHA-256 of text]
        B2 --> B3[Compare with existing content]
    end
    
    subgraph Layer3["Layer 3: Semantic-level"]
        C1[BGE-M3 Embedding] --> C2[Weighted multi-sample]
        C2 --> C3[Vector similarity search]
    end
    
    A2 -->|No match| B3
    B3 -->|No match| C3
    C3 -->|Similarity ΓëÑ 0.98| BLOCK[BLOCK]
    C3 -->|0.85 Γëñ sim < 0.98| SUGGEST[SUGGEST VERSION]
    C3 -->|sim < 0.85| UNIQUE[UNIQUE - INGEST]
```

**Chi tiß║┐t tß╗½ng Layer:**

| Layer | Method | Pros | Cons | Action |
|-------|--------|------|------|--------|
| L1 | File SHA-256 | Instant, exact | Same content diff format = not detected | BLOCK if exact |
| L2 | Content SHA-256 | Format-independent | "Edited" = new hash | BLOCK if exact |
| L3 | BGE-M3 Vector | Semantic similarity | Slower, needs threshold tuning | BLOCK/SUGGEST based on threshold |

#### Layer 1: File-level De-duplication (SHA-256)

**Mß╗Ñc ─æ├¡ch**: Ph├ít hiß╗çn file tr├╣ng lß║»p byte-by-byte.

**C├ích hoß║ít ─æß╗Öng**:
1. Frontend t├¡nh SHA-256 hash cß╗ºa to├án bß╗Ö file
2. Gß╗¡i hash l├¬n backend ─æß╗â kiß╗âm tra
3. So s├ính vß╗¢i hash cß╗ºa tß║Ñt cß║ú file ─æ├ú upload

```typescript
// Frontend: T├¡nh SHA-256 cß╗ºa file
const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());

// Backend: Kiß╗âm tra tr├╣ng lß║»p
const existing = await versionRepo.findByChecksum(hash);
if (existing) return { action: 'BLOCK', existing };
```

**╞»u ─æiß╗âm**: Cß╗▒c nhanh, ch├¡nh x├íc tuyß╗çt ─æß╗æi, kh├┤ng cß║ºn giß║úi n├⌐n file.
**Nh╞░ß╗úc ─æiß╗âm**: Chß╗ë ph├ít hiß╗çn file **ho├án to├án giß╗æng nhau** (c├╣ng bytes). File c├╣ng nß╗Öi dung nh╞░ng format kh├íc nhau (PDF vs DOCX) sß║╜ kh├┤ng bß╗ï ph├ít hiß╗çn.
**Khi n├áo trigger**: Mß╗ìi file upload ─æß╗üu qua L1 ─æß║ºu ti├¬n.

#### Layer 2: Content-level De-duplication (Text SHA-256)

**Mß╗Ñc ─æ├¡ch**: Ph├ít hiß╗çn file tr├╣ng lß║»p **format kh├íc nhau** nh╞░ng nß╗Öi dung giß╗æng nhau.

**C├ích hoß║ít ─æß╗Öng**:
1. Tr├¡ch xuß║Ñt text tß╗½ file (bß╗Å qua ─æß╗ïnh dß║íng, h├¼nh ß║únh, font)
2. T├¡nh SHA-256 hash cß╗ºa text thuß║ºn t├║y
3. So s├ính vß╗¢i content hash cß╗ºa c├íc document ─æ├ú l╞░u

```python
# Backend: Tr├¡ch xuß║Ñt text v├á hash
text = text_extractor.extract(file)  # loß║íi bß╗Å format, chß╗ë giß╗» nß╗Öi dung
content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

existing = await versionRepo.findByContentHash(content_hash)
if (existing) return { action: 'BLOCK', existing }
```

**╞»u ─æiß╗âm**: Format-independent - ph├ít hiß╗çn c├╣ng nß╗Öi dung kh├íc format (PDFΓåÆDOCXΓåÆTXT).
**Nh╞░ß╗úc ─æiß╗âm**: Text extraction c├│ thß╗â kh├┤ng ho├án hß║úo (OCR lß╗ùi, layout phß╗⌐c tß║íp), v├á bß║Ñt kß╗│ thay ─æß╗òi nhß╗Å n├áo (sß╗¡a 1 chß╗») ─æß╗üu tß║ío hash mß╗¢i.
**Khi n├áo trigger**: Khi L1 kh├┤ng match (file bytes kh├íc nhau).

#### Layer 3: Semantic De-duplication (BGE-M3 Vector)

**Mß╗Ñc ─æ├¡ch**: Ph├ít hiß╗çn documents **t╞░╞íng tß╗▒ vß╗ü ngß╗» ngh─⌐a** (d├╣ nß╗Öi dung kh├┤ng ho├án to├án giß╗æng).

**C├ích hoß║ít ─æß╗Öng**:
1. Lß║Ñy 3 samples tß╗½ document (head, body, tail) vß╗¢i trß╗ìng sß╗æ kh├íc nhau
2. Generate BGE-M3 embeddings cho tß╗½ng sample
3. T├¡nh weighted average embedding
4. So s├ính vector similarity vß╗¢i tß║Ñt cß║ú document embeddings trong pgvector

```python
# Multi-sample strategy vß╗¢i weighted average
samples = [
    (head_sample, 0.3),   # 30% - phß║ºn mß╗ƒ ─æß║ºu
    (body_sample, 0.5),   # 50% - phß║ºn th├ón (quan trß╗ìng nhß║Ñt)
    (tail_sample, 0.2),   # 20% - phß║ºn kß║┐t luß║¡n
]

embeddings = await embed_batch([s[0] for s in samples])
weighted_emb = sum(emb * weight for emb, (_, weight) in zip(embeddings, samples))

# So s├ính vß╗¢i pgvector
similarity = await find_similar(weighted_emb)
```

**╞»u ─æiß╗âm**: Hiß╗âu ngß╗» ngh─⌐a - ph├ít hiß╗çn documents gß║ºn giß╗æng, phi├¬n bß║ún cß║¡p nhß║¡t, nß╗Öi dung t╞░╞íng tß╗▒.
**Nh╞░ß╗úc ─æiß╗âm**: Chß║¡m h╞ín L1/L2, cß║ºn threshold tuning, c├│ thß╗â false positive.
**Khi n├áo trigger**: Khi cß║ú L1 v├á L2 ─æß╗üu kh├┤ng match.

#### Layer 3: Multi-sample Weighted Embedding

─Éß╗â so s├ính semantic giß╗»a 2 documents d├ái, ta kh├┤ng thß╗â embedding to├án bß╗Ö text (giß╗¢i hß║ín 512 tokens/chunk). Thay v├áo ─æ├│:

```python
# services/ingestion-service/src/services/deduplicator.py
class Deduplicator:
    SEMANTIC_BLOCK_THRESHOLD = 0.98  # ΓëÑ 98% similar = duplicate
    SEMANTIC_VERSION_THRESHOLD = 0.85  # 85-98% = suggest new version
    
    async def check_semantic_duplicate(self, text: str) -> DeduplicationResult:
        # Sample 1: Introduction (Head)
        # Weight: 0.3 (30%)
        # Rationale: Documents often have similar intro patterns
        head_sample = text[:3000]
        head_weight = 0.3
        
        # Sample 2: Core content (Body)  
        # Weight: 0.5 (50%) - MOST IMPORTANT
        # Rationale: Body contains the unique information
        if len(text) > 4000:
            body_start = (len(text) - 4000) // 2
            body_sample = text[body_start:body_start + 4000]
        else:
            body_sample = text[3000:]
        body_weight = 0.5
        
        # Sample 3: Conclusion (Tail)
        # Weight: 0.2 (20%)
        # Rationale: Similar conclusions don't make documents duplicates
        tail_sample = text[-2000:] if len(text) > 2000 else text[3000:]
        tail_weight = 0.2
        
        # Generate embeddings for all samples
        samples = [(head_sample, head_weight), 
                   (body_sample, body_weight), 
                   (tail_sample, tail_weight)]
        
        embeddings = await embedding_service.embed_batch([s[0] for s in samples])
        
        # Weighted average
        weighted_emb = sum(emb * weight for emb, (_, weight) in zip(embeddings, samples))
        
        # Compare with existing document embeddings in pgvector
        near_duplicates = await version_repo.find_near_duplicates(weighted_emb)
        
        return near_duplicates
```

**Tß║íi sao weighted samples?**

1. **Body weight cao nhß║Ñt (0.5)**: Phß║ºn th├ón chß╗⌐a nß╗Öi dung ch├¡nh, kh├íc biß╗çt nhß║Ñt giß╗»a documents
2. **Head weight trung b├¼nh (0.3)**: Phß║ºn giß╗¢i thiß╗çu th╞░ß╗¥ng c├│ patterns chung
3. **Tail weight thß║Ñp nhß║Ñt (0.2)**: Phß║ºn kß║┐t luß║¡n th╞░ß╗¥ng generic

**Threshold explanation:**

| Similarity | Interpretation | Action |
|-----------|----------------|--------|
| ΓëÑ 0.98 | Nearly identical (maybe different formatting) | BLOCK as duplicate |
| 0.85 - 0.98 | Very similar (minor edits) | SUGGEST new version |
| < 0.85 | Different content | ALLOW as new document |

#### Embedding Cache (Layer 3 optimization)

─Éß╗â tß╗æi ╞░u performance v├á cost, BGE-M3 embeddings ─æ╞░ß╗úc cache:

```python
# services/ingestion-service/src/services/embedding_service.py
class EmbeddingService:
    async def embed_batch_cached(self, texts: list[str], session) -> list[list[float]]:
        # Step 1: Compute SHA-256 hash for each text
        hashes = [hashlib.sha256(t.encode('utf-8')).hexdigest() for t in texts]
        
        # Step 2: Batch lookup in cache
        cache_hits = await cache_repo.lookup_batch(hashes, EMBEDDING_MODEL_NAME)
        
        # Step 3: Identify cache misses
        miss_indices = [i for i, h in enumerate(hashes) if h not in cache_hits]
        miss_texts = [texts[i] for i in miss_indices]
        
        # Step 4: Generate embeddings only for misses
        if miss_texts:
            miss_embeddings = await self.embed_batch(miss_texts)
            
            # Step 5: Save new embeddings to cache
            await cache_repo.save_batch([{
                "text_hash": hashes[miss_indices[i]],
                "text_length": len(miss_texts[i]),
                "embedding_model": "BGE_M3",
                "embedding_dimension": 1024,
                "embedding_vector": miss_embeddings[i]
            } for i in range(len(miss_texts))])
        
        # Step 6: Merge results (preserving original order)
        return [cache_hits.get(h) or miss_embeddings[miss_indices.index(i)]
                for i, h in enumerate(hashes)]
```

**Cache table schema:**

```sql
CREATE TABLE knowledge.embedding_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 of text
    text_length INTEGER NOT NULL,
    embedding_model VARCHAR(50) NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    embedding_vector VECTOR(1024) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_embedding_cache_hash ON knowledge.embedding_cache(text_hash);
CREATE INDEX idx_embedding_cache_model ON knowledge.embedding_cache(embedding_model);
```

---

## 2. AI Chat Flow (RAG Pipeline)

### 2.1 Tß╗òng quan RAG Pipeline

```mermaid
flowchart TB
    subgraph Input["INPUT"]
        A[User Query]
    end
    
    subgraph Guard["GATEWAY LAYERS"]
        A --> B[Layer 1: Toxic Filter]
        B -->|Clean| C[Layer 2: Intent Classification]
        B -->|Toxic| B1[Block + Publish Violation]
    end
    
    subgraph Processing["PROCESSING PIPELINE"]
        C -->|SIMPLE| D[Layer 2: Simple Responder]
        C -->|COMPLEX| E[Layer 3: Query Refiner]
        
        E --> F[Hybrid Search Engine]
        
        subgraph Retrieval["Retrieval"]
            F --> G[Dense: pgvector + BGE-M3]
            F --> H[Sparse: PostgreSQL ts_rank]
            G --> I[RRF Fusion]
            H --> I
            I --> J[Reranker: Cross-encoder]
        end
        
        J --> K[Knowledge Gap Detector]
        
        K -->|Has relevant chunks| L[LLM: Contextual Answer]
        K -->|No relevant chunks| M[LLM: General Answer + Mark UNANSWERED]
    end
    
    subgraph Output["OUTPUT"]
        L --> N[Streaming Response via SSE]
        M --> N
        D --> O[Direct Response]
    end
    
    style Guard fill:#f9f,color:#000
    style Processing fill:#bbf,color:#000
    style Output fill:#bfb,color:#000
```

### 2.2 Chi tiß║┐t tß╗½ng Layer

#### Layer 1: Toxic Filter (Content Guard)

Content Guard l├á lß╗¢p bß║úo vß╗ç ─æß║ºu ti├¬n, ng─ân chß║╖n queries ─æß╗Öc hß║íi.

**Architecture:**

```python
# services/ai-qa-service/src/services/pipeline/layer1_toxic_filter.py
class ToxicFilterService:
    """
    Layer 1: Multi-stage toxic content detection
    
    Stage 1: Rule-based pre-filter (fast, no API call)
    Stage 2: LLM classification (accurate, async)
    """
    
    TOXIC_PATTERNS = [
        r'\b(hack|exploit|bypass)\b',  # Security-related
        r'<script.*?>.*?</script>',      # XSS injection
        r'\$\(.*\)',                     # Command injection
        # ... more patterns
    ]
    
    CATEGORIES = [
        "TOXIC_QUERY",   # General toxic content
        "ABUSE",         # Personal attacks
        "SPAM",          # Repetitive/nonsensical
        "JAILBREAK",     # Prompt injection attempts
        "INJECTION",     # Code/injection attacks
    ]
    
    async def check(self, query: str) -> ToxicFilterResult:
        # Stage 1: Fast rule-based check
        if self._matches_patterns(query):
            return ToxicFilterResult(
                is_toxic=True,
                label="TOXIC_QUERY",
                severity="LOW"
            )
        
        # Stage 2: LLM classification (if needed)
        llm_result = await self._llm_classify(query)
        if llm_result.is_toxic:
            await self.violation_publisher.publish(llm_result)
            return llm_result
        
        return ToxicFilterResult(is_toxic=False)
```

**Violation event published to RabbitMQ:**

```python
# When toxic content detected
await violation_publisher.publish(
    ViolationEvent(
        type="TOXIC_QUERY",
        severity="HIGH" if label in ["JAILBREAK", "INJECTION"] else "LOW",
        evidence=query,
        user_id=user_context.user_id,
        source="SYSTEM",
        timestamp=datetime.utcnow()
    )
)
```

#### Layer 2: Intent Classification

**Model: Llama-3.1-8B-Instant via Groq API**

**Tß║íi sao Llama-3.1-8B-Instant?**

| Criteria | Llama-3.1-8B-Instant | GPT-4 | Claude |
|----------|---------------------|-------|--------|
| **Speed (Groq)** | ~1000 tokens/sec | ~50 tokens/sec | ~80 tokens/sec |
| **Cost** | $0.05/1M tokens | $15/1M tokens | $3/1M tokens |
| **Vietnamese** | Γ£à Good | Γ£à Excellent | Γ£à Excellent |
| **Simple task** | Γ£à Ideal | Γ¥î Overkill | Γ¥î Overkill |

**Llama-3.1-8B-Instant advantages:**

1. **Ultra-fast inference**: Groq LPU (Language Processing Unit) ─æß║ít ~1000 tokens/sec
2. **Cost-effective**: Rß║╗ h╞ín 300x so vß╗¢i GPT-4 cho classification task
3. **Sufficient accuracy**: Vß╗¢i binary classification (SIMPLE vs COMPLEX), 8B model l├á ─æß╗º
4. **Low latency**: User kh├┤ng notice delay khi typing

**Classification prompt:**

```python
# services/ai-qa-service/src/services/pipeline/layer2_intent_classifier.py
INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for an AI policy assistant.
Your task: Classify the user query as [SIMPLE] or [COMPLEX].

[SIMPLE]: Questions that DO NOT require searching internal documents.
If an ordinary person without special knowledge could answer confidently, it is SIMPLE.

Examples of SIMPLE:
- "Hello, how are you?" -> SIMPLE
- "What is 2 + 2?" -> SIMPLE  
- "Thank you, goodbye!" -> SIMPLE
- "What's the weather today?" -> SIMPLE
- "Can you help me?" -> SIMPLE

[COMPLEX]: Questions that REQUIRE searching internal documents/policies.
If you would need to look up a document/policy to answer correctly, it is COMPLEX.

Examples of COMPLEX:
- "What is our company's remote work policy?" -> COMPLEX
- "How many vacation days am I entitled to?" -> COMPLEX
- "What are the expense reimbursement procedures?" -> COMPLEX
- "policy vß╗ü remote work nh╞░ thß║┐ n├áo?" -> COMPLEX (Vietnamese mixed)

Rule: 
- SIMPLE = any person could answer without documents
- COMPLEX = needs internal knowledge/policy lookup

User Query: {query}

Recent conversation:
{recent_history}

Return ONLY one word: [SIMPLE] or [COMPLEX]"""
```

**Intent types explained:**

| Intent | Description | Pipeline Path |
|--------|-------------|----------------|
| **SIMPLE** | Greeting, math, general knowledge | Layer 2 Responder (direct LLM) |
| **COMPLEX** | Policy questions, document-specific | Layer 3 + RAG pipeline |

**SIMPLE query examples:**

```python
SIMPLE_QUERIES = [
    "hello", "hi there", "ch├áo bß║ín",  # Greetings
    "how are you?", "bß║ín khß╗Åe kh├┤ng?",  # Check-in
    "2 + 2 = ?", "5 nh├ón 6 bß║▒ng bao nhi├¬u",  # Math
    "thanks", "cß║úm ╞ín", "goodbye", "tß║ím biß╗çt",  # Closing
    "what is the weather?", "trß╗¥i h├┤m nay thß║┐ n├áo",  # General
    "who are you?", "bß║ín l├á ai",  # Meta questions
]
```

**COMPLEX query examples:**

```python
COMPLEX_QUERIES = [
    "what is our WFH policy?",  # Policy lookup
    "policy vß╗ü l├ám viß╗çc tß╗½ xa",  # Vietnamese policy
    "how do I request time off?",  # Procedure
    "expense report process",  # Process documentation
    "remote work guidelines",  # Guidelines
    "benefits for new employees",  # HR policy
]
```

#### Layer 3: Query Refinement

Query Refiner contextualizes and improves the search query:

```python
# services/ai-qa-service/src/services/pipeline/query_refiner.py
class QueryRefinerService:
    """
    Refines user query before retrieval:
    1. Contextualize follow-up questions
    2. Translate mixed language queries
    3. Expand abbreviations
    """
    
    async def refine(self, original_query: str, history: list[Message]) -> RefinedQuery:
        # Build context from conversation history
        context = self._build_context(history)
        
        prompt = QUERY_REFINEMENT_PROMPT.format(
            original_query=original_query,
            context=context
        )
        
        refined = await groq_client.complete(prompt)
        
        return RefinedQuery(
            original=original_query,
            refined=refined,
            was_expanded=(refined != original_query)
        )
```

**Examples:**

| Original Query | Refined Query | Reason |
|----------------|---------------|--------|
| "n├│ c├│ ─æ╞░ß╗úc kh├┤ng?" | "policy n├áy c├│ ─æ╞░ß╗úc ph├⌐p kh├┤ng?" | Follow-up context |
| "WFH policy" | "remote work policy work from home" | Expand abbreviation |
| "ch├¡nh s├ích ─æ├│" | "ch├¡nh s├ích nghß╗ë ph├⌐p n─âm 2024" | Previous context |

#### Hybrid Search (Retrieval)

Hybrid search kß║┐t hß╗úp 2 ph╞░╞íng ph├íp retrieval:

**1. Dense Retrieval (Semantic)**
- Sß╗¡ dß╗Ñng BGE-M3 embeddings
- T├¼m documents c├│ ngß╗» ngh─⌐a t╞░╞íng tß╗▒ query
- Tß╗æt vß╗¢i synonyms, paraphrases

**2. Sparse Retrieval (Full-text Search)**
- Sß╗¡ dß╗Ñng PostgreSQL `ts_rank` (BM25-like algorithm)
- T├¼m documents chß╗⌐a keywords ch├¡nh x├íc
- Tß╗æt vß╗¢i technical terms, proper nouns

```python
# services/ai-qa-service/src/services/retrieval/hybrid_search.py
class HybridSearchService:
    """
    Hybrid search combining dense + sparse retrieval
    
    Dense: BGE-M3 embeddings ΓåÆ pgvector (cosine similarity)
    Sparse: PostgreSQL ts_rank (BM25-like full-text search)
    """
    
    async def search(
        self,
        query: str,
        user_id: str,
        user_role: str,
        filters: Optional[RetrievalFilters] = None,
        limit: int = 10
    ) -> list[RetrievalChunk]:
        # 1. Generate query embedding with BGE-M3
        query_embedding = await self.embedding_service.embed(query)
        
        # 2. Dense retrieval via pgvector
        dense_chunks = await self.vector_store.search(
            embedding=query_embedding,
            limit=limit * 2,  # Get more for reranking
            filters=self._build_filters(user_id, user_role, filters)
        )
        
        # 3. Sparse retrieval via BM25
        sparse_chunks = await self.bm25_index.search(
            query=query,
            limit=limit * 2
        )
        
        # 4. Reciprocal Rank Fusion (RRF)
        ranked_chunks = self._reciprocal_rank_fusion(
            dense_results=dense_chunks,
            sparse_results=sparse_chunks,
            k=60  # RRF constant
        )
        
        return ranked_chunks[:limit]
    
    def _reciprocal_rank_fusion(
        self,
        dense_results: list[Chunk],
        sparse_results: list[Chunk],
        k: int = 60
    ) -> list[Chunk]:
        """
        Reciprocal Rank Fusion combines rankings from multiple retrievers.
        
        Formula: RRF(d) = ╬ú 1/(k + rank(d))
        
        Benefits:
        - Simple yet effective
        - No training needed
        - Handles different result sets well
        """
        scores = defaultdict(float)
        
        for rank, chunk in enumerate(dense_results):
            scores[chunk.id] += 1 / (k + rank + 1)
        
        for rank, chunk in enumerate(sparse_results):
            scores[chunk.id] += 1 / (k + rank + 1)
        
        sorted_chunks = sorted(
            dense_results + sparse_results,
            key=lambda c: scores[c.id],
            reverse=True
        )
        
        return sorted_chunks
```

**Reciprocal Rank Fusion (RRF) Score - ├¥ ngh─⌐a v├á ß╗¿ng dß╗Ñng:**

RRF score cß╗ºa 1 chunk = **tß╗òng ─æiß╗âm tß╗½ cß║ú Dense v├á Sparse retrieval**, ─æ╞░ß╗úc t├¡nh bß║▒ng:

```
score = 1/(k + dense_rank) + 1/(k + sparse_rank)
```

**V├¡ dß╗Ñ thß╗▒c tß║┐ trong Poliwise:**

Query: "chß║┐ ─æß╗Ö nghß╗ë ph├⌐p n─âm 2026"

| Chunk | Dense Score | Sparse Score | **RRF Total** |
|-------|------------|--------------|---------------|
| "Quy ─æß╗ïnh nghß╗ë ph├⌐p" | 1 | 1 | 0.7/61 + 0.3/61 = **0.0164** |
| "Working from home policy" | 3 | 8 | 0.7/63 + 0.3/68 = **0.0088** |
| "Leave policy 2026" | 2 | 3 | 0.7/62 + 0.3/63 = **0.0115** |

ΓåÆ **Chunk 1 v├á 3** ─æ╞░ß╗úc ╞░u ti├¬n cao nhß║Ñt v├¼ ─æß╗⌐ng top trong cß║ú 2 retrievers.

**Tß║íi sao cß║ºn kß║┐t hß╗úp cß║ú 2?**

| Retriever | Strength | Weakness |
|-----------|----------|----------|
| **Dense** | Hiß╗âu "nghß╗ë ph├⌐p" Γëê "time off" | Kh├┤ng bß║»t ─æ╞░ß╗úc tß╗½ hiß║┐m |
| **Sparse** | Exact match tß╗½ kh├│a | Kh├┤ng hiß╗âu synonyms |

**RRF kß║┐t hß╗úp cß║ú 2** ΓåÆ ─æß║úm bß║úo:
- Documents c├│ keywords ─æ├║ng ΓåÆ ─æ╞░ß╗úc boost tß╗½ sparse
- Documents c├│ ngß╗» ngh─⌐a li├¬n quan ΓåÆ ─æ╞░ß╗úc boost tß╗½ dense

**Trong Conversation Context:**

Sau khi retrieve, chunks ─æ╞░ß╗úc ─æ╞░a v├áo prompt cho LLM:

```
Context chunks:
1. [RRF: 0.0164] Quy ─æß╗ïnh nghß╗ë ph├⌐p - c├┤ng ty ABC...
2. [RRF: 0.0115] Leave policy 2026 - employee handbook...

Question: chß║┐ ─æß╗Ö nghß╗ë ph├⌐p n─âm 2026?
Answer: Theo quy ─æß╗ïnh cß╗ºa c├┤ng ty...
```

**pgvector query example:**

```sql
-- Vector similarity search with RBAC filters
SELECT 
    dc.id,
    dc.chunk_text,
    dc.metadata,
    dc.embedding <=> $1 AS distance
FROM knowledge.document_chunks dc
JOIN knowledge.documents d ON dc.document_id = d.id
WHERE 
    -- RBAC: User can only see documents in their department or public
    (d.department_id = $2 OR d.is_public = true)
    -- Status filter: Only READY documents
    AND d.status = 'READY'
    -- Optional category filter
    AND ($3::uuid IS NULL OR d.category_id = $3)
ORDER BY dc.embedding <=> $1
LIMIT 10;
```

#### Reranker

**Model: Cross-encoder**

**Vai tr├▓ cß╗ºa Reranker trong Pipeline:**

Reranker l├á b╞░ß╗¢c **cuß╗æi c├╣ng** tr╞░ß╗¢c khi ─æ╞░a context v├áo LLM. N├│ nhß║¡n ─æß║ºu v├áo l├á Top-20 chunks tß╗½ RRF v├á trß║ú vß╗ü Top-5 chunks chß║Ñt l╞░ß╗úng nhß║Ñt.

```
Query ΓåÆ [Dense Search] ΓåÆ Top-50
      ΓåÆ [Sparse Search] ΓåÆ Top-50  
      ΓåÆ [RRF Fusion] ΓåÆ Top-20  ΓåÉ Nhanh, recall cao
      ΓåÆ [Cross-encoder Reranker] ΓåÆ Top-5  ΓåÉ Ch├¡nh x├íc, precision cao
      ΓåÆ LLM ΓåÆ Answer
```

**Tß║íi sao cß║ºn Reranker?**

Vector search (Dense + Sparse) tß╗æt trong viß╗çc **recall** - t├¼m tß║Ñt cß║ú documents li├¬n quan. Tuy nhi├¬n, ch├║ng d├╣ng approximate nearest neighbor n├¬n ranking kh├┤ng ho├án hß║úo.

Reranker d├╣ng **cross-encoder** ─æß╗â:
- ─É├ính gi├í ch├¡nh x├íc h╞ín mß╗⌐c ─æß╗Ö relevance giß╗»a query v├á tß╗½ng document
- Ph├ón biß╗çt ─æ╞░ß╗úc subtle differences (VD: "remote work" vs "remote sensing")
- ─É╞░a ra final ranking ch├¡nh x├íc h╞ín

**Cross-encoder vs Bi-encoder:**

| Aspect | Bi-encoder (Retrieval) | Cross-encoder (Reranking) |
|--------|------------------------|----------------------------|
| **C├ích hoß║ít ─æß╗Öng** | Query ΓåÆ Vector, Doc ΓåÆ Vector ri├¬ng | Query + Doc ΓåÆ Vector CHUNG |
| **Tß╗æc ─æß╗Ö** | Nhanh (1 forward pass mß╗ùi c├íi) | Chß║¡m (N forward passes) |
| **─Éß╗Ö ch├¡nh x├íc** | Tß╗æt cho retrieval | Xuß║Ñt sß║»c cho ranking |
| **Tr╞░ß╗¥ng hß╗úp d├╣ng** | Chß╗ìn nhanh Top-k candidates | Final ranking |
| **So s├ính** | Cosine similarity gi├ín tiß║┐p | Direct pairwise scoring |

**V├¡ dß╗Ñ thß╗▒c tß║┐:**

Query: "ch├¡nh s├ích l├ám viß╗çc tß╗½ xa"

| Chunk | RRF Score | Cross-encoder Score | Final Rank |
|-------|-----------|---------------------|------------|
| "Working from home policy 2026" | 0.028 | 0.95 | **1** |
| "Remote sensing technology" | 0.025 | 0.12 | 4 |
| "WFH guidelines HR department" | 0.027 | 0.89 | **2** |

ΓåÆ RRF xß║┐p hß║íng tß║Ñt cß║ú gß║ºn nh╞░ ngang nhau, nh╞░ng cross-encoder ph├ón biß╗çt ─æ╞░ß╗úc "remote work" Γëá "remote sensing".

**Cross-encoder hoß║ít ─æß╗Öng thß║┐ n├áo?**

```python
# Input: [Query, Document] ─æ╞░ß╗úc gh├⌐p lß║íi th├ánh 1 chuß╗ùi
input_text = "[CLS] ch├¡nh s├ích l├ám viß╗çc tß╗½ xa [SEP] Working from home policy 2026 [SEP]"

# Cross-encoder encode C├ÖNG L├ÜC cß║ú query v├á doc
# ΓåÆ C├│ thß╗â hß╗ìc ─æ╞░ß╗úc interactions giß╗»a query terms v├á doc terms
score = cross_encoder(input_text)  # Output: 0.95
```

Kh├íc vß╗¢i bi-encoder chß╗ë so s├ính 2 vectors ri├¬ng lß║╗, cross-encoder **thß║Ñy ─æ╞░ß╗úc** query v├á doc t╞░╞íng t├íc vß╗¢i nhau nh╞░ thß║┐ n├áo.

**Lß╗úi ├¡ch cß╗ºa Reranker cho Poliwise:**

1. **Precision cho policy queries**: Khi user hß╗Åi "remote work", ─æß║úm bß║úo documents vß╗ü "work from home policy" xß║┐p hß║íng cao h╞ín "remote sensing"
2. **Department filtering**: C├│ thß╗â ╞░u ti├¬n documents tß╗½ department cß╗ºa user
3. **Freshness bias**: C├│ thß╗â incorporate ─æß╗Ö mß╗¢i cß╗ºa document v├áo ranking

**Code implementation:**

```python
# services/ai-qa-service/src/services/retrieval/reranker.py
class RerankerService:
    """
    Cross-encoder reranking ─æß╗â cß║úi thiß╗çn precision.
    
    Flow: Top-50 candidates ΓåÆ Cross-encoder rerank ΓåÆ Top-5 final
    """
    
    async def rerank(
        self,
        query: str,
        chunks: list[RetrievalChunk],
        limit: int = 5
    ) -> list[RetrievalChunk]:
        """
        Rerank chunks sß╗¡ dß╗Ñng cross-encoder model.
        
        Cross-encoder t├¡nh relevance score cho tß╗½ng cß║╖p query-document
        bß║▒ng c├ích xß╗¡ l├╜ ch├║ng c├╣ng nhau, capture ─æ╞░ß╗úc interactions
        giß╗»a query terms v├á document terms.
        """
        if not chunks or not self.enabled:
            return chunks[:limit]
        
        # Gß╗ìi external reranker service (Cohere, Jina, v.v.)
        response = await self.client.post(
            f"{self.reranker_url}/rerank",
            json={
                "query": query,
                "texts": [chunk.content for chunk in chunks],
                "truncate": True
            }
        )
        
        results = response.json()
        
        # Sß║»p xß║┐p lß║íi chunks dß╗▒a tr├¬n reranker scores
        ranked = sorted(results, key=lambda x: x["score"], reverse=True)
        
        for r in ranked:
            idx = r["index"]
            chunks[idx].similarity_score = r["score"]
        
        return chunks[:limit]
```

#### Knowledge Gap Detector

Kiß╗âm tra xem retrieved chunks c├│ ─æß╗º relevant kh├┤ng ─æß╗â trß║ú lß╗¥i c├óu hß╗Åi:

```python
# services/ai-qa-service/src/services/knowledge_gap.py
class KnowledgeGapDetector:
    """
    Evaluates if the retrieved context is sufficient to answer the query.
    
    Uses semantic similarity from top retrieved chunk.
    Threshold configured via settings.similarity_threshold (default: 0.15)
    """
    
    def __init__(self):
        self.threshold = settings.similarity_threshold  # 0.15
    
    async def evaluate(
        self,
        query: str,
        retrieved_chunks: list[RetrievalChunk]
    ) -> UnansweredQuestionResult:
        if not retrieved_chunks:
            return UnansweredQuestionResult(
                is_unanswered=True,
                reason="no_chunks_retrieved",
                top_similarity=0.0
            )
        
        top_similarity = retrieved_chunks[0].similarity_score
        
        if top_similarity < self.threshold:
            return UnansweredQuestionResult(
                is_unanswered=True,
                reason="low_relevance",
                top_similarity=top_similarity,
                search_query=query,
                priority=self._determine_priority(top_similarity)
            )
        
        return UnansweredQuestionResult(
            is_unanswered=False,
            top_similarity=top_similarity
        )
```

**Action on gap detection:**

| Similarity | Confidence | Action |
|-----------|------------|--------|
| < 0.4 | LOW | Mark as UNANSWERED, publish event |
| 0.4 - 0.7 | MEDIUM | Answer vß╗¢i medium confidence |
| ΓëÑ 0.7 | HIGH | Normal answer |

#### LLM Generation

**Model: Configurable (Llama/Qwen via Groq API)**

```python
# services/ai-qa-service/src/services/generation/llm_client.py
class LLMClient:
    """
    LLM client for answer generation with streaming support.
    """
    
    async def generate_streaming(
        self,
        messages: list[ChatMessage],
        model_id: str,
        temperature: float = 0.3,
        max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response from LLM.
        
        Settings:
        - temperature=0.3: Lower hallucination risk
        - max_tokens=1024: Prevent overly long responses
        """
        async for chunk in self.groq_client.chat.completions.create(
            model=model_id,
            messages=[m.to_dict() for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        ):
            yield chunk.choices[0].delta.content or ""
```

**Prompt structure for RAG:**

```python
SYSTEM_PROMPT = """Bß║ín l├á trß╗ú l├╜ AI chuy├¬n vß╗ü v─ân bß║ún ch├¡nh s├ích cß╗ºa c├┤ng ty.
Chß╗ë trß║ú lß╗¥i dß╗▒a tr├¬n ngß╗» cß║únh ─æ╞░ß╗úc cung cß║Ñp. Nß║┐u kh├┤ng chß║»c chß║»n, h├úy n├│i r├╡.

Quy tß║»c:
1. Trß║ú lß╗¥i bß║▒ng tiß║┐ng Viß╗çt, trß╗½ khi user hß╗Åi bß║▒ng tiß║┐ng Anh
2. Tr├¡ch dß║½n nguß╗ôn khi c├│ thß╗â (ti├¬u ─æß╗ü document)
3. Kh├┤ng bß╗ïa ─æß║╖t th├┤ng tin
4. Nß║┐u ngß╗» cß║únh kh├┤ng ─æß╗º, n├│i r├╡ "T├┤i kh├┤ng t├¼m thß║Ñy th├┤ng tin trong t├ái liß╗çu"
"""

USER_PROMPT = """Ngß╗» cß║únh tß╗½ t├ái liß╗çu:
{context}

C├óu hß╗Åi cß╗ºa user: {query}

Trß║ú lß╗¥i:"""
```

### 2.3 Data Flow Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant AG as API Gateway
    participant AI as AI-QA Service
    participant G as Groq API
    participant PV as pgvector
    participant RR as Reranker
    participant LLM as LLM

    U->>F: Gß╗¡i c├óu hß╗Åi
    F->>AG: POST /api/v1/ai/chat/stream
    AG->>AI: Forward request (JWT validated)
    
    rect rgb(200, 230, 200)
        Note over AI,G: Layer 1 + Layer 2 (Parallel)
        AI->>AI: Toxic Filter (Rule-based)
        AI->>G: Intent Classification
        G-->>AI: SIMPLE/COMPLEX
    end
    
    alt SIMPLE
        AI->>G: Direct response request
        G-->>AI: Response text
        AI->>AI: Save to DB
    else COMPLEX
        rect rgb(200, 200, 240)
            Note over AI,PV: Layer 3 Pipeline
            AI->>AI: Query Refinement
            AI->>PV: Vector search (BGE-M3)
            PV-->>AI: Top-50 chunks
            AI->>RR: Rerank chunks
            RR-->>AI: Top-5 ranked chunks
            AI->>AI: Knowledge Gap Detection
        end
        
        AI->>AI: Build prompt with context
        AI->>LLM: Streaming generation
        LLM-->>AI: Token by token
    end
    
    AI-->>F: SSE Stream
    F-->>U: Real-time display
```

---

## 3. Violations Flow

### 3.1 Tß╗òng quan

```mermaid
flowchart TD
    A[User gß╗¡i toxic query] --> B[Layer 1 Content Guard]
    B -->|Detected| C[ViolationPublisher]
    C --> D[RabbitMQ Exchange]
    D --> E[violation.layer1 queue]
    E --> F[ViolationConsumer]
    F --> G[ViolationService]
    
    G --> H[Log to analytics.violations - planned]
    H --> I[Increment User strike_count]
    
    I --> J{Strike count?}
    J -->|1-2| K[No action yet]
    J -->|3+| L[Send Warning to user]
    J -->|5+| M[Deactivate Account]
    J -->|10+| N[Revoke Account permanently]
    
    L --> O[Admin notified]
    M --> O
    N --> O
```

### 3.2 Violation Types

| Type | Label | Description | Severity |
|------|-------|-------------|----------|
| `TOXIC_QUERY` | C├óu hß╗Åi ─æß╗Öc hß║íi | Queries containing harmful/offensive content | Varies |
| `ABUSE` | Lß║ím dß╗Ñng | Personal attacks, harassment | HIGH |
| `SPAM` | Spam | Repetitive, nonsensical content | LOW |
| `JAILBREAK` | Prompt injection | Attempts to bypass AI safety | CRITICAL |
| `INJECTION` | Code injection | Malicious code/commands | CRITICAL |

**Severity mapping:**

| Severity | Strike Weight | Example |
|----------|---------------|---------|
| LOW | 1 | Spam, minor toxicity |
| MEDIUM | 2 | Abuse, harassment |
| HIGH | 3 | Jailbreak attempts |
| CRITICAL | 5 | Code injection |

### 3.3 Strike Escalation

```mermaid
flowchart LR
    subgraph Escalation["Strike Escalation Path"]
        S1[1-2 strikes] --> S2[3+ strikes]
        S2 --> S3[5+ strikes]
        S3 --> S4[10+ strikes]
    end
    
    subgraph Actions["Actions at each threshold"]
        S1 --> A1[Normal operation]
        S2 --> A2[Warning notification]
        S3 --> A3[Account deactivated]
        S4 --> A4[Account revoked]
    end
```

**Threshold details:**

| Strikes | Action | User Impact | Admin Notification |
|---------|--------|-------------|-------------------|
| 1-2 | No action | None | None |
| 3 | Warning | Warning banner displayed | Γ£à Notified |
| 5 | Deactivate | Cannot login until reactivated | Γ£à Notified |
| 10 | Revoke | Account permanently closed | Γ£à Notified |

### 3.4 Admin Actions

Admin c├│ thß╗â xß╗¡ l├╜ violations theo nhiß╗üu c├ích:

| Action | Description | Effect on Strikes |
|--------|-------------|------------------|
| `DISMISSED` | False positive | -1 strike |
| `WARNED` | Issue formal warning | No change |
| `NOTED` | Acknowledge without action | No change |
| `DEACTIVATED` | Deactivate user account | N/A |
| `REVOKED` | Permanently revoke access | N/A |

---

## 4. Architecture Summary

### 4.1 System Overview

```mermaid
flowchart TB
    subgraph Frontend
        W[Next.js Web App]
    end
    
    subgraph Gateway
        AG[API Gateway :3001]
    end
    
    subgraph Services
        AS[Auth Service :8081]
        US[User Service :8082]
        KS[Knowledge Service :8083]
        MS[Metadata Service :8084]
        FS[Feedback Service :8085]
        AIQ[AI-QA Service :8086]
        ING[Ingestion Service :8088]
    end
    
    subgraph External
        GROQ[Groq API]
        MINIO[MinIO Storage]
    end
    
    subgraph Data
        PG[(PostgreSQL)]
        PV[(pgvector)]
        RMQ[RabbitMQ]
    end
    
    W --> AG
    AG --> AS
    AG --> US
    AG --> KS
    AG --> MS
    AG --> AIQ
    
    KS --> PG
    AIQ --> PG
    AIQ --> PV
    AIQ --> GROQ
    
    ING --> KS
    ING --> PG
    ING --> PV
    ING --> MINIO
    
    FS --> PG
    FS --> RMQ
    
    RMQ --> ING
    RMQ --> FS
```

### 4.2 Data Flow Summary

| Flow | Start | End | Key Components |
|------|-------|-----|----------------|
| Document Upload | User | MinIO + pgvector | Frontend ΓåÆ Gateway ΓåÆ Knowledge ΓåÆ Ingestion |
| AI Chat | User | SSE Response | Frontend ΓåÆ Gateway ΓåÆ AI-QA ΓåÆ Groq ΓåÆ pgvector |
| Violation Handling | Toxic Query | Admin Notification | AI-QA ΓåÆ RabbitMQ ΓåÆ Feedback ΓåÆ Admin |

---

## Files tham chiß║┐u

| Component | File Path |
|-----------|-----------|
| **Frontend** | |
| Upload Modal | `frontend/web/components/documents/UploadModal.tsx` |
| Document Service | `frontend/web/services/document.service.ts` |
| Chat Container | `frontend/web/components/chat/ChatContainer.tsx` |
| **AI-QA Service** | |
| Pipeline Orchestrator | `services/ai-qa-service/src/services/pipeline/pipeline_orchestrator.py` |
| Toxic Filter | `services/ai-qa-service/src/services/pipeline/layer1_toxic_filter.py` |
| Intent Classifier | `services/ai-qa-service/src/services/pipeline/layer2_intent_classifier.py` |
| Query Refiner | `services/ai-qa-service/src/services/pipeline/query_refiner.py` |
| Hybrid Search | `services/ai-qa-service/src/services/retrieval/hybrid_search.py` |
| Reranker | `services/ai-qa-service/src/services/retrieval/reranker.py` |
| LLM Client | `services/ai-qa-service/src/services/generation/llm_client.py` |
| Violation Publisher | (planned, not implemented) |
| **Ingestion Service** | |
| Pipeline | `services/ingestion-service/src/services/pipeline.py` |
| Embedding Service | `services/ingestion-service/src/services/embedding_service.py` |
| Deduplicator | `services/ingestion-service/src/services/deduplicator.py` |
| Chunker | `services/ingestion-service/src/services/chunker.py` |
| **Knowledge Service** | |
| Document Management | `services/knowledge-service/src/main/java/com/poliwise/knowledge/service/DocumentManagementService.java` |
| **Feedback Service** | |
| Violation Consumer | (planned, not implemented) |
| Violation Service | (planned, not implemented) |
| Escalation Checker | (planned, not implemented) |
