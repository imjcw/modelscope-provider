import asyncio
import os
import sys
import time
from pathlib import Path

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# When imported as a module (e.g. via uvicorn), use 'provider.' prefix;
# when run as a script from the provider/ dir, bare imports work.
try:
    from provider.core.config import ConfigManager
    from provider.core.service_init import ServiceInitializer
    from provider.api.openai_routes import router
    from provider.api.admin_routes import router as admin_router
except ImportError:
    from core.config import ConfigManager
    from core.service_init import ServiceInitializer
    from api.openai_routes import router
    from api.admin_routes import router as admin_router
import logging
import logging.handlers

# Configure logging: write to file (rotating, max 5MB per file, keep 5 backups)
# + console. Log directory / file / level are overridable via env vars (LOG_DIR,
# LOG_FILE, LOG_LEVEL) so the process can run in read-only or containerized
# environments.
log_dir = Path(os.getenv("LOG_DIR", str(Path(__file__).parent / "logs")))
log_dir.mkdir(exist_ok=True)
_log_file = os.getenv("LOG_FILE", str(log_dir / "ai_router.log"))
_log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "5242880"))  # 5 MB
_log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))  # keep 5 archives
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            _log_file,
            maxBytes=_log_max_bytes,
            backupCount=_log_backup_count,
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

