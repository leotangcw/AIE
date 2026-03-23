"""Memory-MCP-Server main entry point."""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from .models.config import Config
from .protocol.server import run_server
from .service.memory_service import MemoryService


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    logger.remove()

    level = "DEBUG" if verbose else "INFO"

    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )


async def main() -> None:
    """Main entry point."""
    # Parse arguments
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    config_path = None

    for arg in sys.argv:
        if arg.startswith("--config="):
            config_path = arg.split("=", 1)[1]

    setup_logging(verbose)

    # Load configuration
    if config_path:
        config = Config.from_yaml(Path(config_path))
    else:
        # Try default paths
        default_paths = [
            Path("config/default.yaml"),
            Path(__file__).parent.parent.parent / "config" / "default.yaml",
        ]
        for path in default_paths:
            if path.exists():
                config = Config.from_yaml(path)
                logger.info(f"Loaded config from {path}")
                break
        else:
            config = Config()
            logger.info("Using default configuration")

    # Override db_path from environment if set
    import os
    db_path_env = os.environ.get("MEMORY_DB_PATH")
    if db_path_env:
        config.storage.db_path = db_path_env
        logger.info(f"Using database path from environment: {db_path_env}")

    # Create service
    service = MemoryService(config)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(service)))

    logger.info("Starting Memory-MCP-Server...")
    logger.info(f"Mode: {config.server.mode}")

    try:
        await run_server(service)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await service.close()
        logger.info("Server stopped")


async def shutdown(service: MemoryService) -> None:
    """Graceful shutdown."""
    logger.info("Shutting down...")
    await service.close()


if __name__ == "__main__":
    asyncio.run(main())
