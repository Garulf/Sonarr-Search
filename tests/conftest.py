import json

import pytest
import requests

import sonarr_search
from sonarr import Sonarr

URL = "http://sonarr.example.lan:8989"
API_KEY = "0123456789abcdef0123456789abcdef"

SERIES = [
    {
        "id": 1,
        "title": "The Expanse",
        "titleSlug": "the-expanse",
        "overview": "Hundreds of years in the future,\nhumans have colonized the solar system.",
        "year": 2015,
        "tvdbId": 280619,
    },
    {
        "id": 2,
        "title": "Breaking Bad",
        "titleSlug": "breaking-bad",
        "overview": "A high school chemistry teacher turns to making meth.",
        "year": 2008,
        "tvdbId": 81189,
    },
]
LOOKUP = [
    {"title": "Severance", "titleSlug": "severance", "overview": "Mark leads a team of office workers.", "year": 2022, "tvdbId": 371980},
    {"title": "Severance (2006)", "titleSlug": "severance-2006", "year": 2006, "tvdbId": 79604},
]


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error", response=self)

    def json(self):
        if isinstance(self._payload, str):
            raise requests.exceptions.JSONDecodeError("Expecting value", self._payload, 0)
        return json.loads(json.dumps(self._payload))


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.timeouts = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, headers, params))
        self.timeouts.append(timeout)
        path = url.split("8989", 1)[1]
        response = self.responses.get(path)
        if isinstance(response, Exception):
            raise response
        return response if response is not None else FakeResponse([])


@pytest.fixture(autouse=True)
def clear_cache():
    sonarr_search.series_cache.clear()
    yield
    sonarr_search.series_cache.clear()


@pytest.fixture
def settings():
    launcher = sonarr_search.plugin.launcher
    launcher._settings = {"url": URL, "api_key": API_KEY}
    yield launcher._settings
    launcher._settings = {}


@pytest.fixture
def session():
    return FakeSession({
        "/api/v3/series": FakeResponse(SERIES),
        "/api/v3/series/lookup": FakeResponse(LOOKUP),
    })


@pytest.fixture
def client(session):
    return Sonarr(URL, API_KEY, session=session)
