#!/bin/bash

# Deploy Script for VMS Analytics Service
# This script pulls the latest image from DockerHub and deploys it on the server

set -e  # Exit on any error

# Configuration
DOCKER_NAMESPACE="dockared"
IMAGE_NAME="vms-analytics"
VERSION=${1:-latest}  # Use first argument as version, default to 'latest'
FULL_IMAGE_NAME="${DOCKER_NAMESPACE}/${IMAGE_NAME}:${VERSION}"
CONTAINER_NAME="analytics-service"
COMPOSE_FILE="docker-compose.yml"

echo "🚀 Deploying VMS Analytics Service..."
echo "📦 Image: ${FULL_IMAGE_NAME}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed or not in PATH."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found. Please create it with required environment variables."
    exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f "${COMPOSE_FILE}" ]; then
    echo "❌ Error: ${COMPOSE_FILE} not found."
    exit 1
fi

# Pull the latest image
echo "📥 Pulling latest image from DockerHub..."
docker pull "${FULL_IMAGE_NAME}"

if [ $? -eq 0 ]; then
    echo "✅ Image pulled successfully!"
else
    echo "❌ Failed to pull image!"
    exit 1
fi

# Stop existing container if running
echo "🛑 Stopping existing container if running..."
docker-compose -f "${COMPOSE_FILE}" down || true

# Remove old container and image (optional cleanup)
echo "🧹 Cleaning up old containers..."
docker container prune -f || true

# Start the new container
echo "🚀 Starting new container..."
docker-compose -f "${COMPOSE_FILE}" up -d

if [ $? -eq 0 ]; then
    echo "✅ Container started successfully!"
else
    echo "❌ Failed to start container!"
    exit 1
fi

# Wait a moment for the container to fully start
echo "⏳ Waiting for service to start..."
sleep 5

# Check if container is running
if docker ps | grep -q "${CONTAINER_NAME}"; then
    echo "✅ Container is running!"
    
    # Show container status
    echo ""
    echo "📊 Container Status:"
    docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # Show logs (last 10 lines)
    echo ""
    echo "📋 Recent logs:"
    docker logs --tail 10 "${CONTAINER_NAME}"
    
else
    echo "❌ Container failed to start!"
    echo "📋 Container logs:"
    docker logs "${CONTAINER_NAME}" || true
    exit 1
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo "📦 Image: ${FULL_IMAGE_NAME}"
echo "🐳 Container: ${CONTAINER_NAME}"
echo ""
echo "💡 Useful commands:"
echo "   View logs: docker logs -f ${CONTAINER_NAME}"
echo "   Stop service: docker-compose -f ${COMPOSE_FILE} down"
echo "   Restart service: docker-compose -f ${COMPOSE_FILE} restart"
