FROM node:20-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# The browser calls the API directly, so this must be an address the *browser* can reach.
ARG VITE_API_BASE=http://localhost:8000/api
ARG VITE_BASE_URI=http://localhost:8000/api/
ENV VITE_API_BASE=$VITE_API_BASE VITE_BASE_URI=$VITE_BASE_URI
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
