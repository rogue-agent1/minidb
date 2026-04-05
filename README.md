# MiniDB

![Version](https://img.shields.io/badge/version-0.4.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A lightweight, zero-dependency key-value store backed by JSON. Single file, production-grade primitives.

Forked from [rogue-agent1/minidb](https://github.com/rogue-agent1/minidb).

## Features

- **TTL support** - per-key expiry with lazy cleanup and `compact()`
- **Atomic writes** - crash-safe via temp file + `os.replace()`
- **File locking** - safe for concurrent processes (`fcntl` on Unix, `msvcrt` on Windows, sentinel fallback)
- **Batch operations** - `put_many`, `get_many`, `delete_many` with a single write per batch
- **Prefix scan** - namespace your keys and query by prefix
- **Stored `None`** - distinguishes a missing key from a key with a `None` value
- **Zero dependencies** - stdlib only (`json`, `os`, `time`, `tempfile`, `fcntl`/`msvcrt`)

## Installation

No install needed. Copy `minidb.py` into your project.

## Usage

```python
from minidb import MiniDB

db = MiniDB("mydb.json")

# Basic ops
db.put("user:1", {"name": "Alice", "age": 30})
db.get("user:1")        # {"name": "Alice", "age": 30}
db.exists("user:1")     # True
db.delete("user:1")

# TTL - expires in 5 minutes
db.put("session:abc", {"token": "xyz"}, ttl=300)

# Default value for missing keys
db.get("missing", default="fallback")   # "fallback"

# Storing None as a value
db.put("flag", None)
db.get("flag")          # None
db.exists("flag")       # True  (distinguishable from a missing key)

# Batch ops - single disk write per call
db.put_many({"a": 1, "b": 2, "c": 3})
db.put_many([("x", 10, 60), ("y", 20, 120)])   # per-item TTL
db.get_many(["a", "b", "missing"])              # {"a": 1, "b": 2}
db.delete_many(["a", "b"])

# Prefix scan
db.put_many({"user:1": "alice", "user:2": "bob", "config:theme": "dark"})
db.scan("user:")        # {"user:1": "alice", "user:2": "bob"}

# Housekeeping
db.keys()               # all non-expired keys
db.count()              # number of non-expired keys
db.compact()            # purge expired keys, rewrite file, return remaining count

# Write buffering - batch disk writes for high-throughput workloads
db = MiniDB("mydb.json", flush_interval=5)     # flush every 5 seconds
db = MiniDB("mydb.json", flush_ops=100)         # flush every 100 mutations
db = MiniDB("mydb.json", flush_interval=5, flush_ops=100)  # whichever comes first

db.put("a", 1)   # held in memory, not written to disk yet
db.put("b", 2)   # still buffered
db.flush()       # force immediate write
db.close()       # flush remaining buffer and stop timer (also called on exit)


with db.transaction():
    db.put("account:alice", 900)
    db.put("account:bob", 1100)
    # Both commit together, or neither if an exception occurs

# Rollback on failure - nothing is written to disk
try:
    with db.transaction():
        db.put("x", "new_value")
        raise ValueError("something went wrong")
except ValueError:
    pass
db.get("x")   # original value - rollback succeeded

# All existing ops work inside transactions
with db.transaction():
    db.put_many({"a": 1, "b": 2})
    db.delete("stale_key")
    db.scan("user:")

```

```bash
python -m unittest test_minidb -v
```

58 tests across basic ops, persistence, TTL, batch ops, prefix scan, concurrency, transactions, and write buffering.

## License

MIT - see [LICENSE](LICENSE).  
Based on [rogue-agent1/minidb](https://github.com/rogue-agent1/minidb).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

