import random
import shutil
from pathlib import Path

import pytest
import yaml

from awato.engine import Engine
from awato.loader import DEFAULT_CONTENT_DIR, load_content


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Never touch the real save folder."""
    monkeypatch.setenv("AWATO_DATA_DIR", str(tmp_path / "data"))


@pytest.fixture
def content():
    return load_content()


@pytest.fixture
def engine(content):
    e = Engine(content, rng=random.Random(1))
    e.new_game("Tester")
    return e


@pytest.fixture
def content_copy(tmp_path):
    """A writable copy of content/, plus a helper to patch one of its YAML files."""
    root = tmp_path / "content"
    shutil.copytree(DEFAULT_CONTENT_DIR, root)

    def patch(rel, update):
        path = Path(root, rel)
        data = yaml.safe_load(path.read_text()) or {}
        update(data)
        path.write_text(yaml.safe_dump(data, sort_keys=False))

    return root, patch
