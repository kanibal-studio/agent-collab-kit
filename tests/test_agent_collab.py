import multiprocessing
from pathlib import Path
import tempfile
import unittest

from agent_collab import Conflict, Store


def race_claim(db, ready, start, result):
    store = Store(db)
    ready.put(True)
    start.wait(10)
    try:
        store.claim("src/shared.py", "worker", 60)
        result.put("claimed")
    except Conflict:
        result.put("conflict")
    finally:
        store.close()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "test.db")
        self.time = 100.0
        Store.initialize(self.db)
        self.store = Store(self.db, clock=lambda: self.time)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_idempotency_and_mismatch(self):
        first = self.store.send("a", "b", "hello", "one")
        self.assertEqual(first, self.store.send("a", "b", "hello", "one"))
        for payload in (("x", "b", "hello"), ("a", "x", "hello"),
                        ("a", "b", "changed")):
            with self.assertRaises(Conflict):
                self.store.send(*payload, "one")
        self.assertEqual(1, len(self.store.inbox("b")))

    def test_inbox_ack_recipient_and_persistence(self):
        message = self.store.send("a", "b", "hello", "one")
        self.assertEqual([], self.store.inbox("a"))
        with self.assertRaises(Conflict):
            self.store.ack(message["id"], "a")
        self.assertEqual(1, len(self.store.inbox("b")))
        acknowledged = self.store.ack(message["id"], "b")
        self.assertEqual(acknowledged, self.store.ack(message["id"], "b"))
        self.store.close()
        self.store = Store(self.db, clock=lambda: self.time)
        self.assertEqual([], self.store.inbox("b"))
        self.assertEqual(acknowledged,
                         self.store.send("a", "b", "hello", "one"))

    def test_expiry_stale_tokens_and_exact_resource(self):
        old = self.store.claim("src/a.py", "a", 10)
        with self.assertRaises(Conflict):
            self.store.claim("src/a.py", "a", 10)
        self.store.claim("src/A.py", "b", 10)
        self.store.claim("src", "c", 10)
        self.assertEqual(3, len(self.store.leases()))
        self.time = 110
        current = self.store.claim("src/a.py", "a", 20)
        self.assertNotEqual(old["generation"], current["generation"])
        with self.assertRaises(Conflict):
            self.store.release("src/a.py", "a", old["generation"])
        with self.assertRaises(Conflict):
            self.store.renew("src/a.py", "a", old["generation"], 20)
        with self.assertRaises(Conflict):
            self.store.release("src/a.py", "b", current["generation"])
        renewed = self.store.renew("src/a.py", "a", current["generation"], 30)
        self.assertEqual(140, renewed["expires_at"])
        self.store.release("src/a.py", "a", current["generation"])
        self.assertEqual([], self.store.leases())

    def test_expired_lease_cannot_renew_or_release(self):
        old = self.store.claim("r", "a", 1)
        self.time += 1
        for operation in (self.store.renew, self.store.release):
            args = ["r", "a", old["generation"]]
            if operation == self.store.renew:
                args.append(10)
            with self.assertRaises(Conflict):
                operation(*args)

    def test_invalid_inputs_and_ttl(self):
        for ttl in (float("nan"), float("inf"), -1, 0, 86401, True, "3"):
            with self.assertRaises(ValueError):
                self.store.claim("r", "a", ttl)
        for invalid in ("", "  ", "bad\x00value", None):
            with self.assertRaises(ValueError):
                self.store.claim(invalid, "a", 1)
            with self.assertRaises(ValueError):
                self.store.send("a", "b", "body", invalid)
            with self.assertRaises(ValueError):
                self.store.inbox(invalid)
        self.assertEqual([], self.store.leases())

    def test_two_process_race(self):
        ctx = multiprocessing.get_context("spawn")
        ready, result, start = ctx.Queue(), ctx.Queue(), ctx.Event()
        processes = [ctx.Process(target=race_claim,
                                 args=(self.db, ready, start, result))
                     for _ in range(2)]
        try:
            for process in processes:
                process.start()
            for _ in processes:
                self.assertTrue(ready.get(timeout=15))
            start.set()
            outcomes = [result.get(timeout=15) for _ in processes]
            self.assertEqual(["claimed", "conflict"], sorted(outcomes))
            for process in processes:
                process.join(15)
                self.assertEqual(0, process.exitcode)
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            ready.close()
            result.close()


if __name__ == "__main__":
    unittest.main()
