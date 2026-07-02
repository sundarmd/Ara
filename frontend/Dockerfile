# Production frontend Dockerfile for React/Vite.
FROM node:24-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --audit=false --fund=false

COPY . .

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
