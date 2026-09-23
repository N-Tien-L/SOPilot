---
title: Frontend Architecture
description: Architecture and patterns for the Poliwise Next.js frontend
type: architecture
version: 1.0
---

# Frontend Architecture

## Overview

The Poliwise frontend is a **Next.js 16 App Router** application with TypeScript, using a layered architecture pattern with clear separation between UI components, API services, and state management.

## Directory Structure

```
frontend/web/
├── app/                        # Next.js App Router pages
│   ├── layout.tsx              # Root layout (server component)
│   ├── page.tsx               # Home page (AI Chat)
│   ├── login/                 # Login page
│   ├── register/             # Registration page
│   ├── documents/            # Document library
│   │   ├── page.tsx         # Document list
│   │   └── [id]/page.tsx    # Document detail
│   ├── profile/              # User profile
│   ├── analytics/            # Analytics dashboard (MANAGER+)
│   ├── sessions/             # Active sessions
│   └── admin/               # Admin panel (ADMIN only)
│       ├── layout.tsx        # Admin layout wrapper
│       ├── users/            # User management
│       ├── metadata/         # Categories, tags
│       ├── unanswered/       # Unanswered questions
│       ├── audit-logs/       # Audit logs
│       └── settings/         # System settings
├── components/               # React components
│   ├── ui/                   # Design system components
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Select.tsx
│   │   ├── Modal.tsx
│   │   ├── Table.tsx
│   │   ├── Badge.tsx
│   │   ├── Card.tsx
│   │   └── ...
│   ├── layout/               # Layout components
│   │   ├── MainLayout.tsx    # Main wrapper (header + sidebar + content)
│   │   ├── Header.tsx        # Top navigation
│   │   └── Sidebar.tsx       # Side navigation
│   ├── chat/                 # Chat-related components
│   │   ├── ChatContainer.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── ChatInput.tsx
│   │   ├── ChatSidebar.tsx
│   │   ├── SourcesPanel.tsx
│   │   └── WelcomeScreen.tsx
│   └── documents/            # Document components
│       ├── UploadModal.tsx
│       ├── PreviewModal.tsx
│       ├── DocumentViewerModal.tsx
│       └── ...
├── services/                  # API client services
│   └── api-client.ts         # Axios instance with interceptors
├── lib/                      # Utilities
│   └── api.ts               # Centralized API client (typed namespaces)
├── store/                    # Zustand state stores
│   ├── auth-store.ts        # Authentication state
│   ├── ui-store.ts          # UI state
│   └── preferences-store.ts # User preferences
├── types/                    # Shared types
│   ├── auth.ts              # Auth types
│   ├── document.ts          # Document types
│   ├── ai.ts                # AI/chat types
│   ├── analytics.ts         # Analytics types
│   └── department.ts         # Department types
├── interfaces/               # Detailed model interfaces
│   ├── models/
│   │   ├── core/            # User, Department
│   │   ├── knowledge/       # Document, Chunk
│   │   ├── metadata/        # Category, Tag, AccessRule
│   │   └── analytics/       # Feedback, AuditLog
│   └── enums/
│       ├── core/            # UserRole, AccountStatus
│       ├── knowledge/        # ProcessingStatus
│       └── ...
├── providers/                # React context providers
│   ├── QueryProvider.tsx    # TanStack Query
│   ├── ThemeProvider.tsx    # Dark/light theme
│   └── LanguageProvider.tsx  # i18n
├── hooks/                    # Custom hooks
│   └── useChat.ts           # Chat-related hooks
└── lib/                     # Utilities
    ├── api.ts               # API client
    └── i18n.ts              # Internationalization
```

## Technology Stack

| Technology | Purpose |
|------------|---------|
| Next.js 16 (App Router) | Framework |
| React 19 | UI library |
| TypeScript 5.x (strict) | Type safety |
| Zustand 5.x | State management |
| TanStack Query | Server state / data fetching |
| CSS Modules | Styling |
| lucide-react | Icons |
| react-markdown + remark-gfm + rehype-raw | Markdown rendering (chat assistant bubbles, document viewer) |

## State Management

### Zustand Stores

The frontend uses **Zustand** for client-side state management with `persist` middleware for localStorage.

#### Auth Store

Location: `frontend/web/store/auth-store.ts`

