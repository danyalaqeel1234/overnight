from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import BodySizeLimitMiddleware, register_exception_handlers
from app.core.rate_limiter import RollingRateLimiter
from app.domain.models import db_state
from app.api.health import router as health_router
from app.api.reset import router as reset_router
from app.api.sports import router as sports_router
from app.api.fixtures import router as fixtures_router
from app.api.leagues import router as leagues_router
from app.api.events import router as events_router
from app.api.standings import router as standings_router
from app.api.roster import router as roster_router
from app.api.checkout import router as checkout_router
from app.api.rbac import router as rbac_router
from app.api.ping import router as ping_router
from app.api.offline_sync import router as offline_sync_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_state.seed_baseline()
    yield


app = FastAPI(title="NaSCon '26 Backend", lifespan=lifespan)

_rate_limiter = RollingRateLimiter(limit=100, window_seconds=10.0)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/v1/"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        allowed, retry_after = _rate_limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMITED", "message": "Rate limit exceeded", "details": {}}},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(reset_router)
app.include_router(sports_router)
app.include_router(fixtures_router)
app.include_router(leagues_router)
app.include_router(events_router)
app.include_router(standings_router)
app.include_router(roster_router)
app.include_router(checkout_router)
app.include_router(rbac_router)
app.include_router(ping_router)
app.include_router(offline_sync_router)
