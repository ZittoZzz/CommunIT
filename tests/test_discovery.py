"""Offline discovery regressions; all institutions, events and IDs are fictional.

These examples are never imported by the collector or used by a live run.
"""
import json
from copy import deepcopy
from datetime import datetime, timezone
from html import escape

import pytest

from backend.adapters import article_parts, brave, html, rss
from backend.app import create_app
from backend.collect import collect
from backend.db import connect, events, ingest, register_sources, source_states
from backend.domain import canonical_url, facebook_post, parse_date_range
from backend.extract import extract
from backend.network import FetchError


NOW = datetime(2031, 2, 10, tzinfo=timezone.utc)
FEED = 'https://kestrel.example/news/feed/'
ARTICLE = 'https://kestrel.example/news/student-technology/'
POST = 'https://www.facebook.com/story.php?story_fbid=707070&id=808080'
SOURCE = {
    'id': 'fictional-university', 'name': 'Fictional university feed', 'kind': 'rss',
    'url': FEED, 'organizer': 'Kestrel University', 'organizer_key': 'kestrel-university',
    'allowed_hosts': ['kestrel.example'], 'follow_articles': True,
    'article_selector': 'main', 'exclude_selector': '.related-news',
    'scope_pattern': r'(?:organized|hosted)\s+by\s+Kestrel University',
}


def feed(title='Student technology bulletin', description='Read the full announcement.', items=True):
    item = f'''<item><title>{escape(title)}</title><link>{ARTICLE}</link>
    <description>{escape(description)}</description><pubDate>Mon, 10 Feb 2031 03:00:00 GMT</pubDate></item>''' if items else ''
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>Campus news</title><link>https://kestrel.example/news/</link><description>Updates</description>{item}</channel></rss>'


def article(dates='April 12–15, 2031', eligibility='Kestrel University students', extra=''):
    return f'''<html><head><title>Campus news</title>
    <meta property="article:published_time" content="2031-02-10T03:00:00Z"></head><body>
    <main><h1>Student technology bulletin</h1><h2>Nebula CTF 2031</h2>
    <p>A Capture the Flag competition hosted by Kestrel University.</p>
    <p>Competition dates: {dates}</p><p>Eligibility: {eligibility}</p>
    <p>Format: online</p><a href="{POST}">Organizer Facebook announcement</a>{extra}
    </main><footer><a href="https://facebook.com/unrelated/posts/909090">Unrelated post</a></footer>
    </body></html>'''


class Pages:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def public_page(self, url, allowed=None):
        self.requests.append(url)
        result = self.pages[url]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def db():
    connection = connect(':memory:')
    yield connection
    connection.close()


def test_new_feed_entry_follows_article_and_discovers_post_without_fetching_it_twice(db):
    client = Pages({FEED: feed(), ARTICLE: article()})
    first = collect(db, [SOURCE], client=client, now=NOW)
    saved = events(db, NOW)[0]
    second = collect(db, [SOURCE], client=client, now=NOW)
    assert (first['events'], second['events'], second['announcements']) == (1, 1, 1)
    assert second['sources'][0]['new_announcements'] == 0
    assert db.execute('SELECT count(*) FROM revisions').fetchone()[0] == 1
    assert events(db, NOW)[0]['first_seen'] == saved['first_seen']
    assert saved['name'] == 'Nebula CTF 2031'
    assert saved['registration_status'] == 'unknown'
    announcement = saved['announcements'][0]
    assert announcement['discovery_path'] == [FEED, ARTICLE]
    assert announcement['related_links'] == [{
        'url': canonical_url(POST), 'label': 'Organizer Facebook announcement',
        'access': 'linked_only', 'discovered_on': ARTICLE,
    }]
    assert client.requests == [FEED, ARTICLE, FEED, ARTICLE]


def test_announcement_index_discovers_article_links_and_preserves_path(db):
    index = 'https://kestrel.example/news/'
    source = {**SOURCE, 'kind': 'html', 'url': index, 'link_pattern': '/news/'}
    client = Pages({index: f'<main><h1>News</h1><a href="{ARTICLE}">Student technology bulletin</a></main>', ARTICLE: article()})
    report = collect(db, [source], client=client, now=NOW)
    assert report['events'] == 1 and report['announcements'] == 1
    assert events(db, NOW)[0]['announcements'][0]['discovery_path'] == [index, ARTICLE]


