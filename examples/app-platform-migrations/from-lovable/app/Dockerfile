FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY . .
RUN npm ci && NITRO_PRESET=node-server npm run build && npm prune --omit=dev
FROM node:24-bookworm-slim
WORKDIR /app
COPY --from=build /app/.output ./.output
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json /app/start.mjs /app/backend.mjs /app/operations.mjs /app/pg_with_multiple_database_servers.mjs ./
COPY --from=build /app/migrations ./migrations
USER node
CMD ["node","start.mjs"]
