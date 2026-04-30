"""
Inventory Service - Dummy microservice for testing auto-healer agent.
Checks stock availability.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Configure structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Inventory Service", version="1.0.0")


class StockCheckRequest(BaseModel):
    item_id: str
    quantity: int


class StockCheckResponse(BaseModel):
    item_id: str
    in_stock: bool
    available_quantity: int
    timestamp: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "inventory", "timestamp": datetime.utcnow().isoformat()}


@app.post("/check_stock")
async def check_stock(
    request: StockCheckRequest,
    chaos_type: Optional[str] = Query(default=None)
):
    """
    Check if item is in stock.

    Chaos injection types:
    - 500_zerodivision: Triggers ZeroDivisionError
    - 502_bad_gateway: Simulates database connection failure
    """
    logger.info(json.dumps({
        "event": "stock_check_received",
        "item_id": request.item_id,
        "quantity": request.quantity,
        "chaos_type": chaos_type
    }))

    # Chaos injection
    if chaos_type == "500_zerodivision":
        logger.error(json.dumps({
            "event": "chaos_triggered",
            "type": "500_zerodivision",
            "item_id": request.item_id
        }))
        result = 1 / 0

    elif chaos_type == "502_bad_gateway":
        logger.error(json.dumps({
            "event": "chaos_triggered",
            "type": "502_bad_gateway",
            "item_id": request.item_id
        }))
        raise HTTPException(status_code=502, detail="Database connection failed")

    # Simulate inventory check (always in stock for testing)
    available_quantity = 100  # Mock available quantity

    in_stock = available_quantity >= request.quantity

    logger.info(json.dumps({
        "event": "stock_check_completed",
        "item_id": request.item_id,
        "requested_quantity": request.quantity,
        "available_quantity": available_quantity,
        "in_stock": in_stock
    }))

    return StockCheckResponse(
        item_id=request.item_id,
        in_stock=in_stock,
        available_quantity=available_quantity,
        timestamp=datetime.utcnow().isoformat()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
