import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Patch,
  Req,
  Res,
  UseGuards,
  HttpCode,
  HttpStatus,
  All,
  Head,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { ProxyService, ServiceName } from './proxy.service';
import { JwtAuthGuard, RolesGuard } from '../common/guards';
import { Roles, Public } from '../common/decorators';
import { UserRole } from '../common/interfaces';

/** Path + query: dùng request.path (không gồm ?) để ghép URL downstream đúng. */
function downstreamDocumentsPath(request: Request): string {
  const relative = request.path.replace(/^\/api\/v1\/documents/, '') || '/';
  return '/api/v1/documents' + (relative === '/' ? '' : relative);
}

/** Tách prefix gateway, giữ nguyên /api/v1/service-prefix/... cho downstream. */
function downstreamPath(request: Request, prefix: string): string {
  const relative = request.path.replace(new RegExp(`^${prefix}`), '') || '/';
  return `${prefix}${relative === '/' ? '' : relative}`;
}

@Controller('api/v1')
export class ProxyController {
  constructor(private readonly proxyService: ProxyService) {}

  // ===== Department Management Endpoints (Admin only) =====
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('departments')
  @Roles(UserRole.ADMIN)
  handleDepartmentsRoot(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/departments'),
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('departments/*path')
  @Roles(UserRole.ADMIN)
  handleDepartmentsNested(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/departments'),
    );
  }

  // ===== User "me" endpoints (authenticated self-service — route to user-service for profile data) =====
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('users/me')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleUserMeGet(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      '/api/v1/users/me',
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @Put('users/me')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleUserMePut(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      '/api/v1/users/me',
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('users/me/status')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleUserMeStatus(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      '/api/v1/users/me/status',
    );
  }

  // ===== User Management Endpoints =====

  /** GET /users — list/search users → user-service (returns department info) */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('users')
  @Roles(UserRole.ADMIN)
  handleUsersList(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** POST /users — create user → auth-service (handles registration + credentials) */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('users')
  @Roles(UserRole.ADMIN)
  handleUsersCreate(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.AUTH,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** GET /users/:id — get user detail → user-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('users/:id')
  @Roles(UserRole.ADMIN)
  handleUserGet(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** PUT /users/:id — update user → user-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Put('users/:id')
  @Roles(UserRole.ADMIN)
  handleUserUpdate(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** DELETE /users/:id — soft-delete user → user-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Delete('users/:id')
  @Roles(UserRole.ADMIN)
  handleUserDelete(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** PATCH /users/:id/status — change status → user-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Patch('users/:id/status')
  @Roles(UserRole.ADMIN)
  handleUserStatus(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** POST /users/:id/deactivate — convenience alias → user-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('users/:id/deactivate')
  @Roles(UserRole.ADMIN)
  handleUserDeactivate(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** POST /users/:id/reactivate — convenience alias → user-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('users/:id/reactivate')
  @Roles(UserRole.ADMIN)
  handleUserReactivate(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** POST /users/:id/revoke — convenience alias → user-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('users/:id/revoke')
  @Roles(UserRole.ADMIN)
  handleUserRevoke(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** POST /users/bulk — bulk create → auth-service */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('users/bulk')
  @Roles(UserRole.ADMIN)
  handleUsersBulkCreate(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.AUTH,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** Get login history for a specific user — accessible by the user themselves */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('users/:userId/login-history')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleLoginHistory(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.AUTH,
      request,
      downstreamPath(request, '/api/v1/users'),
    );
  }

  /** Get login stats for dashboard — MANAGER/ADMIN only */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('auth/login-stats')
  @Roles(UserRole.MANAGER, UserRole.ADMIN)
  handleLoginStats(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.AUTH,
      request,
      downstreamPath(request, '/api/v1/auth'),
    );
  }

  // ===== Document Management Endpoints =====
  
  /** List documents with pagination, search, and filters */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('documents')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleDocumentsRoot(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.KNOWLEDGE,
      request,
      downstreamDocumentsPath(request),
    );
  }

  /** Upload new document (ADMIN only) */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('documents/upload')
  @Roles(UserRole.ADMIN)
  @HttpCode(HttpStatus.OK)
  handleDocumentUpload(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.KNOWLEDGE,
      request,
      downstreamDocumentsPath(request),
    );
  }

  /** Confirm document metadata after upload (ADMIN only) */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('documents/:documentId/confirm')
  @Roles(UserRole.ADMIN)
  @HttpCode(HttpStatus.OK)
  handleDocumentConfirm(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.KNOWLEDGE,
      request,
      downstreamDocumentsPath(request),
    );
  }


  /** Serve document file for OnlyOffice Document Server.
   *  OnlyOffice DS downloads the file via this URL. No user auth is required — the request
   *  comes from the OnlyOffice DS container with a callback JWT token in the Authorization
   *  header. The gateway forwards it directly to knowledge-service (which handles auth). */
  @Public()
  @Get('documents/:documentId/file')
  handleDocumentFileDownload(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.KNOWLEDGE,
      request,
      downstreamDocumentsPath(request),
      false,
      true,
    );
  }

  @Public()
  @Head('documents/:documentId/file')
  handleDocumentFileHead(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.KNOWLEDGE,
      request,
      downstreamDocumentsPath(request),
      false,
      true,
    );
  }

  /** Document CRUD operations (get detail, delete, etc.) */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('documents/*path')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleDocumentsNested(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.KNOWLEDGE,
      request,
      downstreamDocumentsPath(request),
    );
  }

  // ===== Categories Endpoints =====

  /** Get all categories (active only, no auth required for public use) */
  @Get('categories/active')
  handlePublicCategories(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/categories/active',
    );
  }

  /** Get category tree (hierarchical structure) */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('categories/active/tree')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleCategoriesActiveTree(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/categories/active/tree',
    );
  }

  /** Get category children by parent ID */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('categories/active/children')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleCategoriesActiveChildren(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/categories/active/children' + (request.url.includes('?') ? request.url.substring(request.url.indexOf('?')) : ''),
    );
  }

