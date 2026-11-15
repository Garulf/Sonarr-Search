from typing import List, Optional

import requests


class Sonarr:
    def __init__(self, url: str, api_key: str, session: Optional[requests.Session] = None) -> None:
        self.url = url
        self.api_key = api_key
        self.session = session or requests.Session()

    def _get(self, path: str, params: Optional[dict] = None):
        response = self.session.get(
            f"{self.url}{path}",
            headers={"X-Api-Key": self.api_key},
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def series(self) -> List[dict]:
        return self._get("/api/v3/series")

    def lookup(self, term: str) -> List[dict]:
        return self._get("/api/v3/series/lookup", params={"term": term})
