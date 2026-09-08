import uuid

from sqlmodel import Session

from app.models import UserRole
from app.services import telegram
from tests.utils.user import create_random_user


def test_link_code_roundtrip() -> None:
    uid = uuid.uuid4()
    code = telegram.issue_link_code(uid)
    assert len(code) == 6
    assert telegram.consume_link_code(code) == uid
    # single use
    assert telegram.consume_link_code(code) is None


def test_consume_unknown_code_returns_none() -> None:
    assert telegram.consume_link_code("ZZZZZZ") is None


def test_handle_update_link_sets_chat_id(db: Session) -> None:
    user = create_random_user(db, role=UserRole.driver)
    code = telegram.issue_link_code(user.id)
    reply = telegram.handle_update(
        db,
        {"message": {"chat": {"id": 987654}, "text": f"/link {code}"}},
    )
    assert reply and "lié" in reply
    db.refresh(user)
    assert user.telegram_chat_id == "987654"


def test_handle_update_bad_code(db: Session) -> None:
    reply = telegram.handle_update(
        db, {"message": {"chat": {"id": 1}, "text": "/link NOPE12"}}
    )
    assert reply and "invalide" in reply.lower()


def test_handle_update_start_returns_help(db: Session) -> None:
    reply = telegram.handle_update(
        db, {"message": {"chat": {"id": 1}, "text": "/start"}}
    )
    assert reply and "/link" in reply


def test_handle_update_ignores_non_message(db: Session) -> None:
    assert telegram.handle_update(db, {"poll": {}}) is None


def test_send_to_role_only_targets_linked_active_users(
    db: Session, no_telegram_http: list[tuple[str, str]]
) -> None:
    # unique chat ids + message so this is independent of other tests' rows
    linked = create_random_user(db, role=UserRole.dispatcher)
    linked.telegram_chat_id = "chat-linked-disp"
    db.add(linked)
    create_random_user(db, role=UserRole.dispatcher)  # dispatcher, not linked
    wrong_role = create_random_user(db, role=UserRole.driver)
    wrong_role.telegram_chat_id = "chat-driver"
    db.add(wrong_role)
    db.commit()

    telegram.send_to_role(db, UserRole.dispatcher, "ping-abc")

    targets = {chat for chat, text in no_telegram_http if text == "ping-abc"}
    assert "chat-linked-disp" in targets
    assert "chat-driver" not in targets
