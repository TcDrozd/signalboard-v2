# Writing a Signal

A signal is a small, self-contained module that fetches one piece of information
and returns a normalized result.

Signals should be:
- simple
- deterministic
- easy to delete

## File Placement

Create a new file in `signals/`:

```text
signals/my_signal.py
```

The file must expose one object named `SIGNAL`.

## Required Structure

```python
from dataclasses import dataclass
from signals.base import SignalMeta, SignalResult

@dataclass(frozen=True)
class MySignal:
    meta = SignalMeta(
        id="my_signal",
        title="My Signal",
        poll_interval_s=60,
        timeout_s=2.0,
    )

    def fetch(self) -> SignalResult:
        # fetch from source and normalize to SignalResult
        return SignalResult(status="ok", value="all good", ts=...)

SIGNAL = MySignal()
```

## SignalResult Contract

Every signal must return `SignalResult` with:

- `status`: `ok`, `warn`, `bad`, or `unknown`
- `value`: short human-readable summary
- `ts`: timestamp of the relevant event
- `details` (optional): explanation or context
- `link` (optional): URL for more info

## Best Practices

- Do network calls only inside `fetch()`.
- Use timeouts aggressively in upstream calls.
- Keep rendering logic out of signals.
- Return normalized failures instead of raising.

## Anti-Patterns

Avoid:
- fetching data during import
- global mutable state
- retry loops/sleeps in `fetch()`
- coupling signals to route/template logic