```typescript
interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) =>
        set({ user, isAuthenticated: !!user }),

      setTokens: (accessToken, refreshToken) => {
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('refreshToken', refreshToken);
        set({ accessToken, refreshToken, isAuthenticated: true });
      },

      logout: () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
      },
    }),
    { name: 'auth-storage' }
  )
);

// Convenience hooks
export const useUser = () => useAuthStore((s) => s.user);
export const useIsAdmin = () => useAuthStore((s) => s.user?.role === 'ADMIN');
export const useIsManager = () => ['ADMIN', 'MANAGER'].includes(useAuthStore((s) => s.user?.role));
export const useUserRole = () => useAuthStore((s) => s.user?.role);
```

#### UI Store

```typescript
interface UIState {
  sidebarOpen: boolean;
  currentPage: string;
  isSourcesPanelOpen: boolean;
  activeMessageSources: SourceDocument[];
  activeDocumentViewer: { documentId: string; versionId?: string } | null;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  currentPage: 'chat',
  isSourcesPanelOpen: false,
  activeMessageSources: [],
  activeDocumentViewer: null,

  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSourcesPanelOpen: (open: boolean) => set({ isSourcesPanelOpen: open }),
  setActiveSources: (sources: SourceDocument[]) => set({ activeMessageSources: sources }),
}));
```

#### Preferences Store

```typescript
interface PreferencesState {
  theme: 'light' | 'dark';
  language: 'vi' | 'en';
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      theme: 'light',
      language: 'vi',
    }),
    { name: 'preferences-storage' }
  )
);
```

## API Client Architecture

### Two-Layer Design

The frontend uses a two-layer API client design:

1. **`services/api-client.ts`** - Low-level Axios instance
2. **`lib/api.ts`** - High-level typed API client

### Low-Level Client

Location: `frontend/web/services/api-client.ts`

```typescript
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001',
  timeout: 10000,
});

// Request interceptor: add Bearer token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401 → refresh → retry
// Uses semaphore pattern to prevent concurrent refresh loops
let isRefreshing = false;
const refreshSubscribers: Array<(token: string) => void> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue request until refresh completes
        return new Promise((resolve) => {
          refreshSubscribers.push((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(apiClient(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = localStorage.getItem('refreshToken');
        const { data } = await directClient.post('/auth/refresh', { refreshToken });
        const { accessToken, refreshToken: newRefresh } = data;

        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('refreshToken', newRefresh);

        // Retry queued requests
        onTokenRefreshed(accessToken);
        return apiClient(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().logout();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
```

### High-Level API Client

Location: `frontend/web/lib/api.ts` (~1880 lines)

