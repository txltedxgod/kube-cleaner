import logging
from datetime import UTC, datetime

from kubernetes import client
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)


def _age_seconds(timestamp: datetime | None, now: datetime) -> float | None:
    if timestamp is None:
        return None
    ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
    return (now - ts).total_seconds()


def _pod_eligible_by_age(pod, min_age_seconds: int, now: datetime) -> bool:
    if min_age_seconds <= 0:
        return True
    finished_times = []
    for cs in getattr(pod.status, 'container_statuses', None) or []:
        terminated = getattr(getattr(cs, 'state', None), 'terminated', None)
        if terminated and terminated.finished_at:
            finished_times.append(terminated.finished_at)
    ref_time = max(finished_times) if finished_times else getattr(pod.status, 'start_time', None)
    age = _age_seconds(ref_time, now)
    return age is None or age >= min_age_seconds


class KubeReaper:
    def __init__(
        self,
        core_api: client.CoreV1Api,
        batch_api: client.BatchV1Api,
        dry_run: bool = False,
        min_age_seconds: int = 0,
    ):
        if min_age_seconds < 0:
            raise ValueError('min_age_seconds must be non-negative')
        self.core_api = core_api
        self.batch_api = batch_api
        self.dry_run = dry_run
        self.min_age_seconds = min_age_seconds

    def reap_stale_pods(self, namespace: str = '') -> list[dict[str, str]]:
        reaped: list[dict[str, str]] = []
        if namespace:
            pods = self.core_api.list_namespaced_pod(namespace).items
        else:
            pods = self.core_api.list_pod_for_all_namespaces().items

        now = datetime.now(UTC)
        for pod in pods:
            if pod.metadata.deletion_timestamp is not None:
                continue

            status = pod.status
            if status is None:
                continue

            ns = pod.metadata.namespace
            name = pod.metadata.name
            phase = status.phase or ''
            reason = status.reason or ''

            if (reason == 'Evicted' or phase in ('Succeeded', 'Failed')) and _pod_eligible_by_age(
                pod, self.min_age_seconds, now
            ):
                action = 'WOULD_DELETE' if self.dry_run else 'DELETED'
                if not self.dry_run:
                    try:
                        self.core_api.delete_namespaced_pod(name, ns)
                    except ApiException as exc:
                        logger.warning('failed to delete pod %s/%s: %s', ns, name, exc)
                        continue
                reaped.append({
                    'type': 'pod',
                    'namespace': ns,
                    'name': name,
                    'reason': f'{phase}:{reason}',
                    'action': action,
                })

        return reaped

    def reap_completed_jobs(self, namespace: str = '') -> list[dict[str, str]]:
        reaped: list[dict[str, str]] = []
        if namespace:
            jobs = self.batch_api.list_namespaced_job(namespace).items
        else:
            jobs = self.batch_api.list_job_for_all_namespaces().items

        now = datetime.now(UTC)
        for job in jobs:
            if job.metadata.deletion_timestamp is not None:
                continue

            status = job.status
            if not status or not (status.succeeded and status.succeeded > 0):
                continue

            if self.min_age_seconds > 0:
                age = _age_seconds(getattr(status, 'completion_time', None), now)
                if age is not None and age < self.min_age_seconds:
                    continue

            ns = job.metadata.namespace
            name = job.metadata.name
            action = 'WOULD_DELETE' if self.dry_run else 'DELETED'
            if not self.dry_run:
                try:
                    self.batch_api.delete_namespaced_job(
                        name, ns, propagation_policy='Background'
                    )
                except ApiException as exc:
                    logger.warning('failed to delete job %s/%s: %s', ns, name, exc)
                    continue
            reaped.append({
                'type': 'job',
                'namespace': ns,
                'name': name,
                'reason': 'Completed',
                'action': action,
            })

        return reaped
