# test_minidb.py
#
# MIT License
# Copyright (c) 2026 John (JT) Thornton 
# See LICENSE file for full license text.

import unittest, threading, os, time, tempfile
from minidb import MiniDB


def _db(tmp_dir, name="test.json", **kwargs):
    """Helper: create a MiniDB in a temp directory."""
    return MiniDB(os.path.join(tmp_dir, name), **kwargs)


class TestBasicOps(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = _db(self.tmp)

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, f))

    def test_put_and_get(self):
        self.db.put("k", "v")
        self.assertEqual(self.db.get("k"), "v")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.db.get("no_such_key"))

    def test_overwrite(self):
        self.db.put("k", "v1")
        self.db.put("k", "v2")
        self.assertEqual(self.db.get("k"), "v2")

    def test_delete(self):
        self.db.put("k", "v")
        self.db.delete("k")
        self.assertIsNone(self.db.get("k"))

    def test_delete_missing_no_error(self):
        self.db.delete("ghost")

    def test_exists_true(self):
        self.db.put("k", "v")
        self.assertTrue(self.db.exists("k"))

    def test_exists_false(self):
        self.assertFalse(self.db.exists("nope"))

    def test_count(self):
        self.db.put("a", 1)
        self.db.put("b", 2)
        self.assertEqual(self.db.count(), 2)

    def test_keys(self):
        self.db.put("x", 1)
        self.db.put("y", 2)
        self.assertCountEqual(self.db.keys(), ["x", "y"])

    def test_value_types(self):
        self.db.put("int", 42)
        self.db.put("float", 3.14)
        self.db.put("list", [1, 2, 3])
        self.db.put("dict", {"a": 1})
        self.assertEqual(self.db.get("int"), 42)
        self.assertAlmostEqual(self.db.get("float"), 3.14)
        self.assertEqual(self.db.get("list"), [1, 2, 3])
        self.assertEqual(self.db.get("dict"), {"a": 1})

    def test_store_none_value(self):
        self.db.put("null_key", None)
        self.assertIsNone(self.db.get("null_key"))
        self.assertTrue(self.db.exists("null_key"))

    def test_none_value_vs_missing_key(self):
        self.db.put("null_key", None)
        self.assertTrue(self.db.exists("null_key"))
        self.assertFalse(self.db.exists("no_such_key"))

    def test_get_with_default(self):
        self.db.put("present", "v")
        self.assertEqual(self.db.get("present", "fallback"), "v")
        self.assertEqual(self.db.get("missing", "fallback"), "fallback")
        self.assertEqual(self.db.get("missing", default=0), 0)

    def test_get_default_does_not_mask_stored_none(self):
        self.db.put("null_key", None)
        self.assertIsNone(self.db.get("null_key", "fallback"))


class TestPersistence(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, f))

    def test_survives_reload(self):
        db1 = _db(self.tmp)
        db1.put("persist", "yes")
        db2 = _db(self.tmp)
        self.assertEqual(db2.get("persist"), "yes")

    def test_delete_survives_reload(self):
        db1 = _db(self.tmp)
        db1.put("k", "v")
        db1.delete("k")
        db2 = _db(self.tmp)
        self.assertIsNone(db2.get("k"))

    def test_atomic_write_leaves_no_tmp_files(self):
        db = _db(self.tmp)
        db.put("k", "v")
        tmp_files = [f for f in os.listdir(self.tmp) if f.endswith(".tmp")]
        self.assertEqual(tmp_files, [])


class TestTTL(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = _db(self.tmp)

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, f))

    def test_no_ttl_persists(self):
        self.db.put("k", "v")
        time.sleep(0.1)
        self.assertEqual(self.db.get("k"), "v")

    def test_ttl_expires(self):
        self.db.put("k", "v", ttl=0.1)
        time.sleep(0.2)
        self.assertIsNone(self.db.get("k"))

    def test_ttl_not_yet_expired(self):
        self.db.put("k", "v", ttl=5)
        self.assertEqual(self.db.get("k"), "v")

    def test_expired_key_removed_from_disk(self):
        self.db.put("k", "v", ttl=0.1)
        time.sleep(0.2)
        self.db.get("k")
        db2 = _db(self.tmp)
        self.assertIsNone(db2.get("k"))

    def test_expired_key_excluded_from_keys(self):
        self.db.put("live", "v", ttl=5)
        self.db.put("dead", "v", ttl=0.1)
        time.sleep(0.2)
        self.assertIn("live", self.db.keys())
        self.assertNotIn("dead", self.db.keys())

    def test_expired_key_excluded_from_count(self):
        self.db.put("live", "v", ttl=5)
        self.db.put("dead", "v", ttl=0.1)
        time.sleep(0.2)
        self.assertEqual(self.db.count(), 1)

    def test_compact_purges_expired(self):
        self.db.put("live", "v", ttl=5)
        self.db.put("dead", "v", ttl=0.1)
        time.sleep(0.2)
        remaining = self.db.compact()
        self.assertEqual(remaining, 1)
        db2 = _db(self.tmp)
        self.assertIsNone(db2.get("dead"))


