from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from slopstop.admin.deps import require_auth
from slopstop.admin.routes.auth_routes import router as auth_router
from slopstop.blocklist import ACTIVE_BLOCKLIST_PATH
from slopstop.dns_control import DEFAULT_TEMPLATE_DIR, UNBOUND_CONF_PATH

STATIC_DIR = Path(__file__).parent.parent.parent.parent / "static"
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"


def create_app(
    db_path: Path,
    blocklist_path: Path = ACTIVE_BLOCKLIST_PATH,
    unbound_conf_path: Path = UNBOUND_CONF_PATH,
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)
    app.state.db_path = db_path
    app.state.blocklist_path = blocklist_path
    app.state.unbound_conf_path = unbound_conf_path
    app.state.template_dir = template_dir

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(auth_router)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    def dashboard_stub(request: Request, _token: str = Depends(require_auth)) -> HTMLResponse:
        return templates.TemplateResponse(request, "base.html", {})

    return app
