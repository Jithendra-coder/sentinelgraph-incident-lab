# Deployment boundary

The supported deployment target is local Demo Mode packaged by the root `Dockerfile` and `compose.yaml`. It runs as a non-root user, uses a persistent local volume, read-only container root, health check, and no-new-privileges setting. An optional read-only Prometheus metrics adapter can be configured through the `SENTINELGRAPH_PROMETHEUS_*` environment variables; the other evidence sources remain simulated.

No cloud account, PostgreSQL, Redis, queue, secret manager, Terraform, Kubernetes, or live multi-source connection is provisioned. Docker Compose syntax validates, but the local Docker CLI did not return engine information after Docker Desktop started, so the image build and live container smoke test remain unverified here. CI builds the image on GitHub Actions.
