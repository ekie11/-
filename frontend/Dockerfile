# Контекст сборки — каталог frontend/.
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# next.config.ts читает API_URL при СБОРКЕ: rewrites фиксируются в routes-manifest.
# Адрес api внутри compose-сети; менять его нужно только вместе с пересборкой образа.
ARG API_URL=http://api:8000
ENV API_URL=$API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
