"""Webhooks endpoints (Clerk, Stripe, etc.)."""
from fastapi import APIRouter, Request, HTTPException, status
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/clerk")
async def clerk_webhook(request: Request):
    """Handle Clerk webhooks (user.created, user.updated, etc.)."""
    try:
        body = await request.body()
        event = await request.json()

        event_type = event.get("type")
        data = event.get("data", {})

        logger.info(f"Clerk webhook: {event_type}")

        if event_type == "user.created":
            # Will be handled on first API call
            pass
        elif event_type == "user.updated":
            pass
        elif event_type == "user.deleted":
            # TODO: deactivate user in DB
            pass
        elif event_type == "session.ended":
            # User logged out
            pass

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Clerk webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks (for future billing)."""
    # TODO: implement when billing is added
    return {"status": "ok"}
