"""QuantumFintek API entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="QuantumFintek API",
    description="Enterprise quantitative finance platform",
    version="0.2.0-alpha",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "quantum-fintek-api", "version": "0.2.0-alpha"}


@app.get("/")
def root():
    return {
        "name": "QuantumFintek",
        "domains": [
            "trading",
            "quantitative",
            "ai-intelligence",
            "enterprise",
            "security",
        ],
    }
