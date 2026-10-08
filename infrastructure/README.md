# Deployment boundary

The supported deployment target is local Demo Mode packaged by the root `Dockerfile` and `compose.yaml`. It runs as a non-root user, uses a persistent local volume, read-only container root, health check, and no-new-privileges setting. Optional Prometheus reads and OpenAI advisory analysis are configured through environment variables; four evidence sources remain simulated.

No cloud account, PostgreSQL, Redis, queue, secret manager, Terraform, Kubernetes, or live multi-source connection is provisioned. Docker Compose syntax validates, but the local Docker CLI did not return engine information after Docker Desktop started, so the image build and live container smoke test remain unverified here. CI builds the image on GitHub Actions.
