import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import DispatcherUser, SessionDep
from app.models import (
    MaintenanceLog,
    MaintenanceLogCreate,
    MaintenanceLogPublic,
    Vehicle,
    VehicleCreate,
    VehiclePublic,
    VehiclesPublic,
    VehicleUpdate,
)

router = APIRouter(prefix="/vehicles", tags=["fleet"])


@router.get("", response_model=VehiclesPublic)
def list_vehicles(
    session: SessionDep, _user: DispatcherUser, skip: int = 0, limit: int = 100
) -> Any:
    count = session.exec(select(func.count()).select_from(Vehicle)).one()
    statement = (
        select(Vehicle)
        .order_by(col(Vehicle.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return VehiclesPublic(data=list(session.exec(statement).all()), count=count)


@router.post("", response_model=VehiclePublic)
def create_vehicle(
    *, session: SessionDep, _user: DispatcherUser, body: VehicleCreate
) -> Any:
    existing = session.exec(
        select(Vehicle).where(Vehicle.plate_number == body.plate_number)
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="A vehicle with this plate number already exists"
        )
    vehicle = Vehicle.model_validate(body)
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehiclePublic)
def update_vehicle(
    *,
    session: SessionDep,
    _user: DispatcherUser,
    vehicle_id: uuid.UUID,
    body: VehicleUpdate,
) -> Any:
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    vehicle.sqlmodel_update(body.model_dump(exclude_unset=True))
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return vehicle


@router.post("/{vehicle_id}/maintenance-logs", response_model=MaintenanceLogPublic)
def add_maintenance_log(
    *,
    session: SessionDep,
    _user: DispatcherUser,
    vehicle_id: uuid.UUID,
    body: MaintenanceLogCreate,
) -> Any:
    vehicle = session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    log = MaintenanceLog.model_validate(body, update={"vehicle_id": vehicle_id})
    session.add(log)
    # Keep the odometer moving forward if this event reports a higher reading.
    if body.odometer_km_at_event > vehicle.current_odometer_km:
        vehicle.current_odometer_km = body.odometer_km_at_event
        session.add(vehicle)
    session.commit()
    session.refresh(log)
    return log
