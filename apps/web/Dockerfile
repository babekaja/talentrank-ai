FROM node:22.22.3-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY angular.json tsconfig*.json .postcssrc.json ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM nginx:stable-alpine
COPY --from=builder /app/dist/talentrank-web/browser /usr/share/nginx/html
RUN chmod a+r /usr/share/nginx/html/assets/talentrank/secure-documents-960.webp
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
