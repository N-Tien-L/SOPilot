# Poliwise Frontend Development Guidelines

> **Source of Truth**: This document defines all rules, standards, and best practices for the Poliwise frontend codebase. All AI agents must follow these guidelines without exception.

---

## 1. Core Architecture & Tech Stack

### 1.1 Technology Versions (Fixed)
- **Next.js**: `16.1.6` (App Router)
- **React**: `19.2.3`
- **TypeScript**: `5.x` (strict mode required)
- **Tailwind CSS**: `4.x`
- **Zustand**: `5.x` (client state)
- **React Query**: `3.x` (server state / data fetching)
- **Lucide React**: icons
- **Axios**: HTTP client

### 1.2 Monorepo Structure
```
Poliwise/
├── frontend/web/           # Next.js frontend (THIS REPO)
├── services/api-gateway/   # NestJS API Gateway
├── services/*-service/     # Spring Boot microservices
├── .agent/context/               # Architecture documentation
└── docs/                   # Product notes
```

### 1.3 Shared Type Import Rules
**ALWAYS** import types from the designated shared folders:
- Frontend types: `frontend/web/types/` or `frontend/web/interfaces/`
- Backend-aligned models: `frontend/web/interfaces/models/`
- Enums: `frontend/web/interfaces/enums/`

**NEVER** create duplicate type definitions. If a type exists in `types/`, use it. If the backend returns a different shape, update the shared type file, not your component.

### 1.4 Key File Conventions
- **API Client**: `frontend/web/lib/api.ts` — single unified API client (class `ApiClient`)
- **State Store**: `frontend/web/store/auth-store.ts` (Zustand)
- **React Query Hooks**: `frontend/web/hooks/` — custom hooks for data fetching
- **UI Components**: `frontend/web/components/ui/` — Shadcn-style components
- **Page Components**: `frontend/web/app/` — Next.js App Router pages

---

## 2. State Management Protocol

### 2.1 Zustand v5 — Global Client State ONLY
Use Zustand for:
- Authentication state (`user`, `isAuthenticated`, `accessToken`)
- UI state (sidebar open/closed, modals, toasts)
- Non-persisted transient state

**Example** (`store/auth-store.ts`):
```typescript
import { create } from 'zustand';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: !!localStorage.getItem('accessToken'),
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  logout: () => {
    localStorage.clear();
    set({ user: null, isAuthenticated: false });
  },
}));
```

### 2.2 React Query v3 — Server State / Data Fetching
Use React Query for:
- API data fetching (conversations, messages, documents)
- Caching and background refetching
- Optimistic updates
- Pagination

**NEVER** use React Query for UI state. **NEVER** introduce Redux, Context API, or other state management for server data.

### 2.3 React Query Provider Setup
Wrap your app with `QueryProvider` in `app/layout.tsx`:
```typescript
import { QueryProvider } from '@/providers';

export default function RootLayout({ children }) {
  return (
    <html lang="vi">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
```

### 2.4 React Query Hook Pattern
Create hooks in `hooks/useChat.ts` (or domain-specific files):
```typescript
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { api } from '@/lib/api';

export function useConversations(params?: { page?: number; size?: number; keyword?: string }) {
  return useQuery({
    queryKey: ['conversations', params],
    queryFn: () => api.ai.getConversationList(params),
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.ai.deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conversations'] }),
  });
}
```

---

## 3. API Integration Rules

### 3.1 Authorization — JWT Bearer Token Only
- **Header**: `Authorization: Bearer <accessToken>`
- **Storage**: `localStorage.getItem('accessToken')`
- **NO HttpOnly cookies** — tokens are stored client-side
- **Token refresh**: Automatic via Axios interceptor in `lib/api.ts` (401 → refresh → retry)

### 3.2 API Client Structure
All API calls go through `lib/api.ts` — the `ApiClient` class. **NEVER** make direct Axios calls in components.

```typescript
// lib/api.ts
class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000',
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });
    this.setupInterceptors(); // Injects Bearer token, handles 401
  }

  // Domain-specific APIs
  ai = {
    askStream: (data: QuestionRequest): ReadableStream<StreamEvent> => { /* ... */ },
    getConversationList: (params) => this.client.get('/api/v1/ai/conversations', { params }),
    // ...
  };
}

export const api = new ApiClient();
```

### 3.3 Streaming (SSE) Implementation
For AI streaming responses, use `fetch` + `ReadableStream` (NOT `EventSource`):
```typescript
// Example: SSE streaming handler
askStream(data: QuestionRequest): ReadableStream<StreamEvent> {
  const token = localStorage.getItem('accessToken');
  return new ReadableStream<StreamEvent>({
    start(controller) {
      fetch('/api/v1/ai/chat/stream', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }).then(response => {
        const reader = response.body.getReader();
        // Parse SSE events...
      });
    },
  });
}
```

