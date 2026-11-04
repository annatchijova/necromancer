import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_synthetic", ROOT / "fixtures" / "build_synthetic.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def synthetic(tmp_path_factory):
    builder = _load_builder()
    base = tmp_path_factory.mktemp("synthetic")
    return builder.build_all(base)
