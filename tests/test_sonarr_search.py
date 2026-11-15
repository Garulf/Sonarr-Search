import asyncio

import requests

import sonarr_search
from conftest import API_KEY, URL, FakeResponse


def titles(results):
    return [result.title for result in results]


def action(result):
    return result.to_json()["JsonRPCAction"]


def test_library_search_matches_title_case_insensitively(client):
    results = sonarr_search.search(client, "EXPANSE")
    assert titles(results) == ["The Expanse"]
    assert results[0].subtitle == "Hundreds of years in the future, humans have colonized the solar system."


def test_empty_query_lists_the_whole_library(client):
    assert titles(sonarr_search.search(client, "")) == ["The Expanse", "Breaking Bad"]


def test_library_result_opens_the_show_and_has_a_context_menu(client):
    result = sonarr_search.search(client, "breaking")[0]
    show_url = f"{URL}/series/breaking-bad"
    assert action(result) == {"Method": "Flow.Launcher.OpenUrl", "Parameters": [show_url, False], "DontHideAfterAction": False}
    assert result.context_data == [show_url]
    assert result.to_json()["Preview"] is not None


def test_context_menu_opens_the_show_in_the_browser(client):
    show_url = sonarr_search.search(client, "breaking")[0].context_data[0]
    menu = sonarr_search.context_menu([show_url])
    assert titles(menu) == ["Open in browser"]
    assert action(menu[0])["Parameters"] == [show_url, False]
    assert sonarr_search.context_menu([]) == []


def test_shows_without_an_overview_are_listed(client, session):
    session.responses["/api/v3/series"] = FakeResponse([
        {"id": 3, "title": "Andor", "titleSlug": "andor"},
        {"id": 4, "title": "Andor Shorts", "titleSlug": "andor-shorts", "overview": None},
    ])
    session.responses["/api/v3/series/lookup"] = FakeResponse([{"title": "Arcane", "overview": None}])
    assert [r.subtitle for r in sonarr_search.search(client, "andor")] == ["...", "..."]
    assert [r.subtitle for r in sonarr_search.search(client, "arcane")] == ["..."]


def test_unknown_show_falls_back_to_lookup(client, session):
    results = sonarr_search.search(client, "severance")
    assert titles(results) == ["Severance", "Severance (2006)"]
    assert results[1].subtitle == "..."
    assert action(results[0])["Parameters"] == [f"{URL}/add/new?term=severance", False]
    assert session.calls[-1][2] == {"term": "severance"}


def test_lookup_add_url_quotes_the_search_term(client):
    result = sonarr_search.search(client, "the office")[0]
    assert action(result)["Parameters"][0] == f"{URL}/add/new?term=the%20office"


def test_requests_send_the_api_key_header(client, session):
    sonarr_search.search(client, "")
    assert session.calls[0][1] == {"X-Api-Key": API_KEY}


def test_requests_time_out(client, session):
    sonarr_search.search(client, "severance")
    assert session.timeouts == [10, 10]


def test_timeout_is_reported_as_a_connection_error(client, session):
    session.responses["/api/v3/series"] = requests.exceptions.ReadTimeout()
    assert titles(sonarr_search.search(client, "")) == ["Connection Error"]


def test_missing_api_key_asks_for_settings(session):
    client = sonarr_search.Sonarr(URL, "", session=session)
    results = sonarr_search.search(client, "")
    assert titles(results) == ["Please set your API key"]
    assert results[0].subtitle == "Plugins > Sonarr Search > API Key"
    assert action(results[0])["Method"] == "Flow.Launcher.OpenSettingDialog"
    assert session.calls == []


def test_connection_error_asks_to_check_settings(client, session):
    session.responses["/api/v3/series"] = requests.exceptions.ConnectionError()
    results = sonarr_search.search(client, "")
    assert titles(results) == ["Connection Error"]
    assert action(results[0])["Method"] == "Flow.Launcher.OpenSettingDialog"


def test_unauthorized_reply_is_reported_and_not_cached(client, session):
    session.responses["/api/v3/series"] = FakeResponse({"message": "Unauthorized"}, status_code=401)
    assert titles(sonarr_search.search(client, "")) == ["Unauthorized or No shows found!"]
    assert sonarr_search.series_cache == {}


def test_empty_library_is_reported(client, session):
    session.responses["/api/v3/series"] = FakeResponse([])
    assert titles(sonarr_search.search(client, "")) == ["Unauthorized or No shows found!"]


def test_not_found_page_is_reported_instead_of_crashing(client, session):
    session.responses["/api/v3/series"] = FakeResponse("<html>Not Found</html>", status_code=404)
    results = sonarr_search.search(client, "")
    assert titles(results) == ["Sonarr returned an error"]
    assert action(results[0])["Method"] == "Flow.Launcher.OpenSettingDialog"


def test_html_reply_is_reported_instead_of_crashing(client, session):
    session.responses["/api/v3/series"] = FakeResponse("<html>Sign in</html>")
    assert titles(sonarr_search.search(client, "")) == ["Sonarr returned an unexpected reply"]


def test_url_without_scheme_is_reported_instead_of_crashing(client, session):
    session.responses["/api/v3/series"] = requests.exceptions.MissingSchema("No scheme supplied")
    assert titles(sonarr_search.search(client, "")) == ["Connection Error"]


def test_lookup_error_is_reported_instead_of_crashing(client, session):
    session.responses["/api/v3/series/lookup"] = FakeResponse({"message": "TVDB is down"}, status_code=503)
    assert titles(sonarr_search.search(client, "severance")) == ["Sonarr returned an error"]


def test_library_is_cached_between_queries(client, session):
    sonarr_search.search(client, "expanse")
    sonarr_search.search(client, "breaking")
    assert [call[0] for call in session.calls] == [f"{URL}/api/v3/series"]


def test_client_is_built_from_settings(settings):
    client = sonarr_search.sonarr()
    assert (client.url, client.api_key) == (URL, API_KEY)
    settings["url"] = ""
    assert sonarr_search.sonarr().url == sonarr_search.DEFAULT_URL


def test_trailing_slash_and_whitespace_are_trimmed_from_settings(settings):
    settings.update(url=" http://localhost:8989/ ", api_key=f" {API_KEY}\n")
    client = sonarr_search.sonarr()
    assert (client.url, client.api_key) == ("http://localhost:8989", API_KEY)


def test_query_method_returns_results_to_flow_launcher(client, monkeypatch):
    monkeypatch.setattr(sonarr_search, "sonarr", lambda: client)
    response = asyncio.run(sonarr_search.plugin._event_handler.trigger_event("query", "expanse"))
    assert [result["Title"] for result in response["Result"]] == ["The Expanse"]
