from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import SignalMeta, SignalResult, now_utc


@dataclass(frozen=True)
class ServiceHealthSignal:
    meta: SignalMeta = SignalMeta(
        id="webhook-router",
        title="Webhook Router",
        poll_interval_s=60,
        timeout_s=1.5,
    )

    def fetch(self) -> SignalResult:
        # Override with SERVICE_BASE_URL, e.g. http://apps.local:5055
        base = os.getenv("WEBHOOK_ROUTER_BASE_URL", "http://localhost:8080").rstrip("/")
        url = f"{base}/health"
        req = Request(url, headers={"User-Agent": "signalboard/0.1"}, method="GET")

        try:
            with urlopen(req, timeout=self.meta.timeout_s) as resp:
                code = int(getattr(resp, "status", 200))

            if 200 <= code < 300:
                return SignalResult(
                    status="ok",
                    value="healthy",
                    ts=now_utc(),
                    details=f"GET {url} -> {code}",
                    link=url,
                )

            return SignalResult(
                status="warn",
                value=f"health HTTP {code}",
                ts=now_utc(),
                details="Non-2xx health response",
                link=url,
            )

        except HTTPError as e:
            status = "bad" if e.code >= 500 else "warn"
            return SignalResult(
                status=status,
                value=f"health HTTP {e.code}",
                ts=now_utc(),
                details=str(e.reason),
                link=url,
            )
        except URLError as e:
            return SignalResult(
                status="bad",
                value="service unreachable",
                ts=now_utc(),
                details=str(getattr(e, "reason", e)),
                link=url,
            )
        except Exception as e:
            return SignalResult(
                status="bad",
                value="health check failed",
                ts=now_utc(),
                details=str(e),
                link=url,
            )


SIGNAL = ServiceHealthSignal()
