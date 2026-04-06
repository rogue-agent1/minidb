#!/usr/bin/env python3
"""
demo.py — MiniDB Job Queue Demo

A realistic job queue built on MiniDB demonstrating all major features:
  - Basic ops, TTL, batch ops, transactions, write buffering,
    query(), Q objects, update_where(), delete_where(), compact()

Run with: python3 demo.py
"""

import time, os, tempfile
from minidb import MiniDB, Q, __version__

# ---------------------------------------------------------------------------
# Setup — use a temp directory so the demo is self-contained
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(tempfile.mkdtemp(), "jobqueue.json")

def divider(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def show(label, value):
    print(f"  {label:<30} {value}")

# ---------------------------------------------------------------------------
# 1. Open the database with write buffering
# ---------------------------------------------------------------------------

divider("1. Open DB")
db = MiniDB(DB_PATH)
print(f"  DB path : {DB_PATH}")
print(f"  Version : {__version__}")

# ---------------------------------------------------------------------------
# 2. Enqueue jobs — basic put
# ---------------------------------------------------------------------------

divider("2. Enqueue individual jobs")

db.put("job:1001", {
    "task": "send_email",
    "payload": {"to": "alice@example.com", "subject": "Welcome"},
    "priority": 1,
    "status": "pending",
    "created_at": time.time(),
})

db.put("job:1002", {
    "task": "generate_report",
    "payload": {"report_id": "Q1-2026"},
    "priority": 2,
    "status": "pending",
    "created_at": time.time(),
})

db.put("job:1003", {
    "task": "resize_image",
    "payload": {"file": "avatar.png", "size": 128},
    "priority": 3,
    "status": "pending",
    "created_at": time.time(),
})

show("Jobs enqueued:", db.count())

# ---------------------------------------------------------------------------
# 3. Batch enqueue — put_many
# ---------------------------------------------------------------------------

divider("3. Batch enqueue 5 jobs (single disk write)")

db.put_many([
    ("job:1004", {"task": "sync_inventory",  "payload": {"sku": "ABC"},  "priority": 2, "status": "pending", "created_at": time.time()}),
    ("job:1005", {"task": "send_sms",        "payload": {"to": "+1555"}, "priority": 1, "status": "pending", "created_at": time.time()}),
    ("job:1006", {"task": "cleanup_logs",    "payload": {"days": 30},    "priority": 3, "status": "pending", "created_at": time.time()}),
    ("job:1007", {"task": "send_email",      "payload": {"to": "bob@example.com"}, "priority": 1, "status": "pending", "created_at": time.time()}),
    ("job:1008", {"task": "generate_report", "payload": {"report_id": "Q2-2026"},  "priority": 2, "status": "pending", "created_at": time.time()}),
])

show("Jobs after batch enqueue:", db.count())

# ---------------------------------------------------------------------------
# 4. Enqueue jobs with TTL — expire if not claimed in time
# ---------------------------------------------------------------------------

divider("4. Enqueue short-lived jobs (TTL = 1 second)")

db.put("job:9001", {
    "task": "ping_healthcheck",
    "payload": {"url": "https://api.example.com/health"},
    "priority": 1,
    "status": "pending",
    "created_at": time.time(),
}, ttl=1)

db.put("job:9002", {
    "task": "ping_healthcheck",
    "payload": {"url": "https://cdn.example.com/health"},
    "priority": 1,
    "status": "pending",
    "created_at": time.time(),
}, ttl=1)

show("Jobs including TTL jobs:", db.count())

# ---------------------------------------------------------------------------
# 5. Query pending jobs — Q objects
# ---------------------------------------------------------------------------

divider("5. Query pending jobs using Q objects")

# All pending jobs
pending = db.query("job:", where=Q(status="pending"))
show("All pending jobs:", len(pending))

# High priority pending (priority 1)
high_priority = db.query("job:",
    where=Q(status="pending") & Q(priority=1),
    order_by='priority')
show("High priority (p1) pending:", len(high_priority))
for j in high_priority:
    print(f"    {j['_key']} → {j['task']}")

# Email jobs specifically
email_jobs = db.query("job:",
    where=Q(status="pending") & Q(task="send_email"))
show("Pending email jobs:", len(email_jobs))

# Top 3 jobs by priority
top3 = db.query("job:",
    where=Q(status="pending"),
    order_by='priority',
    limit=3,
    columns=['task', 'priority', 'status'])
show("Top 3 jobs by priority:", "")
for j in top3:
    print(f"    {j['_key']} → {j['task']} (p{j['priority']})")

# ---------------------------------------------------------------------------
# 6. Claim a job — transaction
# ---------------------------------------------------------------------------

divider("6. Claim job:1001 atomically (transaction)")

with db.transaction():
    job = db.get("job:1001")
    if job and job['status'] == 'pending':
        job['status'] = 'running'
        job['claimed_at'] = time.time()
        db.put("job:1001", job)

claimed = db.get("job:1001")
show("job:1001 status:", claimed['status'])

# ---------------------------------------------------------------------------
# 7. Complete a job
# ---------------------------------------------------------------------------

divider("7. Complete job:1001")

with db.transaction():
    job = db.get("job:1001")
    job['status'] = 'completed'
    job['completed_at'] = time.time()
    db.put("job:1001", job)

show("job:1001 status:", db.get("job:1001")['status'])

# ---------------------------------------------------------------------------
# 8. Simulate failures — update_where
# ---------------------------------------------------------------------------

divider("8. Mark all priority-3 jobs as failed (update_where + Q)")

count = db.update_where("job:",
    where=Q(status="pending") & Q(priority=3),
    updates={'status': 'failed', 'failed_at': time.time()})

show("Jobs marked failed:", count)
failed = db.query("job:", where=Q(status="failed"))
for j in failed:
    print(f"    {j['_key']} → {j['task']}")

# ---------------------------------------------------------------------------
# 9. Retry one failed job atomically — transaction
# ---------------------------------------------------------------------------

divider("9. Retry job:1003 atomically (transaction)")

show("job:1003 status before:", db.get("job:1003")['status'])

with db.transaction():
    job = db.get("job:1003")
    if job and job['status'] == 'failed':
        job['status'] = 'pending'
        job['retries'] = job.get('retries', 0) + 1
        db.put("job:1003", job)

show("job:1003 status after:", db.get("job:1003")['status'])
show("job:1003 retry count:", db.get("job:1003").get('retries', 0))
show("Remaining failed jobs:", len(db.query("job:", where=Q(status="failed"))))

# ---------------------------------------------------------------------------
# 10. TTL expiry
# ---------------------------------------------------------------------------

divider("10. TTL expiry — healthcheck jobs expire after 1 second")

print("  Waiting 1.5 seconds for TTL jobs to expire...")
time.sleep(1.5)

expired_check = db.get("job:9001")
show("job:9001 after TTL:", expired_check)  # None — expired

pending_after = db.query("job:", where=Q(status="pending"))
show("Pending jobs after expiry:", len(pending_after))

# ---------------------------------------------------------------------------
# 11. compact() — purge expired keys
# ---------------------------------------------------------------------------

divider("11. compact() — purge expired TTL jobs from disk")

# Count raw keys in data including expired ones still on disk
before = len(db.data)
remaining = db.compact()
show("Raw keys before compact:", before)
show("Keys after compact:", remaining)
show("Expired keys removed:", before - remaining)

# ---------------------------------------------------------------------------
# 12. Delete completed jobs — delete_where
# ---------------------------------------------------------------------------

divider("12. Delete completed jobs (delete_where + Q)")

deleted = db.delete_where("job:", where=Q(status="completed"))
show("Completed jobs deleted:", deleted)
show("Remaining jobs:", db.count())

# ---------------------------------------------------------------------------
# 13. Write buffering — high-throughput ingestion
# ---------------------------------------------------------------------------

divider("13. Write buffering — batch 20 jobs with flush_ops=10")

BUFFER_PATH = os.path.join(tempfile.mkdtemp(), "buffered.json")
db_buf = MiniDB(BUFFER_PATH, flush_ops=10)

for i in range(20):
    db_buf.put(f"bulkjob:{i:04d}", {
        "task": "bulk_process",
        "index": i,
        "status": "pending"
    })

# First 10 ops auto-flushed, second 10 still buffered
show("File exists after 20 puts:", os.path.exists(BUFFER_PATH))
show("Dirty (unflushed ops):", db_buf._dirty)
db_buf.close()  # flushes remaining buffer
show("File exists after close():", os.path.exists(BUFFER_PATH))
show("Total buffered jobs on disk:", MiniDB(BUFFER_PATH).count())

# ---------------------------------------------------------------------------
# 14. Persistence — reload from disk
# ---------------------------------------------------------------------------

divider("14. Persistence — flush and reload DB")

db.flush()
db2 = MiniDB(DB_PATH)
show("Jobs reloaded from disk:", db2.count())

pending_reloaded = db2.query("job:", where=Q(status="pending"), order_by='priority')
print("  Pending jobs after reload:")
for j in pending_reloaded:
    print(f"    {j['_key']} → {j['task']} (p{j['priority']})")

# ---------------------------------------------------------------------------
# 14. Final stats
# ---------------------------------------------------------------------------

divider("15. Final queue summary")

all_jobs = db2.query("job:")
statuses = {}
for j in all_jobs:
    statuses[j['status']] = statuses.get(j['status'], 0) + 1

show("Total jobs:", len(all_jobs))
for status, count in sorted(statuses.items()):
    show(f"  {status}:", count)

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

db.close()
print(f"\n{'─' * 60}")
print("  Demo complete.")
print(f"{'─' * 60}\n")
