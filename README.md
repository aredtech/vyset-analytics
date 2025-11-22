# Analytics Service Scripts Quickstart (one-off inline env)

Set env vars inline per command; no shell export needed.

## Build & Push

- Analytics Service:
```
DOCKER_NAMESPACE=dockared VERSION=1.0.0 ./build-and-push.sh
```

## Deploy (pull + up -d)

- Analytics Service:
```
DOCKER_NAMESPACE=dockared VERSION=1.0.0 ./deploy.sh
```

## Complete Workflow Example

Run the complete build and deploy process:
```
DOCKER_NAMESPACE=dockared VERSION=1.0.0 ./example-build-deploy.sh
```

## Notes
- Replace `dockared` with your Docker Hub namespace.
- `VERSION` must match the tag you built/pushed.
- Run commands from the analytics service root directory.
- The service will be available at `http://localhost:8069` after deployment.
- Check service status with: `docker compose ps`
- View logs with: `docker compose logs -f analytics-service`