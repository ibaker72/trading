# Worker

Phase 7 queue-based worker prototype (RQ + Redis).

## Files
- `worker_queue.py`: Redis and queue setup.
- `jobs.py`: job functions (currently `reconcile_user`).
- `scheduler.py`: enqueues reconcile jobs for configured user IDs.
- `worker.py`: runs the RQ worker.
- `reconcile_worker.py`: legacy direct-call script from previous phase.

## Local run
```bash
cd services/worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python worker.py
```

In another shell enqueue jobs:

```bash
python scheduler.py
```
