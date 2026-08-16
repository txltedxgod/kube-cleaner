import click
import os
from kubernetes import config, client
from .reaper import KubeReaper
from .notifier import send_webhook_report


@click.command()
@click.option("-n", "--namespace", default="", help="Target namespace (empty for all namespaces)")
@click.option("--dry-run", is_flag=True, help="Simulate deletion without making changes")
@click.option("--webhook-url", default=lambda: os.getenv("CLEANER_WEBHOOK_URL", ""), help="Slack/Discord webhook URL for notifications")
def main(namespace: str, dry_run: bool, webhook_url: str):
    """Kubernetes cluster cleaner & orphaned resource reaper."""
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()

    core_api = client.CoreV1Api()
    batch_api = client.BatchV1Api()

    reaper = KubeReaper(core_api, batch_api, dry_run=dry_run)

    print(f"[*] Scanning cluster resources (Dry-run: {dry_run})...")
    pods_reaped = reaper.reap_stale_pods(namespace)
    jobs_reaped = reaper.reap_completed_jobs(namespace)

    total_reaped = pods_reaped + jobs_reaped
    print(f"[+] Found & processed {len(total_reaped)} resources ({len(pods_reaped)} pods, {len(jobs_reaped)} jobs).")

    if webhook_url:
        send_webhook_report(webhook_url, total_reaped, dry_run)


if __name__ == "__main__":
    main()
