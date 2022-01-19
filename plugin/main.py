import webbrowser
import json

from flox import Flox, utils, ICON_BROWSER, ICON_SETTINGS
from pyarr import SonarrAPI

CACHE_DIR = 'Sonarr-Search'
UNAUTHORIZED = {'error': 'Unauthorized'}


@utils.cache('sonarr_series.json', max_age=300)
def get_sonarr_series(sonarr):
    shows = sonarr.get_series()
    if shows == UNAUTHORIZED:
        utils.remove_cache('sonarr_series.json')
        return []
    return shows

@utils.cache('sonarr_new_series.json', max_age=3)
def get_sonarr_new_series(sonarr, query):
    return sonarr.lookup_series(query)

@utils.cache('sonarr_episodes.json', max_age=300)
def get_episodes_by_id(sonarr, series_id):
    return sonarr.get_episodes_by_series_id(series_id)

def format_subtitle(text):
    return text.replace('\r\n', ' ').replace('\n', ' ')

class SonarrSearch(Flox):

    def init_api(self):
        self.url, self.api_key = self.settings.get('url'), self.settings.get('api_key')
        self.sr = SonarrAPI(self.url, self.api_key)

    def query(self, query):
        self.init_api()
        if self.api_key == "":
            self.add_item(
                title='Please set your API key',
                subtitle=f'Plugins > {self.name} > API Key',
                icon=ICON_SETTINGS,
                method=self.open_setting_dialog
            )
            return
        with utils.ThreadPoolExecutor(max_workers=10) as executor:
            self.series_results(query, executor)
            if len(self._results) == 0:
                self.new_series(query, executor)

    def series_results(self, query, executor):
        shows = get_sonarr_series(self.sr)
        if shows == []:
            self.add_item(
                title='Unauthorized or No shows found!',
                subtitle='Please check your API key.',
                icon=ICON_SETTINGS,
                method=self.open_setting_dialog
            )
            return
        for show in shows:
            if query.lower() in show['title'].lower():
                try:
                    icon = self.url + show['images'][1]['url']
                except IndexError:
                    icon = self.icon
                self.add_item(
                    title=show['title'],
                    subtitle=format_subtitle(show['overview']),
                    icon=str(utils.get_icon(icon, self.name, show['titleSlug'] + '.jpg')),
                    context=show,
                    method=self.open_show,
                    parameters=[self.url, show['titleSlug']],
                )

    def new_series(self, query, executor):
        new_shows = self.sr.lookup_series(query)
        for show in new_shows:
            try:
                icon = show['images'][1]['url']
            except (IndexError, KeyError):
                icon = self.icon
            try:
                overview = show['overview']
            except KeyError:
                overview = '...'
            self.add_item(
                title=show['title'],
                subtitle=format_subtitle(overview),
                icon=str(utils.get_icon(executor, icon, self.name, show['titleSlug'] + '.jpg')),
                method=self.add_new,
                parameters=[self.url, show['tvdbId']],
            )

    def context_menu(self, data):
        show = data
        url = self.settings['url']
        self.add_item(
            title='Open in browser',
            icon=ICON_BROWSER,
            method=self.open_show,
            parameters=[url, show['titleSlug']],
        )

    def open_activity(self):
        url = self.settings['url']
        webbrowser.open(f"{url}/activity/queue")

    def open_show(self, url, titleSlug):
        webbrowser.open(f'{url}/series/{titleSlug}')

    def add_new(self, url, id):
        url = f'{url}/add/new?term=tvdb:{id}'
        webbrowser.open(url)


if __name__ == "__main__":
    SonarrSearch()
