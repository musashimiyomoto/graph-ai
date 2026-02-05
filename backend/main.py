"""Backend entrypoint."""

import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the backend entrypoint."""
    logger.info("Backend entrypoint invoked.")


if __name__ == "__main__":
    main()
