import shutil

import pytest


def pytest_collection_modifyitems(config, items):
    if shutil.which("soffice"):
        return
    skip = pytest.mark.skip(reason="LibreOffice (soffice) не установлен")
    for item in items:
        if "soffice" in item.keywords:
            item.add_marker(skip)
