# Static site served by nginx. Built by GitHub Actions (.github/workflows/images.yml).
FROM nginx:1.29-alpine
COPY . /usr/share/nginx/html
