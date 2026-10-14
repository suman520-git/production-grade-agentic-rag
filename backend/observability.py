import json
import logging
import sys
from datetime import datetime, timezone
from functools import wraps
from time import perf_counter


logger = logging.getLogger("rag.trace")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def log_event(event, request_id, level=logging.INFO, **fields):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level),
        "event": event,
        "request_id": request_id,
        **fields,
    }

    logger.log(level, json.dumps(record))


def traced_node(name, function):
    @wraps(function)
    def wrapped(state):
        request_id = state["request_id"]
        started = perf_counter()

        log_event(
            "node_started",
            request_id,
            node=name,
        )

        try:
            result = function(state)

        except Exception as exc:
            log_event(
                "node_failed",
                request_id,
                level=logging.ERROR,
                node=name,
                duration_ms=round(
                    (perf_counter() - started) * 1000,
                    2,
                ),
                error_type=type(exc).__name__,
            )

            # Preserve the existing error-handling behavior.
            raise

        log_event(
            "node_finished",
            request_id,
            node=name,
            duration_ms=round(
                (perf_counter() - started) * 1000,
                2,
            ),
        )

        return result

    return wrapped