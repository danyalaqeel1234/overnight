from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.errors import BodySizeLimitMiddleware, register_exception_handlers
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_state.seed_baseline()
    yield


app = FastAPI(title="NaSCon '26 Backend", lifespan=lifespan)

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
