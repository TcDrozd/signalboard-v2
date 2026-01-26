from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .base import SignalMeta, SignalResult, now_utc


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _github_get_json(url: str, token: Optional[str], timeout_s: float) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "signalboard/0.1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=timeout_s) as resp:
        data = resp.read().decode("utf-8")
        return json.loads(data)


def _parse_github_iso(ts: str) -> datetime:
    # GitHub timestamps look like: "2026-01-18T14:23:05Z"
    # fromisoformat doesn't like Z, so convert to +00:00
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


@dataclass(frozen=True)
class PortfolioLastCommitAgeSignal:
    meta: SignalMeta = SignalMeta(
        id="portfolio_last_commit_age",
        title="Portfolio: last commit age",
        poll_interval_s=300,
        timeout_s=2.0,
    )

    def fetch(self) -> SignalResult:
        owner = os.getenv("GITHUB_OWNER", "").strip()
        repo = os.getenv("GITHUB_REPO", "").strip()
        token = os.getenv("GITHUB_TOKEN", "").strip() or None

        warn_days = _parse_int_env("PORTFOLIO_WARN_DAYS", 7)
        bad_days = _parse_int_env("PORTFOLIO_BAD_DAYS", 21)

        if not owner or not repo:
            return SignalResult(
                status="warn",
                value="GitHub repo not configured",
                ts=now_utc(),
                details="Set GITHUB_OWNER and GITHUB_REPO (and optionally GITHUB_TOKEN).",
            )

        # Last commit on default branch (most recent commit visible via API)
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
        try:
            payload = _github_get_json(url, token=token, timeout_s=self.meta.timeout_s)
        except HTTPError as e:
            # Helpful details for rate-limits / auth
            return SignalResult(
                status="bad",
                value=f"GitHub HTTP {e.code}",
                ts=now_utc(),
                details=f"{e.reason}. If this is rate limiting, set GITHUB_TOKEN.",
                link=f"https://github.com/{owner}/{repo}",
            )
        except URLError as e:
            return SignalResult(
                status="bad",
                value="GitHub unreachable",
                ts=now_utc(),
                details=str(e.reason),
                link=f"https://github.com/{owner}/{repo}",
            )
        except Exception as e:
            return SignalResult(
                status="bad",
                value="GitHub fetch failed",
                ts=now_utc(),
                details=str(e),
                link=f"https://github.com/{owner}/{repo}",
            )

        if not isinstance(payload, list) or not payload:
            return SignalResult(
                status="bad",
                value="No commits returned",
                ts=now_utc(),
                details="GitHub API returned an empty commits list.",
                link=f"https://github.com/{owner}/{repo}",
            )

        commit_obj = payload[0]
        # Prefer committer date (what GitHub considers the commit timestamp),
        # fall back to author date.
        ts_str = (
            (commit_obj.get("commit") or {}).get("committer", {}) or {}
        ).get("date") or (
            (commit_obj.get("commit") or {}).get("author", {}) or {}
        ).get("date")

        if not ts_str:
            return SignalResult(
                status="bad",
                value="Commit timestamp missing",
                ts=now_utc(),
                details="Could not find commit.committer.date or commit.author.date in API response.",
                link=f"https://github.com/{owner}/{repo}",
            )

        commit_dt = _parse_github_iso(ts_str)
        now = now_utc()
        age_s = int((now - commit_dt).total_seconds())
        age_days = max(age_s // 86400, 0)

        if age_days >= bad_days:
            status = "bad"
        elif age_days >= warn_days:
            status = "warn"
        else:
            status = "ok"

        value = f"{age_days}d since last commit"
        details = f"Last commit: {commit_dt.isoformat()} (UTC). Thresholds: warn≥{warn_days}d, bad≥{bad_days}d."

        return SignalResult(
            status=status,
            value=value,
            ts=commit_dt,
            details=details,
            link=f"https://github.com/{owner}/{repo}",
        )


SIGNAL = PortfolioLastCommitAgeSignal()
