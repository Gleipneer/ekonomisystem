from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Household Economics Frontend")
app.mount("/assets", StaticFiles(directory=ROOT), name="assets")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")

