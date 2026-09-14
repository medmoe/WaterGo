import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import DispatcherUser, SessionDep
from app.models import (
    PendingMapPoint,
    Route,
    RouteCreate,
    RoutePublic,
    RoutesPublic,
    RouteUpdate,
    UserPublic,
)
from app.services import routes as routes_service

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.get("/drivers", response_model=list[UserPublic])
def list_drivers(session: SessionDep, _user: DispatcherUser) -> Any:
    """Active drivers, for the route-builder's driver picker."""
    return routes_service.list_drivers(session)


@router.get("/pending-map", response_model=list[PendingMapPoint])
def pending_map(session: SessionDep, _user: DispatcherUser) -> Any:
    """Geo points for every confirmed order not yet on a route."""
    return routes_service.pending_map(session)


@router.get("/routes", response_model=RoutesPublic)
def list_routes(
    session: SessionDep, _user: DispatcherUser, planned_date: date | None = None
) -> Any:
    data, count = routes_service.list_routes(session, planned_date=planned_date)
    return RoutesPublic(data=data, count=count)


@router.post("/routes", response_model=RoutePublic)
def create_route(
    *, session: SessionDep, _user: DispatcherUser, body: RouteCreate
) -> Any:
    """Group confirmed orders onto one truck/driver route."""
    return routes_service.create_route(
        session,
        vehicle_id=body.vehicle_id,
        driver_id=body.driver_id,
        planned_date=body.planned_date,
        order_ids=body.order_ids,
    )


@router.patch("/routes/{route_id}", response_model=RoutePublic)
def update_route(
    *,
    session: SessionDep,
    _user: DispatcherUser,
    route_id: uuid.UUID,
    body: RouteUpdate,
) -> Any:
    """Reorder stops and/or advance route status (planned/in_progress/completed)."""
    route = session.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return routes_service.update_route(
        session, route, status=body.status, order_ids=body.order_ids
    )
