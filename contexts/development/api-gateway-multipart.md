# API Gateway Bypass for Multipart Uploads

## Overview
As of Phase 1, the frontend application (`web-service`) bypasses the `api-gateway` (Port 3000) and communicates directly with the `knowledge-service` (Port 8083) for the following operations:
1. **Document Upload**: `POST /api/v1/documents`
2. **Metadata Confirmation**: `POST /api/v1/documents/{id}/confirm`
3. **Upload Cancellation**: `DELETE /api/v1/documents/{id}/cancel`

## Rationale
The primary reason for this bypass is the handling of `multipart/form-data` and raw request streams. 

1. **Gateway Stream Consumption**: The `api-gateway` (built with NestJS/Express) uses middleware that often consumes or attempts to parse the request body. For large file uploads, proxying multipart data through an intermediate Node.js gateway can lead to:
   - High memory consumption on the gateway.
   - Timeout issues due to synchronous proxying of large streams.
   - Complexities in boundary parsing between the gateway and internal services.
2. **Bypass Implementation**: In `frontend/web/lib/api.ts`, the `ksUrl` logic checks for the environment and routes directly to the service:
   ```typescript
   const ksUrl = typeof window === 'undefined' 
     ? 'http://knowledge-service:8083' 
     : 'http://localhost:8083';
   ```

## Future Considerations
If we decide to consolidate all traffic through the gateway in Phase 2:
- Implement a dedicated Node.js stream-aware proxy (e.g., using `http-proxy` with proper events).
- Configure `multer` on the gateway only if we need to perform logic (like virus scanning) at the edge.
- Ensure the gateway forwards Authorization headers correctly (already implemented in current bypass).

## Reference
- **Frontend Code**: [api.ts](file:///c:/Users/Tien/university/TTCS/do_an_cuoi_ky/Poliwise/frontend/web/lib/api.ts)
- **Knowledge Service**: [DocumentController.java](file:///c:/Users/Tien/university/TTCS/do_an_cuoi_ky/Poliwise/services/knowledge-service/src/main/java/com/poliwise/knowledge/controller/DocumentController.java)
