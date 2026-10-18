from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppException
from app.domain.qr_guest import qr_guest_domain

router = APIRouter()


@router.post("/audit/v1/guest/cart-merge")
async def guest_cart_merge(request: Request):
    try:
        raw = await request.body()
        if not raw:
            raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)
        import json
        body = json.loads(raw)
    except AppException:
        raise
    except Exception:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    if not isinstance(body, dict):
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": []}, 400)

    invalid_fields: list[str] = []

    guest_token = body.get("guest_token")
    if not isinstance(guest_token, str) or not guest_token.startswith("guest_"):
        invalid_fields.append("guest_token")

    registered_user_id = body.get("registered_user_id")
    if not isinstance(registered_user_id, str) or not registered_user_id.strip():
        invalid_fields.append("registered_user_id")

    guest_cart = body.get("guest_cart")
    if not isinstance(guest_cart, list) or not (1 <= len(guest_cart) <= 10):
        invalid_fields.append("guest_cart")
    else:
        for item in guest_cart:
            if not isinstance(item, dict):
                invalid_fields.append("guest_cart")
                break
            vid = item.get("variant_id")
            qty = item.get("quantity")
            if not isinstance(vid, str) or not vid.strip():
                invalid_fields.append("guest_cart")
                break
            if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
                invalid_fields.append("guest_cart")
                break

    test_write_block = body.get("test_write_block", True)
    if not isinstance(test_write_block, bool):
        invalid_fields.append("test_write_block")

    if invalid_fields:
        raise AppException("VALIDATION_ERROR", "Validation error", {"fields": invalid_fields}, 400)

    result = qr_guest_domain.merge_guest_cart(
        guest_token=guest_token,
        registered_user_id=registered_user_id,
        guest_cart=guest_cart,
        test_write_block=test_write_block,
    )
    return JSONResponse(status_code=200, content=result)


@router.post("/api/v1/guest/cart")
async def stage_guest_cart(request: Request):
    """Guest cart staging allowed for guests."""
    body = await request.json() if await request.body() else {}
    guest_token = body.get("guest_token", "guest_anon_tok_7721")
    items = body.get("items", [])
    qr_guest_domain.guest_carts[guest_token] = items
    return JSONResponse(status_code=200, content={"status": "staged", "items_count": len(items)})


@router.post("/api/v1/chat")
async def post_chat(request: Request):
    """
    Authenticated chat endpoint.
    GuestWriteGuardMiddleware will reject any guest tokens with 403.
    """
    body = await request.json() if await request.body() else {}
    return JSONResponse(status_code=201, content={"status": "message_broadcast", "data": body})