### 3.4 API Response Handling
Backend returns wrapped responses. Use the `coercePaginated` helper for consistent parsing:
```typescript
// Handle both formats:
// 1. { success: true, data: {...} }
// 2. { content: [...], totalElements: N }

const coerced = coercePaginated<Conversation>(res.data as Record<string, unknown>, 'data');
return coerced.data;
```

---

## 4. UI/UX & Styling Guidelines

### 4.1 Design Aesthetic
**"Vercel-like, minimalist, crisp, enterprise dashboard"**:
- Clean white/gray backgrounds (`--background: #ffffff`, `--foreground: #0f172a`)
- Indigo primary color (`--primary: #4f46e5`)
- Subtle borders and shadows
- Generous whitespace
- No gradients, no heavy decorations

### 4.2 Tailwind CSS v4 — Mandatory
**Use Tailwind utility classes for all styling**. NO inline styles, NO custom CSS files for components (except CSS modules for third-party integration).

```tsx
// GOOD
<div className="flex items-center justify-between p-4 border-b border-border">
  <h1 className="text-xl font-semibold text-foreground">Title</h1>
</div>

// BAD
<div style={{ display: 'flex', padding: '16px', borderBottom: '1px solid #e2e8f0' }}>
  <h1 style={{ fontSize: '20px', fontWeight: '600' }}>Title</h1>
</div>
```

### 4.3 CSS Variables (Design Tokens)
Use CSS variables from `app/globals.css`:
```css
:root {
  --background: #ffffff;
  --foreground: #0f172a;
  --primary: #4f46e5;
  --primary-foreground: #ffffff;
  --secondary: #f1f5f9;
  --muted: #f1f5f9;
  --muted-foreground: #64748b;
  --destructive: #ef4444;
  --border: #e2e8f0;
  --radius: 0.5rem;
}
```

### 4.4 Shadcn UI Components — Mandatory
**Use existing Shadcn-style components from `components/ui/`**:
- `Button` (variants: primary, secondary, ghost, destructive, outline)
- `Input`, `Textarea`, `Select`
- `Card`, `Badge`, `Avatar`
- `Modal`, `ConfirmDialog`
- `Table`, `Pagination`, `Tabs`
- `Skeleton`, `Spinner`, `EmptyState`

**NEVER** build button, input, modal, or card components from scratch. Use and extend the existing library.

### 4.5 Icons
**Use `lucide-react` exclusively**. NO inline SVGs, NO emoji icons.
```tsx
import { Send, User, Bot, Loader2, Trash2 } from 'lucide-react';
```

### 4.6 Loading States
**Always show loading states** — never leave users with blank screens:
```tsx
// Skeleton loading for lists
<div className="space-y-2">
  {[1, 2, 3].map(i => <div key={i} className="h-16 bg-muted rounded-lg animate-pulse" />)}
</div>

// Button loading state
<Button loading={isLoading}>Gửi</Button>
```

### 4.7 Error States
Handle all error states:
```tsx
// Inline error message
{error && (
  <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-lg">
    {error}
  </div>
)}

// Empty state
<div className="text-center py-8 text-muted-foreground">
  <FileText size={32} className="mx-auto mb-2 opacity-50" />
  <p>Không có dữ liệu</p>
</div>
```

### 4.8 Responsive Design
- Mobile-first approach
- Sidebar: hidden on mobile, fixed on desktop (`lg:relative`)
- Chat layout: full-width on mobile, max-w-4xl centered on desktop
- Tables: horizontal scroll on mobile

---

## 5. Coding Standards & Best Practices

### 5.1 TypeScript — Strict Mode
**NO `any` types allowed**. Always define proper types:
```typescript
// BAD
function handleSubmit(data: any) { /* ... */ }

// GOOD
function handleSubmit(data: ChatRequest) { /* ... */ }

// If type is unknown, use unknown
function handleError(error: unknown) {
  if (error instanceof Error) {
    console.error(error.message);
  }
}
```

### 5.2 Server vs. Client Components
**Default to Server Components**. Add `"use client"` only when necessary:
- Using React hooks (`useState`, `useEffect`, `useQuery`)
- Using browser APIs (`localStorage`, `window`)
- Using event handlers
- Using Zustand store

```tsx
// Server Component (default)
export default async function DocumentPage({ params }: { params: { id: string } }) {
  const doc = await api.documents.getById(params.id); // Direct API call
  return <DocumentView document={doc} />;
}

// Client Component
'use client';
export function ChatInput() {
  const [value, setValue] = useState('');
  // ...
}
```

### 5.3 Component File Structure
```
components/
├── chat/
│   ├── ChatContainer.tsx    # Main component
│   └── index.ts             # Barrel export
└── ui/
    ├── button/
    │   ├── Button.tsx
    │   ├── button.module.css
    │   └── index.ts
    └── index.ts             # Main barrel export
```

### 5.4 Import Conventions
Use path aliases (`@/`):
```typescript
import { Button, Card } from '@/components/ui';
import { useConversations } from '@/hooks/useChat';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api';
import type { Message, Conversation } from '@/types';
```

