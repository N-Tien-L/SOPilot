# Performance Antipatterns in SOPilot

## Java (Spring Boot)
- **N+1 JPA Queries**: Iterating over collections of entities that lazy-load relations. Use `@EntityGraph` or `JOIN FETCH` instead.
- **Missing Indexes**: Frequently queried columns (especially in `WHERE`, `ORDER BY`, or `JOIN` clauses) lacking DB indexes.
- **Blocking Event Handlers**: Performing synchronous, long-running tasks inside event consumer threads. Delegate to async execution or separate workers.

## Python (FastAPI)
- **Synchronous I/O in Async Context**: Using blocking libraries (like `requests` or synchronous DB drivers) inside `async def` endpoints, which blocks the whole event loop.
- **Unbatched Embedding Calls**: Making single-item API calls to embedding models (e.g., OpenAI) in a loop instead of batching them.
- **High Memory Footprint**: Loading full, massive documents into memory instead of streaming or chunking them appropriately.

## Frontend (Next.js & React)
- **Unnecessary Re-renders**: Passing new object/function references on every render. Missing `useMemo` or `useCallback` for expensive computations or stable props.
- **Large Bundle Imports**: Importing entire libraries instead of specific modules (e.g., `import { Icon } from 'lucide-react'` vs default imports if tree-shaking fails).
- **Missing React Query Cache**: Refetching static or semi-static data repeatedly instead of properly configuring `staleTime` and cache policies in React Query.

## Database (PostgreSQL & pgvector)
- **Full Table Scans**: Caused by missing indexes, incorrect data types in queries, or non-sargable conditions (`LIKE '%term%'`).
- **Missing Vector Indexes**: Not using HNSW or IVFFlat indexes on pgvector columns for similarity searches, leading to sequential scans on vectors.
- **Unoptimized GIN Indexes**: Missing or poorly configured GIN indexes for JSONB or array columns.

## Infrastructure
- **Missing Redis Caching**: Hitting the database for highly accessed, rarely changing configuration or master data (hot paths).
- **Synchronous Event Publishing**: Waiting for a synchronous HTTP call when a fire-and-forget message to RabbitMQ would be appropriate and faster.
