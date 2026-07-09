import os
import tempfile
from pathlib import Path
from app.core.project_trust import ProjectTrustStore

def test_project_trust_store():
    with tempfile.NamedTemporaryFile() as tmp:
        store = ProjectTrustStore(store_path=Path(tmp.name))
        repo = "/tmp/fake-repo"

        assert store.is_trusted(repo) is False

        store.set_trusted(repo, True)
        assert store.is_trusted(repo) is True

        store.set_trusted(repo, False)
        assert store.is_trusted(repo) is False
