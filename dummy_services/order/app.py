"""
Order Service - Dummy microservice for testing auto-healer agent.
Includes chaos injection endpoints for testing 5xx error scenarios.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Configure structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Order Service", version="1.0.0")

# Service URLs from environment (defaults for local testing)
import os
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://payment:8002")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://inventory:8003")


class OrderRequest(BaseModel):
    item_id: str
    quantity: int
    customer_id: str


class OrderResponse(BaseModel):
    order_id: str
    status: str
    payment_id: Optional[str] = None
    inventory_status: Optional[str] = None
    timestamp: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "order", "timestamp": datetime.utcnow().isoformat()}


@app.get("/order")
async def create_order(
    item_id: str = Query(default="item-001"),
    quantity: int = Query(default=1),
    customer_id: str = Query(default="customer-123"),
    chaos_type: Optional[str] = Query(default=None)
):
    """
    Create an order by calling Payment and Inventory services.

    Chaos injection types:
    - 500_zerodivision: Triggers ZeroDivisionError
    - 504_gateway_timeout: Causes timeout with long sleep
    - 502_bad_gateway: Simulates upstream service failure
    """
    order_id = str(uuid.uuid4())

    logger.info(json.dumps({
        "event": "order_received",
        "order_id": order_id,
        "item_id": item_id,
        "quantity": quantity,
        "chaos_type": chaos_type
    }))

    # Chaos injection
    if chaos_type == "500_zerodivision":
        logger.error(json.dumps({
            "event": "chaos_triggered",
            "type": "500_zerodivision",
            "order_id": order_id
        }))
        # This will cause an unhandled exception and 500 error
        result = 1 / 0

    elif chaos_type == "504_gateway_timeout":
        logger.warning(json.dumps({
            "event": "chaos_triggered",
            "type": "504_gateway_timeout",
            "order_id": order_id,
            "sleep_duration": 60
        }))
        await asyncio.sleep(60)
        raise HTTPException(status_code=504, detail="Gateway Timeout")

    elif chaos_type == "502_bad_gateway":
        logger.error(json.dumps({
            "event": "chaos_triggered",
            "type": "502_bad_gateway",
            "order_id": order_id
        }))
        raise HTTPException(status_code=502, detail="Bad Gateway - Upstream service failure")

    # Normal flow - call downstream services
    try:
        # Check inventory
        async with httpx.AsyncClient(timeout=5.0) as client:
            logger.info(json.dumps({
                "event": "calling_inventory_service",
                "order_id": order_id,
                "url": f"{INVENTORY_URL}/check_stock"
            }))

            inventory_response = await client.post(
                f"{INVENTORY_URL}/check_stock",
                json={"item_id": item_id, "quantity": quantity}
            )
            inventory_data = inventory_response.json()

            if not inventory_data.get("in_stock", False):
                logger.warning(json.dumps({
                    "event": "inventory_check_failed",
                    "order_id": order_id,
                    "item_id": item_id
                }))
                raise HTTPException(status_code=400, detail="Item out of stock")

            # Process payment
            logger.info(json.dumps({
                "event": "calling_payment_service",
                "order_id": order_id,
                "url": f"{PAYMENT_URL}/process_payment"
            }))

            payment_response = await client.post(
                f"{PAYMENT_URL}/process_payment",
                json={"order_id": order_id, "amount": quantity * 10.0}
            )
            payment_data = payment_response.json()

            logger.info(json.dumps({
                "event": "order_completed",
                "order_id": order_id,
                "payment_id": payment_data.get("payment_id"),
                "status": "success"
            }))

            return OrderResponse(
                order_id=order_id,
                status="success",
                payment_id=payment_data.get("payment_id"),
                inventory_status="confirmed",
                timestamp=datetime.utcnow().isoformat()
            )

    except httpx.TimeoutException as e:
        logger.error(json.dumps({
            "event": "downstream_timeout",
            "order_id": order_id,
            "error": str(e)
        }))
        raise HTTPException(status_code=504, detail=f"Downstream service timeout: {str(e)}")

    except httpx.HTTPError as e:
        logger.error(json.dumps({
            "event": "downstream_http_error",
            "order_id": order_id,
            "error": str(e)
        }))
        raise HTTPException(status_code=502, detail=f"Downstream service error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
