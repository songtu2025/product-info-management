from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.shared.flash import pop_flash


BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["pop_flash"] = pop_flash


def format_percent(value):
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


templates.env.filters["percent"] = format_percent
