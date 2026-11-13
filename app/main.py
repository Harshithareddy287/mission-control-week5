from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Mission Control")

@app.get("/api/health")
def health():
    return {"status": "ok"}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
