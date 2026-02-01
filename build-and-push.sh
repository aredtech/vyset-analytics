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

# Ensure buildx is available and create builder if needed (for multi-platform)
echo "🔧 Setting up Docker Buildx for multi-platform build..."
if ! docker buildx version &> /dev/null; then
    echo "❌ Error: docker buildx is required for multi-platform builds. Please upgrade Docker."
    exit 1
fi
docker buildx create --name multiarch-builder --use 2>/dev/null || docker buildx use multiarch-builder 2>/dev/null || true

# Build and push for both AMD64 and ARM64 (single manifest, multi-platform image)
echo "🔨 Building Docker image for linux/amd64 and linux/arm64..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag "${FULL_IMAGE_NAME}" \
    --push \
    .

if [ $? -eq 0 ]; then
    echo "✅ Multi-platform build successful!"
else
    echo "❌ Build failed!"
    exit 1
fi

if [ $? -eq 0 ]; then
    echo "✅ Push successful!"
    echo "🎉 Image ${FULL_IMAGE_NAME} is now available on DockerHub!"
else
    echo "❌ Push failed!"
    exit 1
fi

# Optional: Also tag as 'latest' on registry if version is not 'latest'
if [ "${VERSION}" != "latest" ]; then
    echo "🏷️  Tagging as latest on registry..."
    docker buildx imagetools create -t "${DOCKER_NAMESPACE}/${IMAGE_NAME}:latest" "${FULL_IMAGE_NAME}"
    echo "✅ Latest tag pushed!"
fi

echo ""
echo "📋 Summary:"
echo "   Image: ${FULL_IMAGE_NAME}"
echo "   Status: Successfully built and pushed"
echo ""
echo "💡 To deploy on server, run:"
echo "   ./deploy.sh ${VERSION}"
