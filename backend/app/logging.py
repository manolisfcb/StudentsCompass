"""Logging setup: every line carries the request it belongs to.

The format gained ``request_id`` in TASK-028. It is filled by a log record
factory rather than by each call site or by a per-handler filter, so a handler
added later — pytest's ``caplog``, a JSON handler, a library's own — still
produces records the format can render. A line logged outside a request says
``-``.
"""
import logging

from app.core.observability import install_request_id_log_factory

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [req %(request_id)s] %(message)s"


def setup_logging():
    install_request_id_log_factory()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    return logging.getLogger(__name__)


logger = setup_logging()
