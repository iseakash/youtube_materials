FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# need to run nginx in the foreground to keep the container running
CMD ["nginx", "-g", "daemon off;"]