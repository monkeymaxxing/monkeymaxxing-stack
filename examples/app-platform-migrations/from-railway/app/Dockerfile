FROM docker.io/library/node:22-bookworm-slim@sha256:9f0dde62d10e7ff7a310ecaebd66225f6b46c17e6cb778449a77b05d3541bea2
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY . .
USER node
ENV NODE_ENV=production
EXPOSE 8080
CMD ["npm", "start"]
