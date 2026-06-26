from pathlib import Path
from typing import Any, Callable

from app import config

try:
    from garminconnect import Garmin  # type: ignore
except ImportError:  # pragma: no cover - exercised in environments without the optional package.
    Garmin = None  # type: ignore[assignment]


class GarminClientUnavailableError(RuntimeError):
    pass


class GarminClientAdapter:
    def __init__(
        self,
        *,
        token_dir: Path | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.token_dir = token_dir or config.GARMIN_TOKEN_DIR
        self.client_factory = client_factory or Garmin

    def has_tokens(self) -> bool:
        token_file = self.token_dir / "garmin_tokens.json"
        if token_file.is_file():
            return True

        return self.token_dir.is_dir() and any(
            child.is_file()
            for child in self.token_dir.rglob("*")
        )

    def _new_client(self, *args: Any, **kwargs: Any) -> Any:
        if self.client_factory is None:
            raise GarminClientUnavailableError(
                "garminconnect is not installed in this environment."
            )

        return self.client_factory(*args, **kwargs)

    def _persist_tokens(self, client: Any) -> None:
        self.token_dir.mkdir(parents=True, exist_ok=True)

        internal_client = getattr(client, "client", None)
        if internal_client is not None and hasattr(internal_client, "dump"):
            internal_client.dump(str(self.token_dir))
        else:
            garth = getattr(client, "garth", None)
            if garth is not None and hasattr(garth, "dump"):
                garth.dump(str(self.token_dir))

        if not self.has_tokens():
            raise GarminClientUnavailableError(
                f"Garmin login succeeded but tokenstore was not written to {self.token_dir}"
            )

    def _login_with_tokenstore(self, client: Any) -> Any:
        self.token_dir.mkdir(parents=True, exist_ok=True)

        try:
            return client.login(str(self.token_dir))
        except TypeError:
            return client.login()

    def connect_from_tokens(self) -> Any:
        client = self._new_client()
        self._login_with_tokenstore(client)
        return client

    def login(self, username: str, password: str) -> tuple[bool, Any, Any]:
        try:
            client = self._new_client(username, password, return_on_mfa=True)
        except TypeError:
            client = self._new_client(username, password)

        result = self._login_with_tokenstore(client)
        if isinstance(result, tuple) and result and str(result[0]).lower() in {
            "needs_mfa",
            "mfa_required",
        }:
            return True, client, result[1] if len(result) > 1 else None

        self._persist_tokens(client)
        return False, client, None

    def resume_mfa(self, client: Any, state: Any, code: str) -> None:
        if hasattr(client, "resume_login"):
            client.resume_login(state, code)
        elif hasattr(client, "login"):
            try:
                client.login(code)
            except TypeError:
                client.login()
        else:
            raise GarminClientUnavailableError("Garmin MFA session cannot be resumed.")

        self._persist_tokens(client)

    def disconnect(self) -> None:
        if not self.token_dir.exists():
            return

        for child in self.token_dir.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                self._delete_directory(child)

    def _delete_directory(self, path: Path) -> None:
        for child in path.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                self._delete_directory(child)
        path.rmdir()

    def get_daily_summary(self, client: Any, metric_date: str) -> Any:
        return self._call_first(client, ("get_user_summary", "get_stats"), metric_date)

    def get_hrv_data(self, client: Any, metric_date: str) -> Any:
        return self._call_first(client, ("get_hrv_data", "get_hrv"), metric_date)

    def get_stress_data(self, client: Any, metric_date: str) -> Any:
        return self._call_first(client, ("get_stress_data", "get_stress"), metric_date)

    def get_body_battery_data(self, client: Any, metric_date: str) -> Any:
        return self._call_first(
            client,
            ("get_body_battery", "get_body_battery_data"),
            metric_date,
        )

    def _call_first(
        self,
        client: Any,
        method_names: tuple[str, ...],
        metric_date: str,
    ) -> Any:
        for method_name in method_names:
            method = getattr(client, method_name, None)
            if method is not None:
                return method(metric_date)

        raise GarminClientUnavailableError(
            f"Garmin client has none of: {', '.join(method_names)}"
        )