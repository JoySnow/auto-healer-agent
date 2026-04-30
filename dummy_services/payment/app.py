"""
Payment Service - Dummy microservice for testing auto-healer agent.
Processes payment transactions.
"""
import json
import logging
import uuid
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

app = FastAPI(title="Payment Service", version="1.0.0")


class PaymentRequest(BaseModel):
    order_id: str
    amount: float


class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    order_id: str
    amount: float
    timestamp: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "payment", "timestamp": datetime.utcnow().isoformat()}


@app.post("/process_payment")
async def process_payment(
    request: PaymentRequest,
    chaos_type: Optional[str] = Query(default=None)
):
    """
    Process a payment transaction.

    Chaos injection types:
    - 500_zerodivision: Triggers ZeroDivisionError
    - 502_bad_gateway: Simulates payment gateway failure
    """
    payment_id = str(uuid.uuid4())

    logger.info(json.dumps({
        "event": "payment_received",
        "payment_id": payment_id,
        "order_id": request.order_id,
        "amount": request.amount,
        "chaos_type": chaos_type
    }))

    # Chaos injection
    if chaos_type == "500_zerodivision":
        logger.error(json.dumps({
            "event": "chaos_triggered",
            "type": "500_zerodivision",
            "payment_id": payment_id
        }))
        result = 1 / 0

    elif chaos_type == "502_bad_gateway":
        logger.error(json.dumps({
            "event": "chaos_triggered",
            "type": "502_bad_gateway",
            "payment_id": payment_id
        }))
        raise HTTPException(status_code=502, detail="Payment gateway unavailable")

    # Validate amount
    if request.amount <= 0:
        logger.warning(json.dumps({
            "event": "invalid_payment_amount",
            "payment_id": payment_id,
            "amount": request.amount
        }))
        raise HTTPException(status_code=400, detail="Invalid payment amount")

    # Normal flow - process payment
    logger.info(json.dumps({
        "event": "payment_processed",
        "payment_id": payment_id,
        "order_id": request.order_id,
        "amount": request.amount,
        "status": "processed"
    }))

    return PaymentResponse(
        payment_id=payment_id,
        status="processed",
        order_id=request.order_id,
        amount=request.amount,
        timestamp=datetime.utcnow().isoformat()
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