### 5.5 Component Patterns

**Functional components with explicit props**:
```tsx
interface ChatMessageProps {
  message: Message;
  onCopy?: (content: string) => void;
  onFeedback?: (messageId: string, type: FeedbackType) => void;
}

export function ChatMessage({ message, onCopy, onFeedback }: ChatMessageProps) {
  // ...
}
```

**NO class components**. Use functional components with hooks.

### 5.6 Streaming Text UI
For streaming AI responses, use incremental state updates:
```tsx
const [content, setContent] = useState('');

for await (const chunk of streamChat(request, (update) => {
  setContent(update.content);
})) {
  // Each yield updates the UI
}

// Final message structure
const assistantMsg: Message = {
  id: `temp-${Date.now()}`,
  role: 'ASSISTANT',
  content: content,
  isStreaming: false,
  createdAt: new Date().toISOString(),
};
```

### 5.7 Event Handler Rules
- Use `on` prefix for props: `onClick`, `onChange`, `onSubmit`
- Use `handle` prefix for handlers: `handleSubmit`, `handleCopy`
- Use `handle` + Verb: `handleDeleteConversation`, `handleMarkAsUnanswered`

### 5.8 Naming Conventions
- **Files**: kebab-case (`chat-container.tsx`, `use-chat.ts`)
- **Components**: PascalCase (`ChatContainer`, `ChatMessage`)
- **Functions/Variables**: camelCase (`handleSubmit`, `isLoading`)
- **Types/Interfaces**: PascalCase (`ChatRequest`, `Message`)
- **Constants**: UPPER_SNAKE_CASE (`API_BASE_URL`)

### 5.9 Accessibility
- Use semantic HTML (`<button>`, `<nav>`, `<main>`, `<article>`)
- Add `aria-label` for icon-only buttons
- Support keyboard navigation
- Use focus-visible styles
- Color contrast ratio: minimum 4.5:1 for text

### 5.10 Performance
- Use `useCallback` and `useMemo` sparingly (only for expensive computations)
- Lazy load pages with `next/dynamic`
- Use `useEffect` cleanup for aborting streams
- Avoid re-renders: use React Query's `staleTime` for caching

---

## 6. Common Patterns Reference

### 6.1 Chat Streaming Pattern
```tsx
// hooks/useChat.ts
export async function* streamChat(
  request: QuestionRequest,
  onStateUpdate: (partial: Partial<StreamingState>) => void
): AsyncGenerator<string, void, unknown> {
  const stream = api.ai.askStream(request);
  const reader = stream.getReader();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      switch (value.type) {
        case 'conversationId':
          onStateUpdate({ conversationId: value.conversationId });
          break;
        case 'sources':
          onStateUpdate({ sources: value.sources });
          break;
        case 'content':
          onStateUpdate({ content: value.content });
          yield value.content;
          break;
        case 'done':
          onStateUpdate({ isStreaming: false });
          break;
        case 'error':
          onStateUpdate({ error: value.error, isStreaming: false });
          break;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

### 6.2 Mutation with Toast Feedback
```tsx
const deleteMutation = useDeleteConversation();

const handleDelete = async () => {
  try {
    await deleteMutation.mutateAsync(conversationId);
    toast.success('Đã xóa cuộc trò chuyện');
  } catch {
    toast.error('Không thể xóa cuộc trò chuyện');
  }
};
```

### 6.3 Auto-growing Textarea
```tsx
const textareaRef = useRef<HTMLTextAreaElement>(null);

useEffect(() => {
  if (textareaRef.current) {
    textareaRef.current.style.height = 'auto';
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
  }
}, [value]);
```

### 6.4 Conversation Sidebar with Delete
```tsx
const [deleteTarget, setDeleteTarget] = useState<Conversation | null>(null);
const deleteMutation = useDeleteConversation();

return (
  <>
    <button onClick={() => setDeleteTarget(conv)}>
      <Trash2 size={14} />
    </button>

    <ConfirmDialog
      open={!!deleteTarget}
      onClose={() => setDeleteTarget(null)}
      title="Xóa cuộc trò chuyện"
      message="Bạn có chắc muốn xóa?"
      variant="danger"
      onConfirm={handleDelete}
      loading={deleteMutation.isLoading}
    />
  </>
);
```

---

## 7. Checklist Before Committing

- [ ] No `any` types in code
- [ ] No direct Axios calls in components (use `api` from `lib/api.ts`)
- [ ] Types imported from `types/` or `interfaces/`
- [ ] Loading states implemented for all async operations
- [ ] Error states handled and displayed to users
- [ ] Responsive design tested (mobile + desktop)
- [ ] Accessibility: semantic HTML, aria labels, keyboard navigation
- [ ] Build passes (`pnpm build`)
- [ ] No console.log statements (use structured logging or remove)
- [ ] Streaming uses `ReadableStream` (not `EventSource`)
