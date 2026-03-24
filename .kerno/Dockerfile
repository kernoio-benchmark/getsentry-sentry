# Multi-stage Dockerfile for Sentry React/TypeScript Application
# Uses pnpm 10.30.2 and Rspack for building

# Build stage
# Using Node.js 23 which supports --experimental-transform-types
FROM node:23.9.0-bookworm-slim AS builder

# Install pnpm 10.30.2 directly via npm
RUN npm install -g pnpm@10.30.2

# Set working directory
WORKDIR /app

# Copy dependency manifests and configuration
COPY package.json pnpm-lock.yaml .npmrc ./

# Install dependencies with frozen lockfile
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Build the application for production
ENV NODE_ENV=production
RUN pnpm run build-production

# Production stage
FROM node:23.9.0-bookworm-slim AS production

# Install curl for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install pnpm 10.30.2 directly via npm
RUN npm install -g pnpm@10.30.2

# Create non-root user
RUN groupadd -r sentry && useradd -r -g sentry sentry

# Set working directory
WORKDIR /app

# Copy dependency manifests
COPY --chown=sentry:sentry package.json pnpm-lock.yaml .npmrc ./

# Install production dependencies only
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --prod && \
    pnpm store prune

# Copy the entire built application from builder
# This is a frontend application, so we copy everything that was built
COPY --chown=sentry:sentry --from=builder /app ./

# Switch to non-root user
USER sentry

# Set environment variables
ENV NODE_ENV=production

# Expose default port (adjust based on actual application port)
EXPOSE 7999

# Default command - this is a frontend app, typically served by a web server
# For now, we'll use a simple Node.js HTTP server
CMD ["node", "-e", "require('http').createServer((req, res) => { res.writeHead(200); res.end('Sentry Frontend'); }).listen(7999, '0.0.0.0', () => console.log('Server running on port 7999'));"]
