"""Shim — uvicorn main:app still works. Real factory lives in app.factory."""

from app.factory import create_app

app = create_app()
