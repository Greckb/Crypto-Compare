FROM node:20-alpine
WORKDIR /app
RUN addgroup -S trading && adduser -S trading -G trading
COPY package*.json ./
RUN npm ci --omit=dev
COPY src/ ./src/
RUN chown -R trading:trading /app
USER trading
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "src/index.js"]
