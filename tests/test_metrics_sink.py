import unittest
import tempfile
import json
from pathlib import Path
from core.events import HarnessEvent
from core.metrics_sink import JSONLMissionMetricsSink


class TestMetricsSink(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temp_dir.name) / "metrics.jsonl"
        self.sink = JSONLMissionMetricsSink(log_path=self.log_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_metrics_lifecycle_recording(self):
        # 1. Start task
        self.sink.handle_event(HarnessEvent("agent.started", {"task_id": "task-test-1", "objective": "Tester les métriques"}))
        self.assertIn("task-test-1", self.sink.active_missions)

        # 2. Tool completed
        self.sink.handle_event(HarnessEvent("tool.completed", {"task_id": "task-test-1", "tool": "read_file"}))
        self.sink.handle_event(HarnessEvent("tool.completed", {"task_id": "task-test-1", "tool": "write_file"}))
        self.assertEqual(self.sink.active_missions["task-test-1"].tool_calls_count, 2)

        # 3. Delegation completed
        self.sink.handle_event(HarnessEvent("delegation.completed", {"task_id": "task-test-1", "agent": "tester"}))
        self.assertEqual(self.sink.active_missions["task-test-1"].delegation_depth, 1)

        # 4. Verification completed
        self.sink.handle_event(HarnessEvent("verification.completed", {"task_id": "task-test-1", "status": "passed"}))
        self.assertTrue(self.sink.active_missions["task-test-1"].verification_passed)

        # 5. Delivery completed -> persists to JSONL
        self.sink.handle_event(HarnessEvent("delivery.completed", {"task_id": "task-test-1"}))
        self.assertNotIn("task-test-1", self.sink.active_missions)

        self.assertTrue(self.log_file.exists())
        lines = self.log_file.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)

        data = json.loads(lines[0])
        self.assertEqual(data["task_id"], "task-test-1")
        self.assertEqual(data["tool_calls_count"], 2)
        self.assertEqual(data["delegation_depth"], 1)
        self.assertTrue(data["verification_passed"])
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(data["duration_seconds"], 0.0)


if __name__ == "__main__":
    unittest.main()