class TestBatchOps(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = _db(self.tmp)

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, f))

    def test_put_many_dict(self):
        self.db.put_many({"a": 1, "b": 2, "c": 3})
        self.assertEqual(self.db.get("a"), 1)
        self.assertEqual(self.db.get("b"), 2)
        self.assertEqual(self.db.get("c"), 3)

    def test_put_many_tuples(self):
        self.db.put_many([("x", 10), ("y", 20)])
        self.assertEqual(self.db.get("x"), 10)
        self.assertEqual(self.db.get("y"), 20)

    def test_put_many_with_uniform_ttl(self):
        self.db.put_many({"a": 1, "b": 2}, ttl=0.1)
        time.sleep(0.2)
        self.assertIsNone(self.db.get("a"))
        self.assertIsNone(self.db.get("b"))

    def test_put_many_per_item_ttl(self):
        self.db.put_many([("live", "v", 5), ("dead", "v", 0.1)])
        time.sleep(0.2)
        self.assertEqual(self.db.get("live"), "v")
        self.assertIsNone(self.db.get("dead"))

    def test_get_many(self):
        self.db.put_many({"a": 1, "b": 2, "c": 3})
        result = self.db.get_many(["a", "c"])
        self.assertEqual(result, {"a": 1, "c": 3})

    def test_get_many_missing_omitted(self):
        self.db.put("a", 1)
        result = self.db.get_many(["a", "missing"])
        self.assertIn("a", result)
        self.assertNotIn("missing", result)

    def test_get_many_expired_omitted(self):
        self.db.put("live", "v", ttl=5)
        self.db.put("dead", "v", ttl=0.1)
        time.sleep(0.2)
        result = self.db.get_many(["live", "dead"])
        self.assertIn("live", result)
        self.assertNotIn("dead", result)

    def test_delete_many(self):
        self.db.put_many({"a": 1, "b": 2, "c": 3})
        self.db.delete_many(["a", "b"])
        self.assertIsNone(self.db.get("a"))
        self.assertIsNone(self.db.get("b"))
        self.assertEqual(self.db.get("c"), 3)

    def test_put_many_single_save(self):
        """Verify put_many writes exactly once regardless of item count."""
        save_count = {"n": 0}
        original_save = self.db._save
        def counting_save():
            save_count["n"] += 1
            original_save()
        self.db._save = counting_save
        self.db.put_many({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5})
        self.assertEqual(save_count["n"], 1)


class TestScan(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = _db(self.tmp)
        self.db.put_many({
            "user:1": "alice",
            "user:2": "bob",
            "session:abc": "data",
        })

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, f))

    def test_scan_prefix(self):
        result = self.db.scan("user:")
        self.assertCountEqual(result.keys(), ["user:1", "user:2"])

    def test_scan_empty_prefix_returns_all(self):
        result = self.db.scan("")
        self.assertEqual(len(result), 3)

    def test_scan_no_match(self):
        result = self.db.scan("order:")
        self.assertEqual(result, {})

    def test_scan_excludes_expired(self):
        self.db.put("user:temp", "v", ttl=0.1)
        time.sleep(0.2)
        result = self.db.scan("user:")
        self.assertNotIn("user:temp", result)


class TestConcurrency(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for f in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, f))

    def test_threaded_writes_no_corruption(self):
        db = _db(self.tmp)
        errors = []

        def writer(n):
            try:
                for i in range(10):
                    db.put(f"thread{n}_key{i}", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(errors, [])
        db2 = _db(self.tmp)
        self.assertIsInstance(db2.data, dict)

    def test_threaded_reads_concurrent(self):
        db = _db(self.tmp)
        db.put_many({f"k{i}": i for i in range(20)})
        errors = []

        def reader():
            try:
                for i in range(20):
                    db.get(f"k{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])

    def test_mixed_read_write_threads(self):
        db = _db(self.tmp)
        errors = []

        def worker(n):
            try:
                for _ in range(5):
                    db.put(f"w{n}", n)
                    db.get(f"w{n}")
                    db.delete(f"w{n}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
