from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def get_health(request: Request) -> dict[str, Any]:
    """Liveness, the release this server is (`1.4.0`, `1.4.0-rc.1`, `dev (<short commit>)`
    or `dev`), and the state of the Home Assistant links: MQTT (off, connecting, connected or
    disconnected) and events (off, ready or failing)."""
    link = getattr(request.app.state, "home_assistant", None)
    publisher = link.publisher if link is not None else None
    sender = link.sender if link is not None else None
    return {
        "status": "ok",
        "version": request.app.state.version,
        "home_assistant": {
            "mqtt": publisher.status.value if publisher is not None else "off",
            "events": sender.status.value if sender is not None else "off",
        },
    }
