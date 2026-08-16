import requests
from typing import List, Dict


def send_webhook_report(webhook_url: str, items: List[Dict[str, str]], dry_run: bool):
    if not webhook_url or not items:
        return

    mode = "DRY-RUN" if dry_run else "EXECUTED"
    lines = [f"🧹 **Kube-Cleaner Report [{mode}]**", f"Cleaned up {len(items)} orphaned resources:\n"]
    for item in items[:15]:
        lines.append(f"- `[{item['type'].upper()}]` {item['namespace']}/{item['name']} ({item['reason']}) -> {item['action']}")

    if len(items) > 15:
        lines.append(f"_...and {len(items) - 15} more items._")

    payload = {"text": "\n".join(lines)}
    try:
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        print(f"[Warning] Webhook notification failed: {e}")
