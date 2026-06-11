# Use official Node.js image as the base image
FROM node:20-alpine

# Set working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json to the container
COPY package.json ./

# Install dependencies
RUN npm install

# Install curl for health checks
RUN apk add --no-cache curl

# Copy the rest of the application code to the container
COPY . .

# Expose the port that the React app will run on
EXPOSE 3000

# Start the React development server
CMD ["npm", "run", "dev"]