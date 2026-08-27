import signal
import pytest
from worker_app.main import handle_sigterm, shutdown_event

def test_worker_handle_sigterm_sets_shutdown_event():
    shutdown_event.clear()
    assert not shutdown_event.is_set()

    handle_sigterm(signal.SIGTERM, None)

    assert shutdown_event.is_set()
