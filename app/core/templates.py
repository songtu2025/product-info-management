from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.shared.flash import pop_flash


BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["pop_flash"] = pop_flash
