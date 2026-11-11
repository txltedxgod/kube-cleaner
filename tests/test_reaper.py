from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from kubernetes.client.exceptions import ApiException

from kube_cleaner import main as main_mod
from kube_cleaner.notifier import send_webhook_report
from kube_cleaner.reaper import KubeReaper


def _pod(name, namespace='default', phase='Running', reason=None, deleting=False, finished_ago=None):
    statuses = []
    if finished_ago is not None:
        statuses.append(
            SimpleNamespace(
                state=SimpleNamespace(
                    terminated=SimpleNamespace(finished_at=datetime.now(UTC) - timedelta(seconds=finished_ago))
                )
            )
        )
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name,
            namespace=namespace,
            deletion_timestamp=datetime.now(UTC) if deleting else None,
        ),
        status=SimpleNamespace(
            phase=phase,
            reason=reason,
            start_time=datetime.now(UTC) - timedelta(hours=1),
            container_statuses=statuses,
        ),
    )


def _job(name, namespace='default', succeeded=1, deleting=False, completed_ago=3600):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name,
            namespace=namespace,
            deletion_timestamp=datetime.now(UTC) if deleting else None,
        ),
        status=SimpleNamespace(
            succeeded=succeeded,
            completion_time=datetime.now(UTC) - timedelta(seconds=completed_ago),
        ),
    )


class FakeCoreApi:
    def __init__(self, pods, fail_names=None):
        self.pods = pods
        self.fail_names = set(fail_names or [])
        self.deleted = []

    def list_namespaced_pod(self, namespace):
        return SimpleNamespace(items=[p for p in self.pods if p.metadata.namespace == namespace])

    def list_pod_for_all_namespaces(self):
        return SimpleNamespace(items=self.pods)

    def delete_namespaced_pod(self, name, ns):
        if name in self.fail_names:
            raise ApiException(status=403, reason='Forbidden')
        self.deleted.append((ns, name))


class FakeBatchApi:
    def __init__(self, jobs, fail_names=None):
        self.jobs = jobs
        self.fail_names = set(fail_names or [])
        self.deleted = []

    def list_namespaced_job(self, namespace):
        return SimpleNamespace(items=[j for j in self.jobs if j.metadata.namespace == namespace])

    def list_job_for_all_namespaces(self):
        return SimpleNamespace(items=self.jobs)

    def delete_namespaced_job(self, name, ns, propagation_policy='Background'):
        if name in self.fail_names:
            raise ApiException(status=500, reason='Server Error')
        self.deleted.append((ns, name, propagation_policy))


def test_reap_stale_pods_handles_evicted_age_deleting_and_api_errors():
    pods = [
        _pod('healthy', phase='Running'),
        _pod('already-deleting', phase='Failed', deleting=True),
        _pod('too-fresh', phase='Succeeded', finished_ago=10),
        _pod('evicted-old', phase='Failed', reason='Evicted', finished_ago=600),
        _pod('forbidden-pod', phase='Succeeded', finished_ago=600),
    ]
    core = FakeCoreApi(pods, fail_names={'forbidden-pod'})
    reaper = KubeReaper(core, FakeBatchApi([]), dry_run=False, min_age_seconds=300)

    res = reaper.reap_stale_pods()
    assert core.deleted == [('default', 'evicted-old')]
    assert [item['name'] for item in res] == ['evicted-old']

    with pytest.raises(ValueError, match='non-negative'):
        KubeReaper(core, FakeBatchApi([]), min_age_seconds=-5)


def test_reap_completed_jobs_and_dry_run():
    jobs = [
        _job('active-job', succeeded=0),
        _job('deleting-job', succeeded=1, deleting=True),
        _job('recent-job', succeeded=1, completed_ago=30),
        _job('done-job', namespace='batch', succeeded=1, completed_ago=900),
    ]
    batch = FakeBatchApi(jobs)
    reaper = KubeReaper(FakeCoreApi([]), batch, dry_run=True, min_age_seconds=120)

    res = reaper.reap_completed_jobs('batch')
    assert batch.deleted == []
    assert len(res) == 1
    assert res[0]['name'] == 'done-job'
    assert res[0]['action'] == 'WOULD_DELETE'


def test_notifier_validates_scheme_and_reports_payload(monkeypatch):
    assert send_webhook_report('ftp://bad.host/hook', [{'type': 'pod'}], dry_run=True) is False

    sent = []

    class FakeResp:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        sent.append((url, json, timeout))
        return FakeResp()

    monkeypatch.setattr('kube_cleaner.notifier.requests.post', fake_post)
    ok = send_webhook_report(
        'https://hooks.example.com/123',
        [{'type': 'pod', 'namespace': 'prod', 'name': 'job-1', 'reason': 'Failed:', 'action': 'DELETED'}],
        dry_run=False,
    )
    assert ok is True
    assert 'job-1' in sent[0][1]['text']


def test_cli_dry_run(monkeypatch):
    core = FakeCoreApi([_pod('stale', phase='Succeeded')])
    batch = FakeBatchApi([_job('done', succeeded=1)])
    monkeypatch.setattr(main_mod.config, 'load_incluster_config', lambda: None)
    monkeypatch.setattr(main_mod.client, 'CoreV1Api', lambda: core)
    monkeypatch.setattr(main_mod.client, 'BatchV1Api', lambda: batch)

    runner = CliRunner()
    res = runner.invoke(main_mod.main, ['--dry-run', '--min-age', '0'])
    assert res.exit_code == 0, res.output
    assert '2 resources (1 pods, 1 jobs)' in res.output
