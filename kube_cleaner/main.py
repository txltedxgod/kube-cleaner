import logging
import os

import click
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from .notifier import send_webhook_report
from .reaper import KubeReaper

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')


@click.command()
@click.option('-n', '--namespace', default='', help='Target namespace (empty for all namespaces)')
@click.option('--dry-run', is_flag=True, help='Simulate deletion without making changes')
@click.option('--min-age', 'min_age_seconds', default=0, type=int, help='Minimum completed age in seconds')
@click.option(
    '--webhook-url',
    default=lambda: os.getenv('CLEANER_WEBHOOK_URL', ''),
    help='Slack/Discord webhook URL for notifications',
)
def main(namespace: str, dry_run: bool, min_age_seconds: int, webhook_url: str):
    """Kubernetes cluster cleaner & orphaned resource reaper."""
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()

    core_api = client.CoreV1Api()
    batch_api = client.BatchV1Api()

    reaper = KubeReaper(
        core_api,
        batch_api,
        dry_run=dry_run,
        min_age_seconds=min_age_seconds,
    )

    print(f'[*] Scanning cluster resources (Dry-run: {dry_run})...')
    pods_reaped = reaper.reap_stale_pods(namespace)
    jobs_reaped = reaper.reap_completed_jobs(namespace)

    total_reaped = pods_reaped + jobs_reaped
    print(
        f'[+] Found & processed {len(total_reaped)} resources '
        f'({len(pods_reaped)} pods, {len(jobs_reaped)} jobs).'
    )

    if webhook_url:
        send_webhook_report(webhook_url, total_reaped, dry_run)


if __name__ == '__main__':
    main()