```typescript
// Organized by domain with typed methods
export const api = {
  // Authentication
  auth: {
    login: (data: LoginRequest) => client.post<LoginResponse>('/auth/login', data),
    logout: (data: LogoutRequest) => client.post('/auth/logout', data),
    register: (data: RegisterRequest) => client.post('/auth/register', data),
    refresh: (data: RefreshTokenRequest) => client.post('/auth/refresh', data),
    me: () => client.get<User>('/auth/me'),
    changePassword: (data: ChangePasswordRequest) => client.post('/auth/change-password', data),
    forgotPassword: (data: ForgotPasswordRequest) => client.post('/auth/forgot-password', data),
    resetPassword: (data: ResetPasswordRequest) => client.post('/auth/reset-password', data),
    getSessions: () => client.get<Session[]>('/auth/sessions'),
    revokeSession: (sessionId: string) => client.delete(`/auth/sessions/${sessionId}`),
    revokeAllSessions: () => client.post('/auth/logout-all'),
  },

  // Users
  users: {
    list: (params?: UserSearchParams) =>
      client.get<PaginatedResponse<User>>('/users', { params }),
    getById: (id: string) => client.get<User>(`/users/${id}`),
    create: (data: CreateUserRequest) => client.post<User>('/users', data),
    update: (id: string, data: UpdateUserRequest) => client.put<User>(`/users/${id}`, data),
    delete: (id: string) => client.delete(`/users/${id}`),
    getLoginHistory: (userId: string, params?: PaginationParams) =>
      client.get(`/users/${userId}/login-history`, { params }),
  },

  // Documents
  documents: {
    list: (params?: DocumentSearchParams) =>
      client.get<PaginatedResponse<Document>>('/documents', { params }),
    getById: (id: string) => client.get<Document>(`/documents/${id}`),
    upload: (formData: FormData) =>
      client.post<DocumentUploadResponse>('/documents', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
    download: (id: string) =>
      client.get(`/documents/${id}/download`, { responseType: 'blob' }),
    getVersions: (id: string) =>
      client.get<DocumentVersion[]>(`/documents/${id}/versions`),
    compare: (params: CompareParams) =>
      client.post<CompareResponse>('/documents/compare', params),
  },

  // AI Chat
  ai: {
    ask: (data: QuestionRequest) =>
      client.post<QuestionResponse>('/ai/ask', data),
    askStream: (data: QuestionRequest) =>
      client.post('/ai/ask/stream', data, { responseType: 'stream' }),
    conversations: () =>
      client.get<Conversation[]>('/ai/conversations'),
    getMessages: (conversationId: string) =>
      client.get<Message[]>(`/ai/conversations/${conversationId}/messages`),
    deleteConversation: (id: string) =>
      client.delete(`/ai/conversations/${id}`),
    getModels: () => client.get<ModelInfo[]>('/ai/models'),
  },

  // Analytics
  analytics: {
    dashboard: () => client.get<DashboardStats>('/analytics/dashboard'),
    overview: () => client.get<AnalyticsOverview>('/analytics/overview'),
    topQuestions: (params?: TopQuestionsParams) =>
      client.get<TopQuestion[]>('/analytics/top-questions', { params }),
    topDocuments: (params?: TopDocsParams) =>
      client.get<TopDocument[]>('/analytics/top-documents', { params }),
    getUnanswered: (params?: PaginationParams) =>
      client.get<PaginatedResponse<UnansweredQuestion>>('/analytics/unanswered', { params }),
  },

  // Feedback
  feedback: {
    submit: (data: FeedbackRequest) => client.post('/feedback', data),
    list: (params?: FeedbackSearchParams) =>
      client.get<PaginatedResponse<Feedback>>('/feedback', { params }),
  },

  // Reports
  reports: {
    export: (format: ExportFormat, params?: ReportParams) =>
      client.post(`/reports/export?format=${format}`, params, { responseType: 'blob' }),
  },

  // Metadata
  metadata: {
    getCategories: () => client.get<Category[]>('/metadata/categories'),
    getTags: () => client.get<Tag[]>('/metadata/tags'),
    getAccessRules: (documentId: string) =>
      client.get<AccessRule[]>(`/metadata/documents/${documentId}/access-rules`),
  },

  // Departments
  departments: {
    list: () => client.get<Department[]>('/departments'),
    tree: () => client.get<DepartmentTreeNode[]>('/departments/tree'),
    create: (data: CreateDepartmentRequest) => client.post('/departments', data),
    update: (id: string, data: UpdateDepartmentRequest) =>
      client.put(`/departments/${id}`, data),
    delete: (id: string) => client.delete(`/departments/${id}`),
    assignUsers: (id: string, data: AssignUserDepartmentRequest) =>
      client.post(`/departments/${id}/users`, data),
  },
};
```

### Response Coercion

The API client handles multiple backend response formats:

```typescript
// Handles: { success: true, data: {...} }
// Also handles: Spring PageResponse { content, totalElements, totalPages }
// Also handles: flat responses

function coercePaginated<T>(response: unknown): PaginatedResponse<T> {
  const root = response as Record<string, unknown>;

  if ('content' in root && Array.isArray(root.content)) {
    // Spring PageResponse format
    return {
      data: root.content as T[],
      pagination: {
        page: (root.number as number) + 1, // Spring uses 0-indexed
        limit: root.size as number,
        total: root.totalElements as number,
        totalPages: root.totalPages as number,
      },
    };
  }

  // Handle wrapped format or throw
}
```

## Streaming Implementation

For AI chat streaming, the frontend uses `ReadableStream`:

```typescript
export async function* streamAIResponse(question: string, conversationId?: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/ai/ask/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
    },
    body: JSON.stringify({ question, conversationId }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (reader) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n').filter(Boolean);

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const event = JSON.parse(line.slice(6));

        switch (event.type) {
          case 'content':
            yield { type: 'content', text: event.text };
            break;
          case 'sources':
            yield { type: 'sources', sources: event.sources };
            break;
          case 'done':
            yield { type: 'done' };
            break;
          case 'error':
            throw new Error(event.message);
        }
      }
    }
  }
}
```

### Chat message rendering (markdown)

The assistant response stream emits raw markdown text (headings, lists, tables, inline code, etc.). `components/chat/ChatMessage.tsx` renders the assistant bubble body through `ReactMarkdown` with the same plugin set used by the document viewer:

```typescript
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

<ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
  {message.content}
</ReactMarkdown>
```

