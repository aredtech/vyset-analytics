#!/bin/bash

# Build and Push Script for VMS Analytics Service
# This script builds the Docker image and pushes it to DockerHub

set -e  # Exit on any error

# Configuration
DOCKER_NAMESPACE="dockared"
IMAGE_NAME="vms-analytics"
VERSION=${1:-latest}  # Use first argument as version, default to 'latest'
FULL_IMAGE_NAME="${DOCKER_NAMESPACE}/${IMAGE_NAME}:${VERSION}"

echo "🚀 Building and pushing VMS Analytics Service..."
echo "📦 Image: ${FULL_IMAGE_NAME}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if user is logged in to DockerHub
# if ! docker info | grep -q "Username:"; then
#     echo "❌ Error: Not logged in to DockerHub. Please run 'docker login' first."
#     exit 1
# fi

# Build the Docker image for AMD64 platform
echo "🔨 Building Docker image for AMD64 platform..."
docker build --platform linux/amd64 -t "${FULL_IMAGE_NAME}" .

if [ $? -eq 0 ]; then
    echo "✅ Build successful!"
else
    echo "❌ Build failed!"
    exit 1
fi

# Push the image to DockerHub
echo "📤 Pushing image to DockerHub..."
docker push "${FULL_IMAGE_NAME}"

if [ $? -eq 0 ]; then
    echo "✅ Push successful!"
    echo "🎉 Image ${FULL_IMAGE_NAME} is now available on DockerHub!"
else
    echo "❌ Push failed!"
    exit 1
fi

# Optional: Also tag and push as 'latest' if version is not 'latest'
if [ "${VERSION}" != "latest" ]; then
    echo "🏷️  Also tagging as latest..."
    docker tag "${FULL_IMAGE_NAME}" "${DOCKER_NAMESPACE}/${IMAGE_NAME}:latest"
    docker push "${DOCKER_NAMESPACE}/${IMAGE_NAME}:latest"
    echo "✅ Latest tag pushed!"
fi

echo ""
echo "📋 Summary:"
echo "   Image: ${FULL_IMAGE_NAME}"
echo "   Status: Successfully built and pushed"
echo ""
echo "💡 To deploy on server, run:"
echo "   ./deploy.sh ${VERSION}"