def test_retained_article_is_rechecked_after_leaving_feed_and_edit_keeps_identity(db):
    client = Pages({FEED: feed(), ARTICLE: article()})
    collect(db, [SOURCE], client=client, now=NOW)
    initial = events(db, NOW)[0]
    client.pages = {FEED: feed(items=False), ARTICLE: article('April 19–22, 2031', 'All Philippine college students')}
    report = collect(db, [SOURCE], client=client, now=NOW)
    current = events(db, NOW)[0]
    assert report['events'] == report['announcements'] == 1
    assert current['id'] == initial['id']
    assert current['start']['value'] == '2031-04-19'
    assert current['eligibility'] == 'All Philippine college students'
    assert current['field_evidence']['eligibility'] == {
        'url': ARTICLE, 'quote': 'Eligibility: All Philippine college students',
    }
    assert current['announcements'][0]['revision_count'] == 2


def test_failed_article_refresh_cannot_replace_full_record_with_feed_excerpt(db):
    client = Pages({FEED: feed(), ARTICLE: article()})
    collect(db, [SOURCE], client=client, now=NOW)
    before = events(db, NOW)[0]
    # The feed remains readable and recognizable, but has no schedule or links.
    client.pages = {FEED: feed('Nebula CTF 2031', 'Hosted by Kestrel University.'), ARTICLE: FetchError('HTTP 503')}
    report = collect(db, [SOURCE], client=client, now=NOW)
    after = events(db, NOW)[0]
    assert report['sources'][0]['status'] == 'partial'
    for field in ('start', 'end', 'eligibility', 'field_evidence', 'announcements'):
        assert after[field] == before[field]


def test_failed_feed_keeps_records_and_last_success(db):
    client = Pages({FEED: feed(), ARTICLE: article()})
    collect(db, [SOURCE], client=client, now=NOW)
    before = events(db, NOW)
    last_success = source_states(db)[0]['last_success']
    client.pages[FEED] = FetchError('HTTP 503')
    report = collect(db, [SOURCE], client=client, now=NOW)
    assert report['sources'][0]['status'] == 'error'
    after = events(db, NOW)
    assert after[0]['review']['required']
    assert 'source checks could not complete' in ' '.join(after[0]['review']['reasons'])
    assert [{k: v for k, v in event.items() if k != 'review'} for event in after] == [
        {k: v for k, v in event.items() if k != 'review'} for event in before]
    assert source_states(db)[0]['last_success'] == last_success


def test_footer_and_sidebar_links_are_not_evidence_of_linked_event_posts():
    extra = '''<footer><a href="https://facebook.com/footer/posts/111111">Footer post</a></footer>
    <aside class="related-news"><a href="https://facebook.com/sidebar/posts/222222">Other event</a></aside>
    <a href="https://facebook.com/kestrel">Our Facebook profile</a>'''
    result = rss(SOURCE, Pages({FEED: feed(), ARTICLE: article(extra=extra)}), [], NOW)
    links = result.announcements[0]['related_links']
    assert [link['url'] for link in links] == [canonical_url(POST)]


def test_footer_heading_does_not_turn_generic_page_into_event():
    raw = '''<main><h1>Student bulletin</h1><p>Hosted by Kestrel University.</p>
    <footer><h2>Archived Nebula CTF 2031</h2></footer></main>'''
    result = rss(SOURCE, Pages({FEED: feed(), ARTICLE: raw}), [], NOW)
    assert result.announcements == []


def test_semantic_article_header_keeps_event_title_without_site_header_links():
    raw = '''<html><head><title>University news</title></head><body>
    <header><h1>University home</h1><a href="https://facebook.com/site/posts/111111">Site social link</a></header>
    <main><article><header><h1>Nebula CTF 2031</h1></header>
    <p>A Capture the Flag competition hosted by Kestrel University.</p>
    <p>Competition dates: April 12–15, 2031</p></article></main></body></html>'''
    result = rss(SOURCE, Pages({FEED: feed(), ARTICLE: raw}), [], NOW)
    assert len(result.announcements) == 1
    assert result.announcements[0]['facts']['name'] == 'Nebula CTF 2031'
    assert result.announcements[0]['facts']['start']['value'] == '2031-04-12'
    assert result.announcements[0]['related_links'] == []


