import uuid
from typing import Any

from fastapi import APIRouter, Response

from app.api.deps import DriverUser, SessionDep
from app.models import RoutePublic, RouteStopPublic
from app.services import routes as routes_service

router = APIRouter(prefix="/driver", tags=["driver"])


@router.get("/routes/today", response_model=RoutePublic | None)
def todays_route(session: SessionDep, driver: DriverUser, response: Response) -> Any:
    """The logged-in driver's route for today, stops in sequence order."""
    route = routes_service.todays_route(session, driver)
    if route is None:
        response.status_code = 204
    return route


@router.patch("/stops/{stop_id}/delivered", response_model=RouteStopPublic)
def mark_delivered(session: SessionDep, driver: DriverUser, stop_id: uuid.UUID) -> Any:
    return routes_service.mark_delivered(session, stop_id, driver)


@router.patch("/stops/{stop_id}/payment-collected", response_model=RouteStopPublic)
def mark_payment_collected(
    session: SessionDep, driver: DriverUser, stop_id: uuid.UUID
) -> Any:
    return routes_service.mark_payment_collected(session, stop_id, driver)
