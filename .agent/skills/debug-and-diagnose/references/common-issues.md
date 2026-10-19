# SOPilot Common Issues & Resolutions

This is a living document of known issues, symptoms, root causes, and resolutions specific to the SOPilot tech stack.

## 1. Database Connection Pool Exhaustion
**Symptoms:** 500 Internal Server Errors, "Timeout: Pool empty", or "Sorry, too many clients already".
**Root Cause:** 
- Spring Boot (HikariCP) or Python (asyncpg) holds connections too long or leaks them.
- `max_connections` in PostgreSQL is set too low for 6 microservices.
**Resolution:** Increase `maximumPoolSize` in Spring Boot `application.yml` slightly. Ensure transactions are short-lived. Increase `max_connections` in postgresql.conf.
**Prevention:** Always use `@Transactional` correctly (read-only where applicable), close resources properly, and use PgBouncer if connections grow too large.

## 2. RabbitMQ Consumer Crashes & DLQ
**Symptoms:** Events stuck, unacked messages growing, DLQ filling up.
**Root Cause:** A consumer threw an unhandled exception (e.g., parsing error, network timeout), causing RabbitMQ to NACK and route to the Dead Letter Queue (DLX/DLQ).
**Resolution:** Inspect the DLQ payload via RabbitMQ Management UI (port 15672). Fix the consumer logic, then requeue messages from the DLQ.
**Prevention:** Add global exception handlers in consumers. Wrap parsing and API calls in try-catch/try-except blocks.

## 3. JWT Token Refresh Race Conditions
**Symptoms:** Occasional 401 Unauthorized errors in the frontend when multiple requests fire simultaneously just as the token expires.
**Root Cause:** Multiple concurrent requests attempt to use an expired token. One triggers a refresh, but others fail before the new token is stored.
**Resolution:** The frontend Axios interceptor must queue failed requests while a refresh is in progress, then retry them once the new token is acquired.
**Prevention:** Maintain a `isRefreshing` flag and a queue of pending requests in the frontend API client.

## 4. MinIO Presigned URL Expiration
**Symptoms:** Images/documents suddenly stop loading with XML AccessDenied errors.
**Root Cause:** The knowledge-service generates presigned URLs with a short expiration, and the frontend caches them or leaves them open too long.
**Resolution:** Re-request the presigned URL from the backend.
**Prevention:** Store the asset ID in the frontend, not the URL, and fetch fresh URLs when rendering, or proxy through the backend if security allows.

## 5. Docker Compose Network Issues
**Symptoms:** "Name or service not known" or "Connection refused" when services talk to each other.
**Root Cause:** Using `localhost` inside a Docker container instead of the service name (e.g., connecting to `localhost:5432` instead of `postgres:5432`).
**Resolution:** Update `.env` files to use Docker service names for inter-service communication.
**Prevention:** Differentiate `.env.local` (for host execution) vs `.env.docker` (for containerized execution).

## 6. pgvector HNSW Index Build Failures
**Symptoms:** High memory usage on PostgreSQL container, query timeouts, or index creation fails.
**Root Cause:** Building HNSW indexes requires `maintenance_work_mem` to be sufficiently high.
**Resolution:** Increase `maintenance_work_mem` in PostgreSQL config before creating the index.
**Prevention:** Build indexes concurrently or before large bulk inserts.

## 7. Python Async Event Loop Blocking
**Symptoms:** FastAPI service (ai-qa or ingestion) becomes completely unresponsive.
**Root Cause:** A synchronous, blocking library (e.g., heavy CPU processing, standard `requests` library) was used inside an `async def` route.
**Resolution:** Move synchronous blocking code to a thread pool using `run_in_executor` or `fastapi.concurrency.run_in_threadpool`, or switch to `def` (no async) if the whole route is blocking.
**Prevention:** Use `aiohttp` or `httpx` for async HTTP calls.

## 8. NestJS Circuit Breaker Tripping
**Symptoms:** API Gateway returns 503 Service Unavailable instantly without attempting to call the backend.
**Root Cause:** The backend service failed repeatedly, tripping the gateway's circuit breaker to protect the system.
**Resolution:** Check the health of the underlying backend service. Once healthy, the circuit breaker will half-open and then close automatically.
**Prevention:** Ensure backend services have proper fallback mechanisms and rate limiting.

## 9. CORS Issues Between Frontend & Gateway
**Symptoms:** Browser console shows "Blocked by CORS policy".
**Root Cause:** Gateway is not configured to allow the frontend's origin, or the preflight OPTIONS request failed.
**Resolution:** Ensure `api-gateway` CORS configuration allows `http://localhost:3000`.
**Prevention:** Centralize CORS configuration in the API Gateway.

## 10. Memory Issues with JVM Serial GC on Low-RAM VPS
**Symptoms:** Spring Boot containers get OOMKilled or experience severe GC pauses.
**Root Cause:** Serial GC is default on low-memory single-core containers, which can cause long stop-the-world pauses.
**Resolution:** explicitly set JVM flags: `-Xmx256m -Xms256m -XX:+UseG1GC`.
**Prevention:** Always define resource limits and JVM memory flags in `docker-compose.yml`.

## 11. Vietnamese Text Processing
**Symptoms:** `underthesea` tokenizer crashes or takes too long.
**Root Cause:** Unhandled special characters or extremely long sentences block the tokenizer.
**Resolution:** Pre-process text to remove control characters and split very long paragraphs before tokenization.
**Prevention:** Add input sanitization and length limits before NLP processing.

## 12. Large File Upload Timeouts
**Symptoms:** Uploads fail at 99%, or gateway returns 504 Gateway Timeout.
**Root Cause:** Gateway or Nginx proxy read timeouts are shorter than the time taken to stream the file to MinIO.
**Resolution:** Increase timeouts for multipart routes, or upload directly to MinIO via presigned POST URLs.
**Prevention:** Implement direct-to-S3/MinIO uploads for large files instead of proxying through the backend.

## 13. SSE/Streaming Connection Drops
**Symptoms:** AI streaming response cuts off mid-sentence.
**Root Cause:** Gateway timeout or frontend proxy (Next.js API route) buffering the response instead of streaming.
**Resolution:** Ensure Next.js API routes use `export const config = { runtime: 'edge' }` or disable response buffering.
**Prevention:** Test SSE connections with long-running simulated streams.