def test_multiple_event_headings_on_generic_page_remain_ambiguous():
    raw = '''<main><h1>Student bulletin</h1><p>Hosted by Kestrel University.</p>
    <h2>Nebula CTF 2031</h2><h2>Orion CTF 2031</h2></main>'''
    _, title, _, _ = article_parts(raw, ARTICLE, SOURCE)
    assert title == 'Student bulletin'
    assert rss(SOURCE, Pages({FEED: feed(), ARTICLE: raw}), [], NOW).announcements == []


def test_evergreen_ctf_heading_does_not_borrow_year_from_unrelated_news():
    raw = '''<main><h1>Campus activities</h1>
    <p>Our annual lecture series in 2031 is hosted by Kestrel University.</p>
    <h3>Capture the Flag challenges</h3><p>Our club enjoys solving these puzzles.</p></main>'''
    _, title, _, _ = article_parts(raw, ARTICLE, SOURCE)
    assert title == 'Campus activities'
    assert rss(SOURCE, Pages({FEED: feed(), ARTICLE: raw}), [], NOW).announcements == []


def test_structured_event_dates_have_their_own_source_evidence():
    source = {**SOURCE, 'kind': 'html', 'url': ARTICLE}
    schema = {'@type': 'Event', 'name': 'Nebula CTF 2031', 'url': ARTICLE,
              'description': 'Hosted by Kestrel University.',
              'startDate': '2031-04-12', 'endDate': '2031-04-15'}
    raw = f'<html><head><script type="application/ld+json">{json.dumps(schema)}</script></head><main><h1>Campus calendar</h1></main></html>'
    result = html(source, Pages({ARTICLE: raw}), [], NOW)
    assert len(result.announcements) == 1
    ann = result.announcements[0]
    for field, expected in (('start', '2031-04-12'), ('end', '2031-04-15')):
        assert ann['facts'][field]['value'] == expected
        assert ann['facts'][field]['precision'] == 'date'
        assert ann['field_evidence'][field]['url'] == ARTICLE
        assert expected in ann['field_evidence'][field]['quote']


def test_university_student_participation_does_not_make_foreign_ctf_in_scope():
    title = 'Nebula CTF 2031'
    foreign = 'Kestrel University students may join this global online CTF hosted by Boreal Institute overseas.'
    assert extract(title, foreign, ARTICLE, SOURCE) is None
    local = 'An online CTF hosted by Kestrel University.'
    assert extract(title, local, ARTICLE, SOURCE) is not None


def test_search_accepts_configured_numeric_owner_alias_but_not_another_owner(monkeypatch):
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY', 'test-only-key')
    monkeypatch.setenv('BRAVE_STORAGE_RIGHTS', '1')
    target = {'account': 'kestrelclub', 'account_aliases': ['808080'], 'organizer': 'Kestrel University',
              'organizer_key': 'kestrel-university', 'query': 'site:facebook.com/kestrelclub/ CTF'}
    source = {'url': 'https://api.search.brave.com/res/v1/web/search', 'targets': [target]}

    class Search:
        def read(self, url, **kwargs):
            assert kwargs['headers']['X-Subscription-Token'] == 'test-only-key'
            return json.dumps({'web': {'results': [
                {'title': 'Nebula CTF 2031', 'url': POST, 'description': 'Registration open; May 6–8.'},
                {'title': 'Nebula CTF 2031', 'url': POST.replace('808080', '999999')},
                {'title': 'Nebula CTF 2031', 'url': 'https://facebook.com/kestrelclub'},
            ]}})

    found = brave(source, Search(), [], NOW).announcements
    assert len(found) == 1
    assert found[0]['url'] == canonical_url(POST)
    assert found[0]['access'] == 'search_only'
    assert found[0]['facts']['start'] is None
    assert found[0]['facts']['registration_state'] is None
    assert found[0]['facts']['eligibility'] is None


