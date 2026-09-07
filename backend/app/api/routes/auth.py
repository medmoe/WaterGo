from datetime import timedelta

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.core import security
from app.core.config import settings
from app.models import Message, OTPRequest, OTPVerify, Token
from app.services import otp

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request")
def request_otp(body: OTPRequest) -> Message:
    """
    Send a one-time code to the given phone number via SMS/WhatsApp.

    Always returns the same response so it can't be used to enumerate accounts.
    """
    otp.request_otp(body.phone_number)
    return Message(message="If the number is valid, a code has been sent.")


@router.post("/otp/verify")
def verify_otp(session: SessionDep, body: OTPVerify) -> Token:
    """
    Verify a code and return a JWT. Creates the user (role=customer) on first
    successful login; pre-provisioned dispatcher/driver/admin accounts keep
    their role.
    """
    if not otp.verify_otp(body.phone_number, body.code):
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    user, _ = crud.get_or_create_user_by_phone(
        session=session, phone_number=body.phone_number
    )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )
