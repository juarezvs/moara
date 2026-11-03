"""Use the shipped Moara HTTP routes without startup jobs or bootstrap writes."""
from contextlib import asynccontextmanager
import httpx
from moara.gateway.api import create_app
from moara.gateway.settings import Settings
from moara.gateway.database import Database
from moara.gateway.auth import Auth
from moara.gateway.identity_api import IdentityStore

config=Settings.load()
config.legacy_gateway='http://moara-validation-adapter:8000'
app=create_app(config)

@asynccontextmanager
async def validation_lifespan(app):
    app.state.settings=config
    app.state.db=Database(config)
    app.state.http=httpx.AsyncClient(timeout=httpx.Timeout(300,connect=5),trust_env=False)
    app.state.auth=Auth(config,app.state.db,app.state.http)
    app.state.identity=IdentityStore(app.state.db)
    try: yield
    finally:
        await app.state.auth.close()
        await app.state.http.aclose()
        await app.state.db.dispose()

app.router.lifespan_context=validation_lifespan