async def initialize_services():
    """Initialize all services (async).

    Returns the assembled services dict. Callers should treat the result as
    app-scoped state and stash it on ``app.state`` (see :func:`lifespan`) rather
    than relying on a module-level global — this keeps service state tied to the
    app instance and makes the code testable without process-wide singletons.
    """
    config = ConfigManager()

    initializer = ServiceInitializer(config)
    # Pass accounts=None so ServiceInitializer loads from DB (with .env migration)
    services = await initializer.initialize_all(accounts=None)

    # Record app start time for uptime calculation
    try:
        from provider.api import admin_routes as _ar
    except ImportError:
        from api import admin_routes as _ar
    _ar.APP_START_TIME = time.time()

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
        from provider.repositories.client_api_key_repository import ClientApiKeyRepository
        from provider.repositories.provider_type_repository import ProviderTypeRepository
    except ImportError:
        from services.admin_service import AdminService
        from repositories.account_repository import AccountRepository
        from repositories.mapping_repository import MappingRepository
        from repositories.mapping_model_repository import MappingModelRepository
        from repositories.config_repository import ConfigRepository
        from repositories.log_repository import LogRepository
        from repositories.quota_repository import QuotaRepository
        from repositories.supplier_model_repository import SupplierModelRepository
        from repositories.client_api_key_repository import ClientApiKeyRepository
        from repositories.provider_type_repository import ProviderTypeRepository

    db = services["database"]
    admin_service = AdminService(
        account_repo=AccountRepository(db),
        mapping_repo=MappingRepository(db),
        config_repo=ConfigRepository(db),
        log_repo=LogRepository(db),
        quota_repo=QuotaRepository(db),
        supplier_model_repo=SupplierModelRepository(db),
        mapping_model_repo=MappingModelRepository(db),
        client_key_repo=ClientApiKeyRepository(db),
        provider_type_repo=ProviderTypeRepository(db),
        rate_limit_strategies=services.get("rate_limit_strategies"),
        db=db,
        quota_updater=services.get("quota_updater"),
        config_cache=services.get("config_cache"),
        rate_limit_cache=services.get("rate_limit_cache"),
    )
    # Expose admin_service so the periodic cleanup task can find it via services["admin_service"]
    services["admin_service"] = admin_service
    logger.info(f"Loaded {len(services['accounts'])} accounts, admin service initialized")

    return services


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for FastAPI."""
    services = await initialize_services()
    app.state.services = services
    app.state.admin_service = services["admin_service"]
    app.state.alias_router = services["alias_router"]

    # Periodic task intervals are overridable via env vars so operators can
    # tune them without redeploying (e.g. LOG_CLEANUP_INTERVAL=600).
    log_cleanup_interval = int(os.getenv("LOG_CLEANUP_INTERVAL", "300"))
    rl_flush_interval = int(os.getenv("RATE_LIMIT_FLUSH_INTERVAL", "60"))
    config_sync_interval = int(os.getenv("CONFIG_SYNC_INTERVAL", "300"))

    # Start periodic log cleanup (every 5 minutes by default)
    async def _periodic_log_cleanup(svc, interval: int = log_cleanup_interval):
        """Periodically delete old request logs based on retention config."""
        while True:
            try:
                await asyncio.sleep(interval)
                admin = svc.get("admin_service")
                if admin:
                    await asyncio.to_thread(admin.cleanup_old_logs)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Log cleanup task failed", exc_info=True)

    # Start periodic rate-limit flush (every 60 seconds by default)
    async def _periodic_rate_limit_flush(svc, interval: int = rl_flush_interval):
        """Flush dirty rate-limit counters from memory to database."""
        while True:
            try:
                await asyncio.sleep(interval)
                cache = svc.get("rate_limit_cache")
                if cache:
                    await asyncio.to_thread(cache.flush)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Rate-limit flush task failed", exc_info=True)

    # Start periodic config sync (every 5 minutes by default)
    async def _periodic_config_sync(svc, interval: int = config_sync_interval):
        """Reload config from database to catch external changes."""
        while True:
            try:
                await asyncio.sleep(interval)
                cache = svc.get("config_cache")
                if cache:
                    await asyncio.to_thread(cache.reload)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Config sync task failed", exc_info=True)

    cleanup_task = asyncio.create_task(_periodic_log_cleanup(services, log_cleanup_interval))
    rl_flush_task = asyncio.create_task(_periodic_rate_limit_flush(services, rl_flush_interval))
    config_sync_task = asyncio.create_task(_periodic_config_sync(services, config_sync_interval))
    logger.info(
        "Periodic tasks started: log cleanup (%ss), rate-limit flush (%ss), config sync (%ss)",
        log_cleanup_interval, rl_flush_interval, config_sync_interval,
    )

    logger.info("AI Provider started")
    yield
    logger.info("AI Provider shutting down")

    # Cancel background tasks
    cleanup_task.cancel()
    rl_flush_task.cancel()
    config_sync_task.cancel()
    for t in (cleanup_task, rl_flush_task, config_sync_task):
        try:
            await t
        except asyncio.CancelledError:
            pass

    # Flush any in-memory rate-limit counters before exiting so a restart
    # (including uvicorn --reload) does not lose the current window counts.
    rl_cache = services.get("rate_limit_cache")
    if rl_cache:
        try:
            rl_cache.flush()
        except Exception:
            logger.warning("Rate-limit flush on shutdown failed", exc_info=True)

    # Close HTTP client
    http_client = services.get("http_client")
    if http_client:
        await http_client.close_all_clients()


# Reject oversized request bodies to protect upstream accounts. Defined at
# module level (not inside lifespan) so it is importable/testable and applies
# to every app instance created by create_app().
MAX_REQUEST_BODY = 16 * 1024 * 1024  # 16 MB
_BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def limit_request_body(request, call_next):
    """Enforce a request body size cap.

    The fast path validates ``Content-Length``. Requests without it (e.g.
    ``Transfer-Encoding: chunked``) would bypass that check, so they are
    buffered and capped here — closing the chunked-encoding body-size bypass.
    """
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BODY:
        return JSONResponse(
            status_code=413,
            content={
                "error": "Payload too large",
                "detail": f"Request body exceeds the {MAX_REQUEST_BODY} byte limit",
            },
        )
    if content_length is None and request.method in _BODY_METHODS:
        received = 0
        chunks = []
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_REQUEST_BODY:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Payload too large",
                        "detail": f"Request body exceeds the {MAX_REQUEST_BODY} byte limit",
                    },
                )
            chunks.append(chunk)
        body = b"".join(chunks)

        async def _receive():  # noqa: ANN202
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = _receive
    return await call_next(request)


def create_app():
    """Create and configure FastAPI application."""
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="AI Provider API",
        description="OpenAI-compatible AI provider gateway with multi-vendor load balancing, quota management, and circuit breaking",
        version="0.2.0",
        lifespan=lifespan
    )

    # Register body-size limit middleware (defined at module level so it is
    # importable for tests and applies to every created app instance).
    app.middleware("http")(limit_request_body)

    # Include API routes
    app.include_router(router, prefix="/openai", tags=["OpenAI"])
    # DEPRECATED dual mount: the pre-2026-08 API used the /api prefix
    # (e.g. /api/v1/chat/completions). Kept only for backward compatibility
    # with existing clients. New integrations should use the /openai prefix.
    app.include_router(router, prefix="/api", tags=["OpenAI-legacy"])
    app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])

    # Disable cache for static assets (dev convenience — prevents browser caching old JS)
    @app.middleware("http")
    async def disable_static_cache(request, call_next):
        response = await call_next(request)
        if request.url.path.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Expires"] = "0"
        return response

    # Root redirect to frontend
    @app.get("/")
    def root_redirect():
        """Redirect root to the web dashboard."""
        return RedirectResponse(url="/web/")

    # Health check — root-level endpoint
    @app.get("/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": "0.2.0"}

    # Serve static frontend files (no cache in dev for hot refresh)
    if getattr(sys, "frozen", False):
        dist_dir = Path(sys._MEIPASS) / "web" / "dist"
    else:
        dist_dir = Path(__file__).parent / "web" / "dist"
    if dist_dir.exists():
        # SPA fallback: in history mode, unknown paths should render index.html
        # so refreshing /web/logs etc. doesn't 404. Static assets under
        # web/dist/assets/* still resolve normally because they exist on disk.
        class SPAStaticFiles(StaticFiles):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            async def get_response(self, path: str, scope):
                try:
                    return await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    if exc.status_code == 404 and not path.startswith("assets/"):
                        # History-mode deep link → serve the SPA entry point.
                        return await super().get_response("index.html", scope)
                    raise

        app.mount(
            "/web",
            SPAStaticFiles(directory=str(dist_dir), html=True, check_dir=False),
            name="static",
        )
        logger.info(f"Serving static files from {dist_dir}")
    else:
        logger.warning("Frontend dist directory not found, static files not served")

    return app


# Create application
app = create_app()

