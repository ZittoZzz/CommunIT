"""Fictional publisher fixtures; never imported by the live collector."""
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from bs4 import BeautifulSoup

from backend.adapters import article_parts, html, posted_from_html, rss
from backend.collect import collect
from backend.db import connect, events
from backend.extract import extract
from backend.network import FetchError
from backend.domain import publisher_url
from backend.tavily import search_announcement

NOW = datetime(2032, 3, 2, tzinfo=timezone.utc)
FEED = 'https://campus.example/feed/?s=capture+the+flag'
PAGE = 'https://campus.example/invitations/student-challenge'
SOURCE = {'id': 'campus', 'name': 'Campus publisher', 'kind': 'rss', 'url': FEED,
          'publisher_role': 'resharer', 'body_identity': True, 'content_complete': True}
TITLE = 'Student Skills Challenge'
BODY = '''A Capture the Flag (CTF) tournament for students.
Pre-tournament workshops ran in 2031.
Event Details:
Date:
May 16, 2032
Venue:
Technology Hall, Makati City
Respectfully yours,
The Kestrel Security Team'''


class Pages:
    def __init__(self, pages):
        self.pages, self.requests = pages, []

    def public_page(self, url, allowed_hosts=None):
        self.requests.append(url)
        raw = self.pages[url]
        if isinstance(raw, Exception):
            raise raw
        return raw


def feed(body=BODY, title=TITLE):
    return f'''<rss version="2.0"><channel><title>Announcements</title>
    <item><title>{escape(title)}</title><link>{PAGE}</link>
    <pubDate>Mon, 01 Mar 2032 04:00:00 GMT</pubDate>
    <description>{escape(body)}</description></item></channel></rss>'''


def test_body_identifies_ctf_without_title_keyword_and_does_not_borrow_workshop_year():
    result = rss(SOURCE, Pages({FEED: feed()}), [], NOW)
    ann = result.announcements[0]
    assert ann['identity']['edition'] == '2032'
    assert ann['facts']['organizer'] == 'Kestrel Security'
    assert ann['publisher']['name'] == 'Campus publisher'
    assert ann['relationship'] == 'reshare' and ann['official'] is False
    assert ann['facts']['registration_state'] is None
    assert ann['facts']['start'] is None
    assert 'May 16, 2032' in ann['field_evidence']['edition']['quote']
    assert 'May 16, 2032' in ann['facts']['summary']
    assert ann['discovery_path'] == [FEED, PAGE]


def test_publication_year_is_not_an_event_edition():
    body = BODY.replace('Event Details:\nDate:\nMay 16, 2032\n', '')
    assert rss(SOURCE, Pages({FEED: feed(body)}), [], NOW).announcements == []


def test_workshop_or_topic_is_not_a_competition():
    for body in [BODY.replace('tournament', 'workshop'), BODY.replace('tournament', 'tutorial')]:
        assert rss(SOURCE, Pages({FEED: feed(body)}), [], NOW).announcements == []


def test_foreign_ctf_shared_by_local_university_is_not_philippine():
    body = BODY.replace('Technology Hall, Makati City', 'Technology Hall, London')
    body += '\nStudents living in Manila may also participate online.'
    assert rss(SOURCE, Pages({FEED: feed(body)}), [], NOW).announcements == []


def test_unknown_organizer_is_not_replaced_by_publisher():
    body = BODY.replace('Respectfully yours,\nThe Kestrel Security Team', 'Join us.')
    ann = rss(SOURCE, Pages({FEED: feed(body)}), [], NOW).announcements[0]
    assert ann['facts']['organizer'] == 'Organizer not confirmed'
    assert 'organizer' not in ann['field_evidence']


def test_complete_feed_rechecks_edits_and_retains_first_seen_without_duplicate():
    db = connect(':memory:')
    client = Pages({FEED: feed()})
    first = collect(db, [SOURCE], client=client, now=NOW)
    seen = events(db, NOW)[0]['first_seen']
    client.pages[FEED] = feed(BODY + '\nRegistration deadline: May 1, 2032 5:00 PM PHT')
    second = collect(db, [SOURCE], client=client, now=NOW)
    record = events(db, NOW)[0]
    assert first['events'] == second['events'] == second['announcements'] == 1
    assert second['sources'][0]['new_announcements'] == 0
    assert record['first_seen'] == seen
    assert record['deadline']['value'].startswith('2032-05-01')
    assert client.requests == [FEED, FEED]
    assert db.execute('select count(*) from revisions').fetchone()[0] == 2
    client.pages[FEED] = FetchError('HTTP 503')
    failed = collect(db, [SOURCE], client=client, now=NOW)
    assert failed['sources'][0]['status'] == 'error'
    after = events(db, NOW)[0]
    assert after['review']['required']
    assert {k: v for k, v in after.items() if k != 'review'} == {k: v for k, v in record.items() if k != 'review'}
    db.close()


def test_winner_recap_cannot_turn_old_register_now_text_into_open_registration():
    ann = extract('Student Skills CTF 2032 winners', BODY + '\nRegister now!', PAGE, SOURCE)
    assert ann['kind'] == 'recap'
    assert ann['facts']['registration_state'] == 'closed'


def test_feed_embed_is_link_evidence_without_facebook_fetch():
    post = 'https://www.facebook.com/fictionalclub/posts/pfbidFictionalExample'
    embed = 'https://www.facebook.com/plugins/post.php?href=' + quote(post, safe='')
    body = BODY.replace('\n', '<br>') + f'<iframe src="{embed}"></iframe>'
    body += '<footer><a href="https://facebook.com/footer/posts/999999">Footer</a></footer>'
    client = Pages({FEED: feed(body)})
    ann = rss(SOURCE, client, [], NOW).announcements[0]
    assert [p['url'] for p in ann['related_links']] == [post]
    assert ann['related_links'][0]['access'] == 'linked_only'
    assert client.requests == [FEED]


