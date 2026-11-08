FROM node:20-alpine AS deps
WORKDIR /app
COPY apps/web/package.json ./
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/ ./
ARG NEXT_PUBLIC_API_URL=http://api.localhost
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

RUN addgroup -S -g 10001 qf && adduser -S -u 10001 -G qf qf

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder --chown=qf:qf /app/public ./public
COPY --from=builder --chown=qf:qf /app/.next/standalone ./
COPY --from=builder --chown=qf:qf /app/.next/static ./.next/static

USER qf

EXPOSE 3000
CMD ["node", "server.js"]
