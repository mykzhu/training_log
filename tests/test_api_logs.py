import asyncio
import logging
import tempfile
import unittest
from pathlib import Path

from fastapi import Response
from starlette.requests import Request

from app import config
from app.db import init_db
import app.main as main
from app.routes.api_logs import get_logs_endpoint
from app.services.log_service import clear_log_buffer_for_tests


class LogsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = Path(self.temp_dir.name) / "training.db"
        init_db()
        clear_log_buffer_for_tests()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_logs_route_is_registered(self) -> None:
        routes = {
            (route.path, tuple(sorted(route.methods)))
            for route in main.app.routes
            if hasattr(route, "methods")
        }

        self.assertIn(("/api/v1/logs", ("GET",)), routes)

    def test_log_endpoint_returns_recent_entries(self) -> None:
        logger = logging.getLogger("training_log.test")
        logger.info("test visible message")

        response = get_logs_endpoint(limit=10)

        messages = [entry["message"] for entry in response["entries"]]
        self.assertTrue(any("test visible message" in message for message in messages))
        self.assertEqual(response["count"], 1)

    def test_log_endpoint_filters_by_level_logger_and_query(self) -> None:
        logger = logging.getLogger("training_log.test.filter")
        logger.info("alpha visible message")
        logger.warning("beta hidden message")
        logging.getLogger("other_logger").warning("alpha other message")

        response = get_logs_endpoint(
            limit=10,
            level="WARNING",
            logger="training_log.test",
            query="beta",
        )

        self.assertEqual(response["count"], 1)
        self.assertIn("beta hidden message", response["entries"][0]["message"])
        self.assertEqual(response["entries"][0]["level"], "WARNING")

    def test_log_endpoint_limits_results(self) -> None:
        logger = logging.getLogger("training_log.test.limit")
        logger.info("first")
        logger.info("second")
        logger.info("third")

        response = get_logs_endpoint(limit=2)

        self.assertEqual(response["count"], 2)
        self.assertEqual(response["total_available"], 3)
        self.assertEqual(response["filtered_available"], 3)
        self.assertTrue(response["truncated"])
        self.assertIn("third", response["entries"][0]["message"])

    def test_log_endpoint_reports_filtered_count_without_false_truncation(self) -> None:
        logger = logging.getLogger("training_log.test.filter_count")
        logger.info("alpha")
        logger.warning("beta")
        logger.warning("gamma")
        logger.error("delta")

        response = get_logs_endpoint(limit=10, level="WARNING")

        self.assertEqual(response["count"], 2)
        self.assertEqual(response["filtered_available"], 2)
        self.assertEqual(response["total_available"], 4)
        self.assertFalse(response["truncated"])

    def test_log_endpoint_reports_filtered_truncation(self) -> None:
        logger = logging.getLogger("training_log.test.filter_truncate")
        logger.info("alpha")
        logger.warning("beta")
        logger.warning("gamma")
        logger.error("delta")

        response = get_logs_endpoint(limit=1, level="WARNING")

        self.assertEqual(response["count"], 1)
        self.assertEqual(response["filtered_available"], 2)
        self.assertEqual(response["total_available"], 4)
        self.assertTrue(response["truncated"])

    def test_logs_endpoint_does_not_log_itself(self) -> None:
        async def call_next(_: Request) -> Response:
            return Response(content="{}", media_type="application/json")

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/logs",
                "headers": [],
                "client": ("testclient", 123),
                "scheme": "http",
                "server": ("testserver", 80),
                "query_string": b"",
            }
        )

        response = asyncio.run(main.log_requests(request, call_next))

        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-ID", response.headers)
        logs = get_logs_endpoint(limit=50)
        self.assertFalse(
            any("/api/v1/logs" in entry["message"] for entry in logs["entries"])
        )

    def test_log_endpoint_redacts_sensitive_values(self) -> None:
        logger = logging.getLogger("training_log.test.redact")
        logger.error(
            "failed password=secret token=abc authorization: Bearer xyz cookie: sid=123"
        )

        response = get_logs_endpoint(limit=10)
        serialized = "\n".join(entry["message"] for entry in response["entries"])

        self.assertNotIn("secret", serialized)
        self.assertNotIn("abc", serialized)
        self.assertNotIn("Bearer xyz", serialized)
        self.assertNotIn("xyz", serialized)
        self.assertNotIn("sid=123", serialized)
        self.assertIn("password=[REDACTED]", serialized)
        self.assertIn("token=[REDACTED]", serialized)


if __name__ == "__main__":
    unittest.main()
