FROM node:20-alpine AS base
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source and generate Prisma client
COPY prisma ./prisma
RUN npx prisma generate

COPY . .

# Default: run the API server
EXPOSE 3001
CMD ["npx", "tsx", "src/server.ts"]
