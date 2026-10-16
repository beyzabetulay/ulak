from fastapi import FastAPI

app = FastAPI(title="CAN Bus IDS Backend")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "can-bus-ids-backend", "docs": "/docs"}
