from fastapi import FastAPI

app = FastAPI(
    title="FleetLine",
    description="Shipment management platform.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"service": "FleetLine", "docs": "/docs"}
