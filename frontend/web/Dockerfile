# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:3001
ARG NEXT_PUBLIC_ONLYOFFICE_URL=http://localhost:8888
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_ONLYOFFICE_URL=${NEXT_PUBLIC_ONLYOFFICE_URL}

COPY package.json pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate && pnpm install

COPY . .

RUN pnpm build

# Production stage
FROM node:22-alpine AS production

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

USER node

EXPOSE 3000

CMD ["node", "server.js"]