@pytest.mark.parametrize('url,account,post', [
    ('https://facebook.com/story.php?id=808080&story_fbid=707070', '808080', '707070'),
    ('https://m.facebook.com/permalink.php?story_fbid=707070&id=808080', '808080', '707070'),
    ('https://www.facebook.com/kestrelclub/posts/707070/', 'kestrelclub', '707070'),
    ('https://facebook.com/kestrelclub/photos/a.606060/707070/', 'kestrelclub', '707070'),
    ('https://facebook.com/photo.php?fbid=707070', None, '707070'),
])
def test_facebook_post_link_shapes(url, account, post):
    identified = facebook_post(url)
    assert identified['account'] == account and identified['post'] == post
    assert facebook_post('https://facebook.com/kestrelclub') is None
    assert facebook_post('https://facebook.com.evil.example/kestrelclub/posts/707070') is None


def test_confirmed_date_range_preserves_dates_without_inventing_clock_times():
    ann = extract('Nebula CTF 2031', 'Hosted by Kestrel University.\nCompetition dates: April 12–15, 2031', ARTICLE, SOURCE)
    assert (ann['facts']['start']['value'], ann['facts']['end']['value']) == ('2031-04-12', '2031-04-15')
    for field in ('start', 'end'):
        assert ann['facts'][field]['precision'] == 'date'
        assert ann['facts'][field]['timezone'] is None
        assert 'T' not in ann['facts'][field]['value']
        assert ann['field_evidence'][field] == {'url': ARTICLE, 'quote': 'Competition dates: April 12–15, 2031'}


def test_missing_date_year_is_not_borrowed_from_post_or_event_title():
    ann = extract('Nebula CTF 2031', 'Hosted by Kestrel University.\nCompetition dates: April 12–15', ARTICLE, SOURCE,
                  posted_at='2031-02-10T03:00:00Z')
    assert ann['facts']['start'] == {'raw': 'April 12–15', 'value': None, 'precision': 'text', 'timezone': None}
    assert ann['facts']['end'] is None
    assert ann['facts']['registration_state'] is None
    assert ann['facts']['eligibility'] is None
    assert parse_date_range('April 15–12, 2031') is None
    assert parse_date_range('February 30–31, 2031') is None


def test_api_provenance_tracks_selected_fact_and_clears_superseded_evidence(tmp_path):
    path = str(tmp_path / 'fictional.sqlite3')
    db = connect(path)
    register_sources(db, [SOURCE])
    ann = extract('Nebula CTF 2031', 'Hosted by Kestrel University.\nCompetition dates: April 12–15, 2031', ARTICLE, SOURCE,
                  posted_at='2031-02-10T03:00:00Z')
    ann['related_links'] = [{'url': canonical_url(POST), 'label': 'Facebook announcement', 'access': 'linked_only', 'discovered_on': ARTICLE}]
    ann['discovery_path'] = [FEED, ARTICLE]
    ingest(db, SOURCE['id'], ann, '2031-02-10T04:00:00Z')
    db.commit()
    app = create_app(path).test_client()
    record = app.get('/api/events').json['events'][0]
    assert record['field_evidence']['start']['url'] == ARTICLE
    assert len(record['announcements']) == 1
    assert record['announcements'][0]['related_links'] == ann['related_links']
    assert record['announcements'][0]['discovery_path'] == [FEED, ARTICLE]
    newer = deepcopy(ann)
    newer['url'] = ARTICLE + 'correction'
    newer['posted_at'] = '2031-02-11T03:00:00Z'
    newer['field_evidence'].pop('start')
    newer['facts']['start'] = {'raw': 'April 13, 2031', 'value': '2031-04-13', 'precision': 'date', 'timezone': None}
    ingest(db, SOURCE['id'], newer, '2031-02-11T04:00:00Z')
    db.commit()
    corrected = app.get('/api/events').json['events'][0]
    assert corrected['start']['value'] == '2031-04-13'
    assert 'start' not in corrected['field_evidence']
    newer['facts']['lifecycle'] = 'postponed'
    newer['field_evidence']['lifecycle'] = {'url': newer['url'], 'quote': 'The competition is postponed.'}
    ingest(db, SOURCE['id'], newer, '2031-02-12T04:00:00Z')
    db.commit()
    postponed = app.get('/api/events').json['events'][0]
    assert postponed['start'] is postponed['end'] is None
    assert 'end' not in postponed['field_evidence']
    assert postponed['field_evidence']['lifecycle']['url'] == newer['url']
    db.close()