  /** Admin category management endpoints */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('categories')
  @Roles(UserRole.ADMIN)
  handleCategoriesAdmin(@Req() request: Request) {
    const relative = request.path.replace(/^\/api\/v1\/categories/, '') || '/';
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/categories' + (relative === '/' ? '' : relative),
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('categories/*path')
  @Roles(UserRole.ADMIN)
  handleCategoriesAdminNested(@Req() request: Request) {
    const relative = request.path.replace(/^\/api\/v1\/categories/, '') || '/';
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/categories' + (relative === '/' ? '' : relative),
    );
  }

  // ===== Tags Endpoints =====

  /** Get all tags */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('tags')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleTagsGet(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/tags',
    );
  }

  /** Get popular tags */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('tags/popular')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleTagsPopular(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/tags/popular',
    );
  }

  /** Search tags */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('tags/search')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleTagsSearch(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/tags/search' + (request.url.includes('?') ? request.url.substring(request.url.indexOf('?')) : ''),
    );
  }

  /** Resolve tags (find-or-create) - ADMIN/MANAGER only */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('tags/resolve')
  @Roles(UserRole.ADMIN, UserRole.MANAGER)
  @HttpCode(HttpStatus.OK)
  handleTagsResolve(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/tags/resolve',
    );
  }

  /** Tag CRUD operations (ADMIN only for create/update/delete) */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('tags')
  @Roles(UserRole.ADMIN)
  handleTagsAdmin(@Req() request: Request) {
    const relative = request.path.replace(/^\/api\/v1\/tags/, '') || '/';
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/tags' + (relative === '/' ? '' : relative),
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('tags/*path')
  @Roles(UserRole.ADMIN)
  handleTagsAdminNested(@Req() request: Request) {
    const relative = request.path.replace(/^\/api\/v1\/tags/, '') || '/';
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/tags' + (relative === '/' ? '' : relative),
    );
  }

  // ===== Metadata Endpoints =====

  /** Document metadata CRUD - ADMIN only */
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('metadata')
  @Roles(UserRole.ADMIN)
  handleMetadataRoot(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/metadata',
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('metadata/*path')
  @Roles(UserRole.ADMIN)
  handleMetadata(@Req() request: Request) {
    const path = request.path;
    let downstream: string;

    if (path.startsWith('/api/v1/metadata/categories')) {
      const relative = path.replace(/^\/api\/v1\/metadata\/categories/, '') || '/';
      downstream = `/api/v1/categories${relative === '/' ? '' : relative}`;
    } else if (path.startsWith('/api/v1/metadata/tags')) {
      const relative = path.replace(/^\/api\/v1\/metadata\/tags/, '') || '/';
      downstream = `/api/v1/tags${relative === '/' ? '' : relative}`;
    } else {
      const relative = path.replace(/^\/api\/v1\/metadata/, '') || '/';
      downstream = `/api/v1/metadata${relative === '/' ? '' : relative}`;
    }

    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      downstream,
    );
  }

  // ===== Access Rules Endpoints =====
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('access-rules')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleAccessRulesRoot(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/access-rules' + (request.url.includes('?') ? request.url.substring(request.url.indexOf('?')) : ''),
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('access-rules/*path')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleAccessRules(@Req() request: Request) {
    const relative = request.path.replace(/^\/api\/v1\/access-rules/, '') || '/';
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      '/api/v1/access-rules' + (relative === '/' ? '' : relative) + (request.url.includes('?') && !request.url.includes(relative) ? request.url.substring(request.url.indexOf('?')) : ''),
    );
  }

  // Simulation endpoint — check who has access to a document (ADMIN only)
  @Get('access-rules/simulation/by-document/:documentId')
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Roles(UserRole.ADMIN)
  handleAccessRuleSimulation(@Req() request: Request) {
    const documentId = (request.params as Record<string, string>).documentId;
    return this.proxyService.forward(
      ServiceName.METADATA,
      request,
      `/api/v1/access-rules/simulation/by-document/${documentId}`,
    );
  }

  // ===== Feedback Endpoints =====
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('feedback/*path')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleFeedback(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.FEEDBACK,
      request,
      downstreamPath(request, '/api/v1/feedback'),
    );
  }

  // ===== Reports Endpoints (export/reports) — route to feedback-service =====
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('reports')
  @Roles(UserRole.MANAGER, UserRole.ADMIN)
  handleReportsRoot(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.FEEDBACK,
      request,
      '/api/v1/reports' + (request.url.includes('?') ? request.url.substring(request.url.indexOf('?')) : ''),
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('reports/*path')
  @Roles(UserRole.MANAGER, UserRole.ADMIN)
  handleReportsNested(@Req() request: Request) {
    const relative = request.path.replace(/^\/api\/v1\/reports/, '') || '/';
    return this.proxyService.forward(
      ServiceName.FEEDBACK,
      request,
      '/api/v1/reports' + (relative === '/' ? '' : relative),
    );
  }

  // ===== Analytics Endpoints =====
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('analytics/*path')
  @Roles(UserRole.MANAGER, UserRole.ADMIN)
  handleAnalytics(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.FEEDBACK,
      request,
      downstreamPath(request, '/api/v1/analytics'),
    );
  }

  // AI Q&A endpoints — route to ai-qa-service
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('ai/unanswered')
  @Roles(UserRole.MANAGER, UserRole.ADMIN)
  handleAIUnansweredList(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.FEEDBACK,
      request,
      '/api/v1/dashboard/unanswered' + (request.url.includes('?') ? request.url.substring(request.url.indexOf('?')) : ''),
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @Put('ai/unanswered/:id/resolve')
  @Roles(UserRole.MANAGER, UserRole.ADMIN)
  handleAIUnansweredResolve(@Req() request: Request) {
    const id = (request.params as Record<string, string>).id;
    return this.proxyService.forward(
      ServiceName.FEEDBACK,
      request,
      `/api/v1/dashboard/unanswered/${id}/resolve`,
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @Put('ai/unanswered/:id/reject')
  @Roles(UserRole.MANAGER, UserRole.ADMIN)
  handleAIUnansweredReject(@Req() request: Request) {
    const id = (request.params as Record<string, string>).id;
    return this.proxyService.forward(
      ServiceName.FEEDBACK,
      request,
      `/api/v1/dashboard/unanswered/${id}/reject`,
    );
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('ai/chat/stream')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleAIStream(@Req() request: Request, @Res() response: Response) {
    const path = '/chat/stream';
    this.proxyService.forward(ServiceName.AI_QA, request, path, true).subscribe({
      next: (proxied: any) => {
        if (proxied && proxied._proxied) {
          response.status(proxied.statusCode ?? 200);
          for (const [key, value] of Object.entries(proxied.headers || {})) {
            response.setHeader(key, value as string);
          }
          if (proxied.data && typeof proxied.data.pipe === 'function') {
            proxied.data.pipe(response);
          } else {
            response.end(proxied.data);
          }
        }
      },
      error: (err) => {
        response.status(500).json({ success: false, error: err.message });
      }
    });
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('ai/*path')
  @Roles(UserRole.USER, UserRole.MANAGER, UserRole.ADMIN)
  handleAI(@Req() request: Request) {
    const path = request.url.replace('/api/v1/ai', '');
    const isStream = path.includes('/stream');
    return this.proxyService.forward(ServiceName.AI_QA, request, path, isStream);
  }

  // Ingestion endpoints — route to ingestion-service
  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('ingest')
  @Roles(UserRole.ADMIN)
  @HttpCode(HttpStatus.ACCEPTED)
  handleIngest(@Req() request: Request) {
    const path = request.url.replace('/api/v1', '');
    return this.proxyService.forward(ServiceName.INGESTION, request, path);
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @Get('ingest/:jobId/status')
  @Roles(UserRole.ADMIN)
  handleIngestStatus(@Req() request: Request) {
    const path = request.url.replace('/api/v1', '');
    return this.proxyService.forward(ServiceName.INGESTION, request, path);
  }

  @UseGuards(JwtAuthGuard, RolesGuard)
  @Post('ingest/:docId/reindex')
  @Roles(UserRole.ADMIN)
  handleReindex(@Req() request: Request) {
    const path = request.url.replace('/api/v1', '');
    return this.proxyService.forward(ServiceName.INGESTION, request, path);
  }

  // Admin endpoints
  @UseGuards(JwtAuthGuard, RolesGuard)
  @All('admin/*path')
  @Roles(UserRole.ADMIN)
  handleAdmin(@Req() request: Request) {
    return this.proxyService.forward(
      ServiceName.USER,
      request,
      downstreamPath(request, '/api/v1/admin'),
    );
  }
}
