"""Tests for the minimal agent. Run from the companion folder:

    python3 -m unittest discover -s tests -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "minimal_agent"))

from agent import ActionError, Agent, Budget, BudgetExceeded, Cache, History, Tools  # noqa: E402


class ScriptedModel:
    """Returns prepared replies in order and records how many calls were made."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        return self.replies.pop(0)


def action(name, **args):
    return json.dumps({"action": name, "args": args})


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tools = Tools(Path(self.dir.name))

    def tearDown(self):
        self.dir.cleanup()

    def test_path_outside_project_is_refused(self):
        with self.assertRaises(ActionError):
            self.tools.read_file("../outside.txt")

    def test_ambiguous_search_is_refused(self):
        self.tools.write_file("a.txt", "x = 1\nx = 1\n")
        with self.assertRaises(ActionError):
            self.tools.search_replace("a.txt", "x = 1", "x = 2")
        self.assertEqual(self.tools.read_file("a.txt"), "x = 1\nx = 1\n")

    def test_unique_search_is_applied(self):
        self.tools.write_file("a.txt", "one\ntwo\n")
        self.tools.search_replace("a.txt", "two", "three")
        self.assertEqual(self.tools.read_file("a.txt"), "one\nthree\n")

    def test_replace_all_allows_several_matches(self):
        self.tools.write_file("a.txt", "x\nx\n")
        self.tools.search_replace("a.txt", "x", "y", replace_all=True)
        self.assertEqual(self.tools.read_file("a.txt"), "y\ny\n")

    def test_command_timeout_is_reported(self):
        with self.assertRaises(ActionError):
            self.tools.run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.2)


class HistoryTest(unittest.TestCase):
    def test_old_observations_collapse_and_recent_stay(self):
        history = History()
        for i in range(15):
            history.add(f"observation {i}")
        rendered = history.render()
        self.assertIn("[collapsed observation of", rendered)
        self.assertIn("observation 14", rendered)
        self.assertNotIn("observation 0\n", rendered)

    def test_long_result_is_cut(self):
        history = History()
        history.add("a" * 5_000)
        self.assertLess(len(history.items[0]), 1_500)


class CacheTest(unittest.TestCase):
    def test_timestamps_do_not_change_the_key(self):
        first = Cache.key("run at 2026-01-01 10:00:00")
        second = Cache.key("run at 2026-06-30 23:59:59")
        self.assertEqual(first, second)

    def test_second_identical_request_is_served_from_cache(self):
        model = ScriptedModel([action("finish", summary="done")])
        cache = Cache()
        cache.get_or_call(model, "same prompt")
        cache.get_or_call(model, "same prompt")
        self.assertEqual(model.calls, 1)
        self.assertEqual(cache.misses, 1)


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_loop_edits_a_file_and_finishes(self):
        model = ScriptedModel([
            action("write_file", path="hello.txt", content="hi\n"),
            action("finish", summary="created hello.txt"),
        ])
        agent = Agent(model, Tools(self.root), Budget(limit_tokens=100_000))
        self.assertEqual(agent.run("create a greeting"), "created hello.txt")
        self.assertEqual((self.root / "hello.txt").read_text(), "hi\n")

    def test_invalid_reply_becomes_an_observation_not_a_crash(self):
        model = ScriptedModel(["not json", action("finish", summary="ok")])
        agent = Agent(model, Tools(self.root), Budget(limit_tokens=100_000))
        self.assertEqual(agent.run("task"), "ok")
        self.assertIn("not a JSON action", agent.history.items[0])

    def test_budget_stops_the_run(self):
        long_reply = action("read_file", path="missing.txt")
        model = ScriptedModel([long_reply] * 50)
        agent = Agent(model, Tools(self.root), Budget(limit_tokens=200))
        with self.assertRaises(BudgetExceeded):
            agent.run("task", max_steps=50)


if __name__ == "__main__":
    unittest.main()