def test_index_body_does_not_create_event_and_titleless_article_can_be_followed():
    index = 'https://campus.example/announcements/'
    source = {**SOURCE, 'kind': 'html', 'url': index, 'index_only': True,
              'article_selector': '.invitation', 'link_pattern': '/invitations/'}
    raw = '<title>Student Skills Challenge</title><div class="invitation">' + BODY.replace('\n', '<br>') + '</div>'
    client = Pages({index: f'<title>Campus archive</title><a href="{PAGE}">Student Skills Challenge</a>', PAGE: raw})
    result = html(source, client, [], NOW)
    assert len(result.announcements) == 1
    assert result.announcements[0]['url'] == PAGE
    assert result.decisions[0]['reason'] == 'Archive index'


def test_calendar_event_time_is_not_publication_time():
    soup = BeautifulSoup('<time datetime="2032-05-16">Event date</time>', 'html.parser')
    assert posted_from_html(soup) is None
    soup = BeautifulSoup('<time itemprop="datePublished" datetime="2032-03-02">Posted</time>', 'html.parser')
    assert posted_from_html(soup) == '2032-03-02'


def test_conference_ctf_component_does_not_inherit_tickets_registration_status():
    source = {'id': 'community', 'name': 'Community', 'kind': 'html', 'url': PAGE,
              'organizer': 'Kestrel Security', 'organizer_key': 'kestrel',
              'article_selector': 'main', 'ctf_component_heading': True,
              'title_from_metadata': True, 'link_pattern': '(?!)'}
    raw = '''<meta property="og:title" content="Student Conference 2032">
    <main><h1>Student Conference 2032</h1><time datetime="2032-05-16">May 16</time>
    <h3>Capture The Flag</h3><p>12:00–15:00</p>
    <a href="https://tickets.example/conference">Conference tickets</a></main>'''
    # A bare agenda heading cannot turn the whole conference into a CTF.
    assert html(source, Pages({PAGE: raw}), [], NOW).announcements == []
    raw = raw.replace('<p>12:00–15:00</p>',
                      '<p>A Capture the Flag competition for teams. 12:00–15:00</p>')
    ann = html(source, Pages({PAGE: raw}), [], NOW).announcements[0]
    assert ann['title'] == 'Student Conference 2032'
    assert ann['posted_at'] is None
    assert ann['facts']['registration_state'] is ann['facts']['registration_url'] is None
    assert ann['facts']['start'] is ann['facts']['end'] is None


def test_published_calendar_body_excludes_draft_and_preserves_cancellation():
    source = {**SOURCE, 'kind': 'html', 'url': PAGE, 'index_only': False,
              'article_selector': '#event-info', 'title_from_metadata': True,
              'status_selector': '.alert', 'reject_text_pattern': 'still a draft', 'link_pattern': '(?!)'}
    raw = '<meta property="og:title" content="Student Skills Challenge"><div id="event-info">' + BODY.replace('\n', '<br>') + '</div>'
    assert html(source, Pages({PAGE: raw + '<div class="alert">This event is still a draft.</div>'}), [], NOW).announcements == []
    result = html(source, Pages({PAGE: raw + '<div class="alert">Event Cancelled</div>'}), [], NOW)
    assert result.announcements[0]['facts']['lifecycle'] == 'cancelled'


def test_exact_campus_eligibility_is_preserved_from_plain_text_feed():
    body = BODY + '\nOnly currently enrolled students of the Kestrel University are allowed to attend.'
    ann = rss(SOURCE, Pages({FEED: feed(body)}), [], NOW).announcements[0]
    assert 'Kestrel University' in ann['facts']['eligibility']
    assert ann['field_evidence']['eligibility']['url'] == PAGE


def test_verified_publisher_url_rule_unifies_search_and_full_article_without_losing_raw_path():
    from backend.db import ingest, register_sources
    raw_url = 'https://partner.example/event/student-competition'
    canonical = raw_url + '/'
    rules = {'hosts': ['partner.example'], 'path_prefixes': ['/event/'], 'trailing_slash': True}
    relationship = {'publisher_hosts': ['partner.example'], 'organizer': 'Kestrel',
                    'organizer_key': 'kestrel', 'event_pattern': r'Kestrel CTF', 'url_normalization': rules}
    source = {'id': 'partner', 'name': 'Partner', 'kind': 'html', 'url': 'https://partner.example/events/',
              'organizer': 'Kestrel', 'organizer_key': 'kestrel', 'url_normalization': rules}
    title = 'Kestrel CTF 2032'
    full = extract(title, 'Registration opens soon.', canonical, source)
    search, _ = search_announcement({'url': raw_url, 'title': title}, {'organizers': [relationship]})
    assert search['url'] == canonical
    assert search['discovery_path'][-1] == raw_url
    db = connect(':memory:')
    register_sources(db, [source, {'id': 'search', 'name': 'Search', 'kind': 'tavily', 'url': 'https://api.tavily.com/search'}])
    ingest(db, 'partner', full, NOW.isoformat())
    ingest(db, 'search', search, NOW.isoformat())
    assert db.execute('select count(*) from announcements').fetchone()[0] == 1
    assert events(db, NOW)[0]['announcements'][0]['access'] == 'full'
    db.close()
    for other in ['https://foreign.example/event/student-competition',
                  'https://partner.example/news/student-competition',
                  'https://partner.example/event/invitation.pdf']:
        assert publisher_url(other, rules) == other
