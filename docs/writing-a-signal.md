# Writing a Signal

A signal is a small, self-contained module that fetches one piece of information
and returns a normalized result.

Signals should be:
- simple
- deterministic
- easy to delete

---

## File placement

Create a new file in `signals/`:

```text
signals/my_signal.py
```

The file must expose **one object** named `SIGNAL`.

---

## Required structure

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
        ...
        return SignalResult(...)
        
SIGNAL = MySignal()
```

---

## SignalResult contract

Every signal must return a `SignalResult` with:

- `status`: `ok`, `warn`, `bad`, or `unknown`
- `value`: short human-readable summary
- `ts`: timestamp of the relevant event
- `details` (optional): explanation or context
- `link` (optional): URL for more info

Signals should **never raise exceptions**.
Failures should be returned as `status="bad"` with details.

---

## Best practices

- Do network calls **only inside `fetch()`**
- Use timeouts aggressively
- Prefer exact parsing for APIs you control
- Normalize complexity early — keep renderers dumb

---

## Anti-patterns

Avoid:
- fetching data during import
- global mutable state
- rendering logic inside signals
- retry loops or sleeps inside `fetch()`

If a signal becomes complex, it probably wants a helper function — not more logic inline.
```

---

# Step 2 — Add a simple Markdown renderer

We’ll use **stdlib + Jinja**, no markdown library.

Add this helper to `app.py` (near the top):

```python
from pathlib import Path
import html

DOCS_PATH = Path("docs")
```

Add this function:

```python
def _render_markdown(md: str) -> str:
    """
    Extremely small markdown renderer:
    - headings (#, ##)
    - paragraphs
    - code blocks (```)

    This is intentional — docs are controlled input.
    """
    lines = md.splitlines()
    html_lines = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            html_lines.append("<pre><code>" if in_code else "</code></pre>")
            continue

        if in_code:
            html_lines.append(html.escape(line))
            continue

        if line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.strip() == "":
            html_lines.append("<br>")
        else:
            html_lines.append(f"<p>{html.escape(line)}</p>")

    return "\n".join(html_lines)
```

This is intentionally tiny and readable.
