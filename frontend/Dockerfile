FROM node:22-alpine AS base

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./

RUN pnpm install

COPY . .

# ---------------- Development ----------------

FROM base AS dev

EXPOSE 5173

CMD ["pnpm", "dev", "--host"]

# ---------------- Build ----------------

FROM base AS builder

RUN pnpm build

# ---------------- Production ----------------

FROM nginx:alpine AS prod

COPY --from=builder /app/dist /usr/share/nginx/html