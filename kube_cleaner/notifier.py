import logging
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def send_webhook_report(webhook_url: str, items: list[dict[str, str]], dry_run: bool) -> bool:
    if not webhook_url or not items:
        return False

    parsed = urlparse(webhook_url.strip())
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        logger.warning('Invalid webhook URL scheme or host: %s', webhook_url)
        return False

    mode = 'DRY-RUN' if dry_run else 'EXECUTED'
    lines = [
        f'🧹 **Kube-Cleaner Report [{mode}]**',
        f'Cleaned up {len(items)} orphaned resources:\n',
    ]
    for item in items[:15]:
        lines.append(
            f"- `[{item['type'].upper()}]` {item['namespace']}/{item['name']}"
            f" ({item['reason']}) -> {item['action']}"
        )

    if len(items) > 15:
        lines.append(f'_...and {len(items) - 15} more items._')

    payload = {'text': '\n'.join(lines)}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=5)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning('Webhook notification failed: %s', exc)
        return False
