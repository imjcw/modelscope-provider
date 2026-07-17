import asyncio
import sys
from pathlib import Path

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# When imported as a module (e.g. via uvicorn), use 'provider.' prefix;
# when run as a script from the provider/ dir, bare imports work.
try:
    from provider.core.config import ConfigManager
    from provider.core.service_init import ServiceInitializer
    from provider.api.routes import router
    from provider.api.admin_routes import router as admin_router
except ImportError:
    from core.config import ConfigManager
    from core.service_init import ServiceInitializer
    from api.routes import router
    from api.admin_routes import router as admin_router
import logging

logger = logging.getLogger(__name__)

# Global services dictionary
_services = None
_admin_service = None


async def initialize_services():
    """Initialize all services (async)."""
    global _services, _admin_service
    config = ConfigManager()

    initializer = ServiceInitializer(config)
    # Pass accounts=None so ServiceInitializer loads from DB (with .env migration)
    _services = await initializer.initialize_all(accounts=None)

    # Initialize admin service
    try:
        from provider.services.admin_service import AdminService
        from provider.repositories.account_repository import AccountRepository
        from provider.repositories.mapping_repository import MappingRepository
        from provider.repositories.mapping_model_repository import MappingModelRepository
        from provider.repositories.config_repository import ConfigRepository
        from provider.repositories.log_repository import LogRepository
        from provider.repositories.quota_repository import QuotaRepository
        from provider.repositories.supplier_model_repository import SupplierModelRepository
    except ImportError:
        from services.admin_service import AdminService
        from repositories.account_repository import AccountRepository
        from repositories.mapping_repository import MappingRepository
        from repositories.mapping_model_repository import MappingModelRepository
        from repositories.config_repository import ConfigRepository
        from repositories.log_repository import LogRepository
        from repositories.quota_repository import QuotaRepository
        from repositories.supplier_model_repository import SupplierModelRepository

    db = _services["database"]
    admin_service = AdminService(
        account_repo=AccountRepository(db),
        mapping_repo=MappingRepository(db),
        config_repo=ConfigRepository(db),
        log_repo=LogRepository(db),
        quota_repo=QuotaRepository(db),
        supplier_model_repo=SupplierModelRepository(db),
        mapping_model_repo=MappingModelRepository(db),
    )
    _admin_service = admin_service
    logger.info(f"Loaded {len(_services['accounts'])} accounts, admin service initialized")

    return _services


def get_services():
    """Get services (sync helper)."""
    return _services


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for FastAPI."""
    services = await initialize_services()
    app.state.services = services
    app.state.admin_service = _admin_service
    logger.info("ModelScope Proxy started")
    yield
    logger.info("ModelScope Proxy shutting down")
    # Close HTTP client
    http_client = services.get("http_client")
    if http_client:
        await http_client.close_all_clients()


def create_app():
    """Create and configure FastAPI application."""
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="ModelScope Proxy API",
        description="OpenAI-compatible proxy for ModelScope API with quota management",
        version="0.2.0",
        lifespan=lifespan
    )

    # Include API routes
    app.include_router(router, prefix="/api", tags=["API"])
    app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])

    # Disable cache for static assets (dev convenience — prevents browser caching old JS)
    @app.middleware("http")
    async def disable_static_cache(request, call_next):
        response = await call_next(request)
        if request.url.path.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Expires"] = "0"
        return response

    # Serve static frontend files (no cache in dev for hot refresh)
    dist_dir = Path(__file__).parent / "web" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True, check_dir=False), name="static")
        logger.info(f"Serving static files from {dist_dir}")
    else:
        logger.warning("Frontend dist directory not found, static files not served")

    return app


# Create application
app = create_app()

