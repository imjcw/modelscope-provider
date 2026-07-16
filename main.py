import asyncio
import sys
from pathlib import Path

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from core.config import ConfigManager
from core.service_init import ServiceInitializer
from api.routes import router
import logging

logger = logging.getLogger(__name__)

# Global services dictionary
_services = None


async def initialize_services():
    """Initialize all services (async)."""
    global _services
    config = ConfigManager()
    accounts = config.load_accounts_from_env()
    logger.info(f"Loaded {len(accounts)} ModelScope accounts")

    initializer = ServiceInitializer(config)
    _services = await initializer.initialize_all(accounts)
    return _services


def get_services():
    """Get services (sync helper)."""
    return _services


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for FastAPI."""
    services = await initialize_services()
    app.state.services = services
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
        version="0.1.0",
        lifespan=lifespan
    )

    # Include routes
    app.include_router(router, prefix="/api", tags=["API"])

    return app


# Create application
app = create_app()
