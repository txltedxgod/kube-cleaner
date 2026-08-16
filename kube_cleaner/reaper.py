from kubernetes import client
from typing import List, Dict


class KubeReaper:
    def __init__(self, core_api: client.CoreV1Api, batch_api: client.BatchV1Api, dry_run: bool = False):
        self.core_api = core_api
        self.batch_api = batch_api
        self.dry_run = dry_run

    def reap_stale_pods(self, namespace: str = "") -> List[Dict[str, str]]:
        reaped = []
        if namespace:
            pods = self.core_api.list_namespaced_pod(namespace).items
        else:
            pods = self.core_api.list_pod_for_all_namespaces().items

        for pod in pods:
            ns = pod.metadata.namespace
            name = pod.metadata.name
            phase = pod.status.phase
            reason = pod.status.reason or ""

            # Check if pod is Evicted, Succeeded, or Failed with CrashLoopBackOff/Dead
            if reason == "Evicted" or phase in ("Succeeded", "Failed"):
                action = "WOULD_DELETE" if self.dry_run else "DELETED"
                if not self.dry_run:
                    try:
                        self.core_api.delete_namespaced_pod(name, ns)
                    except Exception as e:
                        continue
                reaped.append({"type": "pod", "namespace": ns, "name": name, "reason": f"{phase}:{reason}", "action": action})

        return reaped

    def reap_completed_jobs(self, namespace: str = "") -> List[Dict[str, str]]:
        reaped = []
        if namespace:
            jobs = self.batch_api.list_namespaced_job(namespace).items
        else:
            jobs = self.batch_api.list_job_for_all_namespaces().items

        for job in jobs:
            ns = job.metadata.namespace
            name = job.metadata.name
            if job.status.succeeded and job.status.succeeded > 0:
                action = "WOULD_DELETE" if self.dry_run else "DELETED"
                if not self.dry_run:
                    try:
                        self.batch_api.delete_namespaced_job(name, ns, propagation_policy="Background")
                    except Exception:
                        continue
                reaped.append({"type": "job", "namespace": ns, "name": name, "reason": "Completed", "action": action})

        return reaped
