import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import config
import app.main as main


class ReactStaticServingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_frontend_dist_dir = config.FRONTEND_DIST_DIR
        self.original_app_url_prefix = config.APP_URL_PREFIX
        dist_dir = Path(self.temp_dir.name)
        (dist_dir / "assets").mkdir()
        (dist_dir / "index.html").write_text("<div id=\"root\"></div>", encoding="utf-8")
        (dist_dir / "assets" / "app.js").write_text("console.log('ok');", encoding="utf-8")
        config.FRONTEND_DIST_DIR = dist_dir
        config.APP_URL_PREFIX = ""

    def tearDown(self) -> None:
        config.FRONTEND_DIST_DIR = self.original_frontend_dist_dir
        config.APP_URL_PREFIX = self.original_app_url_prefix
        self.temp_dir.cleanup()


    def test_strip_app_url_prefix_default_preserves_path(self) -> None:
        config.APP_URL_PREFIX = ""

        self.assertEqual(main.strip_app_url_prefix("history"), "history")

    def test_strip_app_url_prefix_removes_configured_prefix(self) -> None:
        config.APP_URL_PREFIX = "custom/prefix"

        self.assertEqual(main.strip_app_url_prefix("custom/prefix"), "")
        self.assertEqual(
            main.strip_app_url_prefix("custom/prefix/history"),
            "history",
        )
        self.assertEqual(
            main.strip_app_url_prefix("other/history"),
            "other/history",
        )

    def test_home_assistant_ingress_prefix_is_removed(self) -> None:
        self.assertEqual(
            main.strip_runtime_url_prefix("api/hassio_ingress/faketoken/history"),
            "history",
        )
        self.assertEqual(
            main.strip_runtime_url_prefix("/api/hassio_ingress/faketoken/api/v1/stats"),
            "/api/v1/stats",
        )

    def test_react_routes_return_index_file(self) -> None:
        response = main.serve_react_app("history")

        self.assertEqual(Path(response.path).name, "index.html")


    def test_prefixed_react_routes_return_index_file(self) -> None:
        response = main.serve_react_app("api/hassio_ingress/faketoken/history")

        self.assertEqual(Path(response.path).name, "index.html")

    def test_prefixed_react_assets_return_asset_file(self) -> None:
        response = main.serve_react_app("api/hassio_ingress/faketoken/assets/app.js")

        self.assertEqual(Path(response.path).name, "app.js")

    def test_react_assets_return_asset_file(self) -> None:
        response = main.serve_react_app("assets/app.js")

        self.assertEqual(Path(response.path).name, "app.js")

    def test_api_paths_are_not_served_as_react(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            main.serve_react_app("api/v1/missing")

        self.assertEqual(exc.exception.status_code, 404)

    def test_missing_assets_are_not_served_as_react(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            main.serve_react_app("assets/missing.js")

        self.assertEqual(exc.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
