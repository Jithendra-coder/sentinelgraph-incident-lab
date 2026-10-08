"""Read-only Prometheus instant-query adapter."""

import json
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from app.models import Evidence, Source, now_utc

MAX_RESPONSE_BYTES = 65_536
MAX_SERIES = 10


class PrometheusMetrics:
    def __init__(self, base_url: str, query: str, bearer_token: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Prometheus URL must be HTTP(S) and cannot contain embedded credentials.")
        if parsed.query or parsed.fragment:
            raise ValueError("Prometheus URL cannot include a query string or fragment.")
        if not query.strip() or len(query) > 1024:
            raise ValueError("Prometheus query must contain 1-1024 characters.")
        if bearer_token and parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Prometheus bearer tokens require HTTPS outside loopback.")
        self.base_url = base_url.rstrip("/")
        self.query = query
        self.bearer_token = bearer_token
        self.transport = transport

    async def collect(self, incident_id: str) -> Evidence:
        headers = {"Authorization": f"Bearer {self.bearer_token}"} if self.bearer_token else {}
        try:
            async with (
                httpx.AsyncClient(timeout=5.0, follow_redirects=False, trust_env=False, transport=self.transport) as client,
                client.stream(
                    "GET",
                    f"{self.base_url}/api/v1/query",
                    params={"query": self.query, "limit": MAX_SERIES},
                    headers=headers,
                ) as response,
            ):
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("Prometheus response exceeded the 64 KiB evidence limit.")
                    body.extend(chunk)
            payload = json.loads(body)
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Prometheus returned HTTP {exc.response.status_code}.") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("Prometheus query timed out.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Prometheus request failed.") from exc
        except ValueError as exc:
            raise RuntimeError("Prometheus returned invalid JSON.") from exc

        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise RuntimeError("Prometheus query returned an error.")
        data = payload.get("data")
        results = data.get("result") if isinstance(data, dict) and data.get("resultType") == "vector" else None
        if not isinstance(results, list) or len(results) > MAX_SERIES:
            raise RuntimeError("Prometheus query must return an instant vector of at most 10 series.")

        samples = []
        for result in results:
            if not isinstance(result, dict) or not isinstance(result.get("metric"), dict):
                raise RuntimeError("Prometheus returned a malformed time series.")
            value = result.get("value")
            if (
                not isinstance(value, list)
                or len(value) != 2
                or not isinstance(value[1], str)
                or not all(isinstance(key, str) and isinstance(label, str) for key, label in result["metric"].items())
            ):
                raise RuntimeError("Prometheus returned a malformed sample.")
            try:
                sampled_at = datetime.fromtimestamp(float(value[0]), UTC).isoformat()
            except (OverflowError, OSError, TypeError, ValueError) as exc:
                raise RuntimeError("Prometheus returned an invalid sample timestamp.") from exc
            samples.append({"labels": result["metric"], "value": value[1], "sampled_at": sampled_at})

        return Evidence(
            id=f"ev-{incident_id[:8]}-prometheus-metrics",
            source=Source.metrics,
            summary=f"{len(samples)} time series returned by the configured Prometheus instant query.",
            observed_value=json.dumps({"series": samples}, sort_keys=True, separators=(",", ":")),
            collected_at=now_utc(),
            provenance="PROMETHEUS",
        )
