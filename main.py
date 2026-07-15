import asyncio
from fastapi import FastAPI
from provider.core.config import ConfigManager
from provider.core.service_init import ServiceInitializer
from provider.api.routes import router
import logging

logger = logging.getLogger(__name__)


def create_app():
    """Create and configure FastAPI application."""
    # Load configuration
    config = ConfigManager()

    # Load accounts
    try:
        accounts = config.load_accounts_from_env()
        logger.info(f"Loaded {len(accounts)} ModelScope accounts")
    except ValueError as e:
        logger.error(f"Failed to load accounts: {e}")
        raise

    # Initialize services (sync wrapper for async)
    initializer = ServiceInitializer(config)
    services = asyncio.run(initializer.initialize_all(accounts))

    # Create FastAPI app
    app = FastAPI(
        title="ModelScope Proxy API",
        description="OpenAI-compatible proxy for ModelScope API with quota management",
        version="0.1.0"
    )

    # Include routes
    app.include_router(router, prefix="/api", tags=["API"])

    # Store services in app state for easy access
    app.state.services = services

    return app


# Create application
app = create_app()


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("ModelScope Proxy starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("ModelScope Proxy shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
