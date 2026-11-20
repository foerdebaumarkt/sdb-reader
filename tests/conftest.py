import os
from collections.abc import Iterator

import pytest
import structlog
import structlog.contextvars
import structlog.stdlib
from hypothesis import HealthCheck, settings

# Property tests (tests/test_reading_time.py). "ci", the default: few fixed
# examples, the same on every run, nothing stored between runs. "thorough":
# many random ones, for a search by hand before a release.
settings.register_profile(
    "ci",
    max_examples=40,
    derandomize=True,
    database=None,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.register_profile(
    "thorough",
    max_examples=2000,
    database=None,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))


@pytest.fixture(autouse=True)
def configure_structlog_for_tests() -> Iterator[None]:
    """Log through the standard library, so caplog sees the lines.

    Reset first and afterwards: structlog's default logger prints to the
    stdout it found when first used, which under pytest is one test's capture
    and closed by the next.
    """
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
    yield
    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def _tesseract_of_a_known_version(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test that stands in for the text recognition must not depend on the
    program being installed: its version is asked wherever a text was read by
    it (SDB-116). Tests marked ``real_tesseract`` ask the program itself."""
    if request.node.get_closest_marker("real_tesseract") is None:
        from sdb_reader import extraction

        monkeypatch.setattr(extraction, "_tesseract_version", lambda: "5.5.4")
