from fastapi import APIRouter

from app.api.routes import (
    auth,
    dispatch,
    driver,
    orders,
    pricing,
    reviews,
    users,
    utils,
    vehicles,
    ws,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(orders.router)
api_router.include_router(dispatch.router)
api_router.include_router(driver.router)
api_router.include_router(vehicles.router)
api_router.include_router(pricing.router)
api_router.include_router(reviews.router)
api_router.include_router(ws.router)
api_router.include_router(utils.router)
