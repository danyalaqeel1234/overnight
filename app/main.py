from fastapi import FastAPI

from app.core.errors import BodySizeLimitMiddleware, register_exception_handlers
from app.domain.models import db_state
from app.api.health import router as health_router
from app.api.reset import router as reset_router
from app.api.sports import router as sports_router
from app.api.fixtures import router as fixtures_router

app = FastAPI(title="NaSCon '26 Backend")

# Middleware (order matters: added last = runs first)
app.add_middleware(BodySizeLimitMiddleware)

# Exception handlers
register_exception_handlers(app)

# Routers
app.include_router(health_router)
app.include_router(reset_router)
app.include_router(sports_router)
app.include_router(fixtures_router)


@app.on_event("startup")
def startup_event():
    db_state.seed_baseline()
