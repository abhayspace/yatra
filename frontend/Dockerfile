# Build stage
FROM node:22-alpine AS build
WORKDIR /srv/app
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts || npm install --ignore-scripts
COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /srv/app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
