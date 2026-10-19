---
name: nextjs-frontend
description: Standards and patterns for building the SOPilot Next.js frontend.
version: 1.0.0
author: SOPilot Team
---

# Next.js Frontend Skill

This skill provides instructions for developing high-quality, consistent UI components and logic in the SOPilot frontend.

## When to use this skill
- When creating or modifying Next.js pages or components.
- When implementing new API service calls on the client.
- When managing global state with Zustand or server state with React Query.

## Core Instructions

### 1. Component Creation
- **Architecture**: Use functional components with TypeScript.
- **Styling**: Always use Tailwind CSS v4. Follow the "Vercel-like" minimalist aesthetic.
- **UI Library**: Use existing components from `@/components/ui`.
- **Icons**: Use `lucide-react`.

### 2. State Management
- **Client State**: Use Zustand (in `@/store`) for auth and UI toggles.
- **Server State**: Use React Query for all data fetching. Define custom hooks in `@/hooks`.

### 3. API Communication
- All calls must use the `api` instance from `@/lib/api.ts`.
- **Streaming**: For chat, use the `ReadableStream` pattern (see `@/hooks/useChat.ts`).
- **Authorization**: Bearer tokens are handled by interceptors; do not manually inject them in every call.

### 4. Code Style
- **TypeScript**: No `any`. Use strict interfaces.
- **Server vs Client**: Default to Server Components. Use `"use client"` only for interactivity or hooks.
- **Naming**: `kebab-case` for files, `PascalCase` for components.

## References
- `@/app/globals.css` - Design tokens and CSS variables.
- `.agent/rules/frontend.md` - Detailed implementation rules.
