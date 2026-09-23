# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate && pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

# Production stage
FROM node:22-alpine AS production

WORKDIR /app

COPY --chown=node:node package*.json pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate && pnpm install --frozen-lockfile --prod

COPY --from=builder --chown=node:node /app/dist ./dist

ENV NODE_ENV=production
ENV PORT=3001

USER node

EXPOSE 3001

CMD ["node", "dist/main"]