- User messages keep the plain `<p>` rendering (no markdown parsing) to preserve the right-aligned bubble styling.
- Assistant messages are wrapped in a `<div className="chat-markdown">`; prose styling (links, lists, code blocks, tables, blockquotes, hr) is scoped through `.chat-markdown` in `app/globals.css` so it never bleeds into `.doc-viewer-content` or other prose areas.
- The streaming cursor / 3-dot loader remains appended after the markdown body and disappears once `streamingCompleted` is true.
- `rehypeRaw` is included so any HTML the LLM emits (e.g. raw `<br/>`, table markup) still renders, matching the document viewer.

## RBAC in Components

### Role-Based Rendering

```typescript
'use client';

import { useAuthStore } from '@/store/auth-store';

export function AdminOnly({ children }: { children: React.ReactNode }) {
  const role = useAuthStore((s) => s.user?.role);

  if (role !== 'ADMIN') {
    return <AccessDeniedMessage />;
  }

  return <>{children}</>;
}

export function ManagerOrAdmin({ children }: { children: React.ReactNode }) {
  const role = useAuthStore((s) => s.user?.role);

  if (role !== 'ADMIN' && role !== 'MANAGER') {
    return null;
  }

  return <>{children}</>;
}
```

### Navigation Filtering

```typescript
const navigationItems = [
  { label: 'Trang chủ', href: '/', roles: ['USER', 'MANAGER', 'ADMIN'] },
  { label: 'Tài liệu', href: '/documents', roles: ['USER', 'MANAGER', 'ADMIN'] },
  { label: 'Phân tích', href: '/analytics', roles: ['MANAGER', 'ADMIN'] },
  { label: 'Quản trị', href: '/admin', roles: ['ADMIN'] },
];

export function SidebarNavigation() {
  const role = useAuthStore((s) => s.user?.role);

  const visibleItems = navigationItems.filter((item) =>
    item.roles.includes(role)
  );

  return (
    <nav>
      {visibleItems.map((item) => (
        <Link key={item.href} href={item.href}>
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
```

## Component Patterns

### Client vs Server Components

Most components use `'use client'` directive. Server components are used for:
- Root `layout.tsx`
- Static page layouts
- Data fetching at build time

### UI Component Library

Location: `frontend/web/components/ui/`

Design system components built with CSS Modules:

```typescript
// Button component
export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={cn(styles.button, styles[variant], styles[size], className)}
      {...props}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}
```

### Modal Pattern

```typescript
export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
}: ModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={cn(styles.modal, styles[size])}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.header}>
          <h2>{title}</h2>
          <button onClick={onClose}>X</button>
        </header>
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
```

## Route Protection

### Middleware Pattern

Location: `frontend/web/middleware.ts`

```typescript
export function middleware(request: NextRequest) {
  const token = request.cookies.get('accessToken')?.value;
  const isAuthenticated = !!token;
  const isLoginPage = request.nextUrl.pathname === '/login';

  // Redirect unauthenticated users to login
  if (!isAuthenticated && !isPublicPath(request.nextUrl.pathname)) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // Redirect authenticated users away from login
  if (isAuthenticated && isLoginPage) {
    return NextResponse.redirect(new URL('/', request.url));
  }
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
```

## Type Definitions

### Common Types

Location: `frontend/web/types/`

```typescript
// api.ts - Core API types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

// auth.ts - Auth types
export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  status: AccountStatus;
  department?: Department;
  profile?: UserProfile;
}

export enum UserRole {
  USER = 'USER',
  MANAGER = 'MANAGER',
  ADMIN = 'ADMIN',
}

export enum AccountStatus {
  ACTIVE = 'ACTIVE',
  DEACTIVATED = 'DEACTIVATED',
  REVOKED = 'REVOKED',
}
```

## Custom Hooks

### useChat Hook

Location: `frontend/web/hooks/useChat.ts`

```typescript
export function useChat(conversationId?: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = async (question: string) => {
    setIsLoading(true);
    setError(null);

    try {
      // Add user message
      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: question,
        createdAt: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // Stream response
      for await (const event of streamAIResponse(question, conversationId)) {
        if (event.type === 'content') {
          // Append to assistant message
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              return [...prev.slice(0, -1), { ...last, content: last.content + event.text }];
            }
            return [...prev, { id: crypto.randomUUID(), role: 'assistant', content: event.text, createdAt: new Date() }];
          });
        }
        if (event.type === 'sources') {
          // Handle sources
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setIsLoading(false);
    }
  };

  return { messages, isLoading, error, sendMessage };
}
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:3001` | API Gateway URL |
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` | Frontend URL |

## Related Documentation

- `contexts/AGENT.md` - Consolidated agent knowledge base
- `contexts/architecture/system-overview.md` - System architecture
- `contexts/authorization/rbac-matrix.md` - RBAC implementation
