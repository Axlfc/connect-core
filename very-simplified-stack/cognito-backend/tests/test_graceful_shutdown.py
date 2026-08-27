import signal
import os
import pytest
from app.main import handle_sigterm, shutdown_event

def test_handle_sigterm_sets_shutdown_event():
    # Ensure event is cleared
    shutdown_event.clear()
    assert not shutdown_event.is_set()

    # Trigger handle_sigterm
    handle_sigterm(signal.SIGTERM, None)

    assert shutdown_event.is_set()
