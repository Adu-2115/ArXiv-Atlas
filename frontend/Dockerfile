# Frontend Dockerfile — Next.js, multi-stage build for a small final image.
FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install

COPY . .
# Baked in at build time since Next.js inlines NEXT_PUBLIC_* vars into the
# client bundle — passed through from docker-compose's build args.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]
