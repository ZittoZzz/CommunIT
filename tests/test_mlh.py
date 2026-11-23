"""Synthetic MLH markup: calendar-only discovery through the normal collector."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.collect import collect
from backend.db import connect, events, source_states
from backend.extract import extract
from backend.mlh import published_moment
from backend.network import FetchError, RateLimited
from backend.source_index import load_sources

ROOT = 'https://ghw.mlh.com/'
EDITION = ROOT + 'events/learning-week'
SIGNUP = 'https://events.mlh.com/events/42000-learning-week'
SOURCE = {'id': 'mlh-test', 'name': 'MLH test', 'kind': 'mlh', 'url': ROOT, 'window_days': 45}
NOW = datetime(2035, 11, 22, 13, tzinfo=timezone.utc)
CALENDAR = f'<title>Global Hack Week</title><p>Attend an upcoming Global Hack Week:</p><a href="{EDITION}">Learn more</a><a href="{EDITION}">Duplicate responsive card</a>'
EDITION_PAGE = f'<h1>Learning Week</h1><p>Global Hack Week is a 100% free event for anyone, anywhere!</p><a href="https://mlh.link/global-register">Register</a><a href="{SIGNUP}">Register</a>'
REGISTRATION = '''<h1 itemprop="name">Global Hack Week: Learning Week</h1>
<meta itemprop="startDate" content="2035-12-07 15:00:00 UTC">
<meta itemprop="endDate" content="2035-12-13 18:00:00 UTC">
<div itemprop="location" itemtype="https://schema.org/VirtualLocation">Event is hosted online</div>
<div itemprop="organizer"><meta itemprop="name" content="Major League Hacking"></div>
<div itemprop="description">Build technical projects and learn new skills.</div>
<div><h4>Who can attend?</h4><button class="option" disabled>Students - University</button><button class="option" disabled>Minors (Between 13-18)</button></div>
<label>I am either over 18 years of age or have a parent's permission to participate in this event.</label>
<a href="/events/42000-learning-week/register">Log In &amp; Register</a>'''


class Pages:
    def __init__(self, overrides=None):
        self.pages = {ROOT: CALENDAR, EDITION: EDITION_PAGE, SIGNUP: REGISTRATION}
        self.pages.update(overrides or {})
        self.requests = []

    def public_page(self, url, allowed_hosts=None):
        self.requests.append(url)
        value = self.pages[url]  # Any unobserved link fails; there is no network.
        if isinstance(value, Exception):
            raise value
        return value.encode()


def run(pages=None, db=None, at=NOW):
    db = db or connect(':memory:')
    report = collect(db, [SOURCE], client=pages or Pages(), now=at)
    return db, report


def test_calendar_only_collector_trace_and_independent_fields():
    pages = Pages()
    db, report = run(pages)
    assert pages.requests == [ROOT, EDITION, SIGNUP]
    source, = report['sources']
    assert source['status'] == 'ok' and source['discovered'] == source['accepted'] == 1
    event, = events(db, NOW)
    assert event['name'] == 'Global Hack Week: Learning Week'
    assert event['geography'] == 'international_online' and event['topic'] == 'general_it'
    assert event['section'] == 'upcoming' and event['registration_status'] == 'open'
    assert event['organizer'] == 'Major League Hacking' and event['organizer_event_url'] == EDITION
    assert event['registration_url'] == SIGNUP and event['account_required'] is True
    assert 'Students - University' in event['eligibility'] and 'parent’s permission' in event['eligibility']
    assert event['price'] == {'kind': 'free', 'amount': 0}
    assert event['start']['value'] == '2035-12-07T23:00:00+08:00'
    assert event['end']['value'] == '2035-12-14T02:00:00+08:00'
    assert event['announcements'][0]['discovery_path'] == [ROOT, EDITION, SIGNUP]
    payload = json.loads(db.execute('SELECT payload FROM announcements').fetchone()[0])
    assert payload['facts']['deadline'] is payload['facts']['submission_deadline'] is None
    assert payload['posted_at'] is None
    for field in ('organizer', 'start', 'end', 'eligibility', 'price', 'registration_state', 'account_required'):
        assert payload['field_evidence'][field]['url'] in (EDITION, SIGNUP)
        assert payload['field_evidence'][field]['quote']
    db.close()


def test_saved_response_replay_keeps_one_edition_and_first_seen():
    db, first = run()
    before = events(db, NOW)[0]
    _, second = run(Pages(), db, NOW + timedelta(hours=1))
    after = events(db, NOW)[0]
    assert first['events'] == second['events'] == 1
    assert first['announcements'] == second['announcements'] == 1
    assert second['sources'][0]['new_announcements'] == 0
    assert before['id'] == after['id'] and before['first_seen'] == after['first_seen']
    assert before['announcements'][0]['first_seen'] == after['announcements'][0]['first_seen']
    assert after['announcements'][0]['revision_count'] == 1
    db.close()


@pytest.mark.parametrize('raw', ['2035-12-13 18:00:00 UTC', '2035-12-13T13:00:00-05:00'])
def test_published_end_time_rolls_over_to_next_manila_day(raw):
    assert published_moment(raw) == {'raw': raw, 'value': '2035-12-14T02:00:00+08:00',
                                      'precision': 'datetime', 'timezone': 'Asia/Manila'}


def test_date_only_is_not_converted_to_midnight_and_ambiguous_zone_stays_text():
    assert published_moment('2035-12-13')['precision'] == 'date'
    assert published_moment('2035-12-13')['value'] == '2035-12-13'
    assert published_moment('December 13, 2035 at 13:00 PST')['precision'] == 'text'


@pytest.mark.parametrize('change,expected,accepted', [
    ({ROOT: FetchError('HTTP 403')}, 'blocked', 0),
    ({ROOT: RateLimited(60)}, 'rate_limited', 0),
    ({ROOT: '<title>Global Hack Week</title><p>Attend an upcoming Global Hack Week:</p>'}, 'ok', 0),
    ({ROOT: '<title>Challenge required</title>'}, 'error', 0),
    ({SIGNUP: FetchError('HTTP 403')}, 'partial', 0),
    ({SIGNUP: FetchError('ReadTimeout')}, 'partial', 0),
    ({SIGNUP: '<h1>Unreadable</h1>'}, 'partial', 0),
])
def test_blocked_unreadable_and_successful_empty_are_distinct(change, expected, accepted):
    db, report = run(Pages(change))
    source, = report['sources']
    assert source['status'] == expected and source['accepted'] == accepted
    if expected == 'partial':
        assert source['decisions'][0]['unverified'] is True
    if expected == 'ok':
        assert source['discovered'] == 0 and source_states(db)[0]['last_success']
    if expected == 'blocked':
        assert source['route_checks'][0]['status'] == 'blocked'
        assert source_states(db)[0]['last_success'] is None
    db.close()


@pytest.mark.parametrize('start,accepted', [
    (NOW, 1), (NOW + timedelta(days=45), 0), (NOW - timedelta(days=1), 0),
])
def test_half_open_pilot_window_uses_start_not_event_end(start, accepted):
    page = REGISTRATION.replace('2035-12-07 15:00:00 UTC', start.strftime('%Y-%m-%d %H:%M:%S UTC'))
    page = page.replace('2035-12-13 18:00:00 UTC', (start + timedelta(days=6)).strftime('%Y-%m-%d %H:%M:%S UTC'))
    db, report = run(Pages({SIGNUP: page}))
    assert report['sources'][0]['status'] == 'ok'
    assert report['sources'][0]['accepted'] == accepted
    db.close()


def test_free_and_account_requirement_are_not_assumed_without_evidence():
    edition = EDITION_PAGE.replace('Global Hack Week is a 100% free event for anyone, anywhere!', 'Global Hack Week is for anyone, anywhere!')
    page = REGISTRATION.replace('Log In &amp; Register', 'Register')
    db, _ = run(Pages({EDITION: edition, SIGNUP: page}))
    event, = events(db, NOW)
    assert event['price'] == {'kind': 'unknown'}
    assert event.get('account_required') is None
    db.close()


def test_signup_specific_price_overrides_general_free_copy():
    db, _ = run(Pages({SIGNUP: REGISTRATION + '<meta itemprop="price" content="25.00"><meta itemprop="priceCurrency" content="USD">'}))
    assert events(db, NOW)[0]['price'] == {'kind': 'paid', 'amount': 25, 'currency': 'USD'}
    db.close()


@pytest.mark.parametrize('change', [
    lambda s: s.replace('Log In &amp; Register', 'Log In'),
    lambda s: s.replace('href="/events/42000-learning-week/register"', 'aria-disabled="true" href="/events/42000-learning-week/register"'),
])
def test_generic_login_or_disabled_control_is_not_open_registration(change):
    db, _ = run(Pages({SIGNUP: change(REGISTRATION)}))
    assert events(db, NOW)[0]['registration_status'] == 'unknown'
    db.close()


def test_distinct_same_year_editions_do_not_merge():
    second_edition, second_signup = ROOT + 'events/another-week', SIGNUP.replace('42000', '42001')
    pages = Pages({ROOT: CALENDAR + f'<a href="{second_edition}">Another edition</a>',
                   second_edition: EDITION_PAGE.replace(SIGNUP, second_signup),
                   second_signup: REGISTRATION.replace('42000', '42001')})
    db, report = run(pages)
    assert report['events'] == report['announcements'] == 2
    assert len({e['id'] for e in events(db, NOW)}) == 2
    db.close()


def test_untrusted_links_and_unrelated_signup_are_not_followed_or_accepted():
    pages = Pages({ROOT: CALENDAR + '<a href="https://elsewhere.example/events/untrusted">Learn more</a>',
                   SIGNUP: REGISTRATION.replace('content="Major League Hacking"', 'content="Someone else"')})
    db, report = run(pages)
    assert pages.requests == [ROOT, EDITION, SIGNUP]
    assert report['sources'][0]['status'] == 'partial' and report['events'] == 0
    db.close()


def test_generic_ctf_gate_is_unchanged_and_runtime_source_contains_only_calendar():
    source = next(s for s in load_sources('sources.json') if s['kind'] == 'mlh')
    assert source['url'] == ROOT
    encoded = json.dumps(source)
    assert '/events/' not in encoded and 'Learning Week' not in encoded
    assert extract('Global Hack Week 2035', 'Learn new skills online.', ROOT,
                   {'organizer':'Major League Hacking', 'organizer_key':'mlh'}) is None


def test_hosted_by_block_without_organization_metadata_is_still_primary_evidence():
    page = REGISTRATION.replace('<div itemprop="organizer"><meta itemprop="name" content="Major League Hacking"></div>',
                                '<div><h4>Hosted by</h4><div><div>Major League Hacking</div></div></div>')
    db, report = run(Pages({SIGNUP: page}))
    assert report['sources'][0]['status'] == 'ok'
    assert events(db, NOW)[0]['organizer'] == 'Major League Hacking'
    db.close()


def test_conflicting_date_metadata_is_unverified_not_a_successful_zero():
    db, report = run(Pages({SIGNUP: REGISTRATION + '<meta itemprop="startDate" content="2035-11-04 15:00:00 UTC">'}))
    source, = report['sources']
    assert source['status'] == 'partial' and source['decisions'][0]['unverified']
    assert 'Conflicting' in source['decisions'][0]['reason']
    assert report['events'] == 0
    db.close()
