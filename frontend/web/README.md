# Poliwise Frontend - Hướng Dẫn Cài Đặt

## Cài đặt Dependencies

```bash
cd frontend/web
pnpm install
```

Dependencies đã được thêm vào `package.json`:
- `lucide-react` - Icon library
- `clsx` - Utility cho class names

## Chạy Development Server

```bash
pnpm dev
```

Frontend sẽ chạy tại: `http://localhost:3001`

## Build Production

```bash
pnpm build
pnpm start
```

## Cấu Trúc Pages

```
app/
├── layout.tsx              # Root layout
├── globals.css             # Global styles với CSS variables
├── page.tsx               # Trang chủ - Chat AI
├── login/
│   ├── page.tsx          # Trang đăng nhập
│   └── login.module.css
├── documents/
│   ├── page.tsx          # Trang danh sách tài liệu
│   └── documents.module.css
├── analytics/
│   ├── page.tsx          # Trang phân tích (Manager+)
│   └── analytics.module.css
├── profile/
│   ├── page.tsx          # Trang cá nhân
│   └── profile.module.css
└── admin/
    └── users/
        ├── page.tsx      # Quản lý người dùng (Admin)
        └── admin-users.module.css
```

## Components

```
components/
├── layout/
│   ├── Header.tsx         # Header với navigation
│   ├── Sidebar.tsx        # Sidebar menu
│   ├── MainLayout.tsx     # Layout wrapper
│   └── *.module.css
```

## Stores (Zustand)

```
store/
├── auth-store.ts          # Auth state management
├── ui-store.ts            # UI state (sidebar, theme)
└── index.ts
```

## API Client

```
lib/
└── api.ts                 # Axios client với interceptors
```

## Types

```
types/
├── auth.ts               # Auth types
├── document.ts           # Document & Metadata types
├── ai.ts                 # AI conversation types
├── analytics.ts          # Analytics types
└── index.ts
```

## Environment Variables

Tạo file `.env.local` trong `frontend/web/`:

```env
NEXT_PUBLIC_API_URL=http://localhost:3001
```

## API Endpoints Coverage

### Auth Service (Proxy → auth-service:8081)
| Method | Endpoint | Status |
|--------|----------|--------|
| POST | `/api/v1/auth/login` | ✅ |
| POST | `/api/v1/auth/register` | ✅ |
| POST | `/api/v1/auth/refresh` | ✅ |
| POST | `/api/v1/auth/logout` | ✅ |
| POST | `/api/v1/auth/logout-all` | ✅ |
| GET | `/api/v1/auth/sessions` | ✅ |

### User Service (Proxy → user-service:8082)
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/users/me` | ✅ |
| GET | `/api/v1/users/{id}` | ✅ |
| PUT | `/api/v1/users/me` | ✅ |
| GET | `/api/v1/users` | ✅ |
| PATCH | `/api/v1/users/me/status` | ✅ |
| DELETE | `/api/v1/users/{id}` | ✅ |

### Documents (Proxy → knowledge-service:8083)
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/documents` | ✅ |
| GET | `/api/v1/documents/{id}` | ✅ |
| POST | `/api/v1/documents/upload` | ✅ |
| DELETE | `/api/v1/documents/{id}` | ✅ |

### Analytics (Proxy → feedback-service:8085)
| Method | Endpoint | Status |
|--------|----------|--------|
| GET | `/api/v1/analytics/dashboard` | ✅ |
| GET | `/api/v1/ai/history` | ✅ |
| POST | `/api/v1/ai/ask` | ✅ |
| POST | `/api/v1/feedback` | ✅ |

## Features

### Chat AI Interface
- Giao diện chat với AI
- Hiển thị nguồn tham khảo
- Like/Dislike feedback
- Lịch sử hội thoại
- Gợi ý câu hỏi

### Knowledge Base
- Danh sách tài liệu (grid/list view)
- Tìm kiếm theo tên
- Filter theo trạng thái
- Phân trang
- Upload tài liệu (Admin)

### Analytics Dashboard
- Stats cards (câu hỏi, satisfaction, tài liệu, users)
- Charts placeholder
- Top questions
- Top documents
- Feedback summary

### Admin Panel
- Quản lý người dùng
- Thay đổi trạng thái tài khoản
- Phân quyền (Admin/Manager/User)

### Profile
- Xem thông tin cá nhân
- Cập nhật profile

## Design System

### Colors (CSS Variables)
```css
--primary: #4f46e5
--primary-foreground: #ffffff
--background: #ffffff (dark: #0f172a)
--foreground: #0f172a (dark: #f8fafc)
--muted: #f1f5f9 (dark: #1e293b)
--border: #e2e8f0 (dark: #334155)
--destructive: #ef4444
--success: #10b981
```

### Icons
Sử dụng `lucide-react` cho tất cả icons:
- `MessageSquare` - Chat
- `BookOpen` - Documents
- `BarChart3` - Analytics
- `User` - Profile
- `Settings` - Settings
- `Shield` - Admin
- `LogOut` - Logout
- `Search` - Search
- `Upload` - Upload
- `Download` - Download
- ...v.v
