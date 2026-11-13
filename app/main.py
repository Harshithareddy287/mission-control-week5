from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.errors import validation_error_handler
from app.llm.base import LLMClient, get_client
from app.models import ApprovalIn, BriefingOut, ReportIn, ReportOut
from app.pipeline import process_report

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _error(status: int, field: str, message: str) -> JSONResponse:
    """Same {"errors": [...]} shape as validation errors, for the front end."""
    return JSONResponse(status_code=status, content={"errors": [{"field": field, "message": message}]})


def get_llm_client() -> LLMClient:
    """FastAPI dependency; tests override it with a scripted FakeLLMClient."""
    return get_client()


def create_app() -> FastAPI:
    app = FastAPI(title="Mission Control")

    app.state.db_path = db.db_path_from_env()
    db.init_db(app.state.db_path)

    app.add_exception_handler(RequestValidationError, validation_error_handler)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/reports", response_model=ReportOut, status_code=201)
    async def create_report(
        report: ReportIn, request: Request, client: LLMClient = Depends(get_llm_client)
    ):
        path = request.app.state.db_path
        report_id = db.insert_report(path, report.model_dump())
        results = await process_report(client, report)
        db.save_results(path, report_id, results)
        return db.get_report(path, report_id)

    @app.get("/api/reports", response_model=list[ReportOut])
    def get_reports(request: Request):
        return db.list_reports(request.app.state.db_path)

    @app.post("/api/briefings/{briefing_id}/approve", response_model=BriefingOut)
    def approve_briefing(briefing_id: int, body: ApprovalIn, request: Request):
        """Human approval: the only way a briefing becomes 'approved'."""
        try:
            return db.approve_briefing(request.app.state.db_path, briefing_id, body.approver_name)
        except db.BriefingNotFound:
            return _error(404, "briefing", f"Briefing {briefing_id} was not found.")
        except db.BriefingNotPending:
            return _error(409, "status", "This briefing is not pending; it was already approved.")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
