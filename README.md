# kube-cleaner

> Automated **Kubernetes cluster housekeeping daemon** for reaping evicted pods, completed/failed jobs, and stale resources in **Python**.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://python.org)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Client-326CE5?style=flat-square&logo=kubernetes)](https://kubernetes.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

`#kubernetes` `#k8s-cleaner` `#cronjob` `#devops` `#cloud-native` `#python` `#cluster-maintenance`

---

## Features

- **Evicted & Failed Pod Reaper:** Automatically removes pods stuck in `Evicted`, `CrashLoopBackOff` dead phases to keep nodes clean.
- **Completed Batch Job Cleanup:** Prunes successfully completed K8s `BatchV1` jobs.
- **Dry-Run Mode:** Test and audit what would be removed without deleting anything (`--dry-run`).
- **Slack / Discord Notifications:** Dispatches cleanup summaries to team channels.
- **In-Cluster CronJob Ready:** Deploy as a scheduled K8s CronJob with fine-grained RBAC.

## Quick Start

### Run Locally / CLI

```bash
# Dry run across all namespaces
python -m kube_cleaner.main --dry-run

# Execute cleanup on specific namespace
python -m kube_cleaner.main -n staging --webhook-url=https://hooks.slack.com/...
```

### Deploy to Kubernetes

```bash
kubectl apply -f deploy/rbac.yaml
kubectl apply -f deploy/cronjob.yaml
```
