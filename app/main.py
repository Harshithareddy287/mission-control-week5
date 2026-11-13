from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app import db
from app.errors import validation_error_handler
from app.models import ReportIn, ReportOut

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Mission Control")

    app.state.db_path = db.db_path_from_env()
    db.init_db(app.state.db_path)

    app.add_exception_handler(RequestValidationError, validation_error_handler)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/reports", response_model=ReportOut, status_code=201)
    def create_report(report: ReportIn, request: Request):
        return db.insert_report(request.app.state.db_path, report.model_dump())

    @app.get("/api/reports", response_model=list[ReportOut])
    def get_reports(request: Request):
        return db.list_reports(request.app.state.db_path)

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
