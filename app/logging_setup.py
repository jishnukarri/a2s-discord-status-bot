"""Logging setup: console output + Sentry.io error reporting.

No log files are written locally - all warnings/errors ship to Sentry when
SENTRY_DSN is configured. Console logging is kept for interactive/docker-logs
visibility.
"""
from __future__ import annotations
import logging

from .config import CONFIG


def setup_logging() -> None:
    level = getattr(logging, str(CONFIG['LOG_LEVEL']).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler()],
    )

    dsn = CONFIG['SENTRY_DSN']
    if not dsn:
        logging.getLogger(__name__).warning('SENTRY_DSN not set - error reporting disabled.')
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        sentry_sdk.init(
            dsn=dsn,
            environment=CONFIG['ENVIRONMENT'],
            integrations=[sentry_logging],
            traces_sample_rate=0.0,
        )
        logging.getLogger(__name__).info('Sentry error reporting enabled (%s).', CONFIG['ENVIRONMENT'])
    except Exception:
        logging.getLogger(__name__).exception('Failed to initialize Sentry.')


__all__ = ['setup_logging']
