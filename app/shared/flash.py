from fastapi import Request


FLASH_SESSION_KEY = "flash_message"


def set_flash(request: Request, message: str) -> None:
    request.session[FLASH_SESSION_KEY] = message


def pop_flash(request: Request) -> str | None:
    return request.session.pop(FLASH_SESSION_KEY, None)
