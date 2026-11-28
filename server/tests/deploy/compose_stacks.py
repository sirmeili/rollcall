"""A Compose stack the deploy tests start: its file, its project name and the settings
interpolated into it, and waiting for its server."""

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

DEPLOY = Path(__file__).parents[3] / "deploy"
CSRF = {"X-Requested-With": "filament-tracker"}


@dataclass
class Stack:
    file: Path
    project: str
    port: int
    env: dict[str, str] = field(default_factory=dict)

    @property
    def api(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/v1"

    def compose(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(  # noqa: S603 - fixed arguments
            ["docker", "compose", "-f", str(self.file), "-p", self.project, *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
            env={**os.environ, **self.env},
        )
        if check and result.returncode != 0:
            raise AssertionError(f"docker compose {args[0]} failed:\n{result.stderr[-2000:]}")
        return result.stdout + result.stderr

    def up(self, *services: str) -> None:
        self.compose("up", "--detach", "--wait", "--wait-timeout", "120", *services)
        self.wait_for_health()

    def logs(self, service: str) -> str:
        return self.compose("logs", "--no-color", service)

    def run_in(self, service: str, *command: str) -> str:
        return self.compose("exec", "-T", service, *command)

    def wait_for_health(self) -> None:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.api}/health", timeout=5).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(1)
        raise AssertionError(f"{self.project} did not answer its health check")


def signed_in(stack: Stack, username: str, password: str) -> httpx.Client:
    """A browser signed in to the stack's server."""
    browser = httpx.Client(base_url=stack.api, timeout=10, headers=CSRF)
    response = browser.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return browser
