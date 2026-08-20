from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests


FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, *, url: str, text: str = "", data=None, status_code: int = 200):
        self.url = url
        self.text = text
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}

    def request(self, method, url, **kwargs):
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        response = self.responses.pop(0)
        response.url = response.url or url
        return response


@pytest.fixture
def load_json():
    return lambda name: json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def load_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")

