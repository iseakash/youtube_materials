# Official lightweight nginx image
FROM nginx:stable-alpine

# Remove existing default config to avoid conflicts with our custom config
RUN rm /etc/nginx/conf.d/default.conf

# Replace default config with our custom reverse-proxy config
COPY default.conf /etc/nginx/conf.d/default.conf

# Document that container listens on port 80
EXPOSE 80

# # Run nginx in foreground so the container stays alive
# CMD ["nginx", "-g", "daemon off;"]
# CMD ["sleep", "infinity"]