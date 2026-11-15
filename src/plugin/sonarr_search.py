import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from pyflowlauncher import FlowLauncherV2, Plugin, Result, api, icons
from pyflowlauncher.models.result import PreviewInfo
from requests.exceptions import HTTPError, JSONDecodeError, RequestException

from sonarr import Sonarr

PLUGIN_NAME = "Sonarr Search"
ICON = str(Path(__file__).resolve().parent.parent / "icon.png")
DEFAULT_URL = "http://localhost:8989"
SERIES_MAX_AGE = 300

plugin = Plugin(launcher=FlowLauncherV2())
series_cache: Dict[Tuple[str, str], Tuple[float, List[dict]]] = {}


def make_result(title: str, subtitle: Optional[str], icon: Optional[str] = ICON) -> Result:
    # Flow Launcher's preview panel throws on a null Preview (Garulf/pyFlowLauncher#44).
    preview = PreviewInfo(PreviewImagePath=None, Description=subtitle, IsMedia=False, PreviewDeligate=None)
    return Result(title=title, subtitle=subtitle, icon=icon, preview=preview)


def settings_result(title: str, subtitle: str) -> Result:
    return make_result(title, subtitle, icons.SETTINGS or ICON).add_action(api.open_setting_dialog())


def format_subtitle(text: str) -> str:
    return text.replace("\r\n", " ").replace("\n", " ")


def sonarr() -> Sonarr:
    settings = plugin.settings
    url = (settings.get("url") or DEFAULT_URL).strip().rstrip("/")
    return Sonarr(url, (settings.get("api_key") or "").strip())


def cached_series(client: Sonarr) -> List[dict]:
    key = (client.url, client.api_key)
    cached = series_cache.get(key)
    if cached and time.monotonic() - cached[0] < SERIES_MAX_AGE:
        return cached[1]
    shows = client.series()
    if shows:
        series_cache[key] = (time.monotonic(), shows)
    return shows


def library_results(client: Sonarr, query: str, shows: List[dict]) -> List[Result]:
    results = []
    for show in shows:
        if query.lower() in show["title"].lower():
            show_url = f"{client.url}/series/{show['titleSlug']}"
            result = make_result(show["title"], format_subtitle(show["overview"]))
            result.context_data = [show_url]
            results.append(result.add_action(api.open_url(show_url)))
    return results


def new_series_results(client: Sonarr, query: str) -> List[Result]:
    add_url = f"{client.url}/add/new?term={quote(query)}"
    return [
        make_result(show["title"], format_subtitle(show.get("overview", "..."))).add_action(api.open_url(add_url))
        for show in client.lookup(query)
    ]


def search(client: Sonarr, query: str) -> List[Result]:
    if not client.api_key:
        return [settings_result("Please set your API key", f"Plugins > {PLUGIN_NAME} > API Key")]
    try:
        shows = cached_series(client)
        if not shows:
            return [unauthorized_result()]
        return library_results(client, query, shows) or new_series_results(client, query)
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 401:
            return [unauthorized_result()]
        return [settings_result("Sonarr returned an error", f"{error}. Please check your Sonarr URL")]
    except JSONDecodeError:
        return [settings_result("Sonarr returned an unexpected reply", "Please check your Sonarr URL")]
    except RequestException:
        return [settings_result("Connection Error", "Please check your settings")]


def unauthorized_result() -> Result:
    return settings_result("Unauthorized or No shows found!", "Please check your API key.")


@plugin.on_method
async def query(query: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, search, sonarr(), query)


@plugin.on_method
def context_menu(data):
    if not data:
        return []
    show_url = data[0]
    return [make_result("Open in browser", show_url, icons.BROWSER or ICON).add_action(api.open_url(show_url))]
