# Deployment boundary

The only supported deployment target in this repository is the local deterministic Demo Mode packaged by the root `Dockerfile` and `compose.yaml`. It runs as a non-root user, uses a persistent local volume, read-only container root, health check, and no-new-privileges setting.

No cloud account, PostgreSQL, Redis, queue, secret manager, Terraform, Kubernetes, or real production adapter is provisioned. Docker Compose syntax validates, but the local Docker CLI did not return engine information after Docker Desktop started, so the image build and live container smoke test remain unverified here. CI builds the image on GitHub Actions.
