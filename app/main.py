import os
import socket

from fastapi import FastAPI

app = FastAPI()
APP_Version = os.environ.get("APP_VERSION", "dev") # falls back to "dev" if unset

@app.get("/")
def root():
    # hostname tells us which copy of the app answered
    return {"pod": socket.gethostname(), "version": APP_Version}