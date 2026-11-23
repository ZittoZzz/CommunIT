"""Synthetic directory and primary markup; no live URLs or reference fixtures."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.collect import collect
from backend.db import connect, events, source_states
from backend.network import FetchError, RateLimited


API = 'https://directory.example/api/v1/events/'
LISTING = 'https://directory.example/event/41000/'
PRIMARY = 'https://contest.example/'
NOW = datetime(2035, 11, 22, 13, tzinfo=timezone.utc)
SOURCE = {'id': 'ctftime', 'kind': 'ctftime', 'name': 'CTF directory', 'url': API,
          'lookback_days': 0, 'future_days': 45, 'include_international_online': True}
EVENT = {'id': 41000, 'ctf_id': 456, 'title': 'Comet CTF 2035',
         'url': PRIMARY, 'ctftime_url': LISTING,
         'organizers': [{'id': 7, 'name': 'Comet Team'}],
         'onsite': False, 'restrictions': 'Open',
         'start': '2035-12-04T18:00:00+00:00', 'finish': '2035-12-06T18:00:00+00:00'}
PAGE = '''<h1>Comet CTF 2035</h1><p>A jeopardy-style CTF with web and crypto challenges.</p>
<p>Comet CTF 2035 will run from Dec 4th 18:00 UTC until Dec 6th 18:00 UTC (48h).</p>
<h2>Rules</h2><p>You are allowed to play either individually or with a team.
When playing with a team, register and use a single account for the entire team.</p>
<a href="/archive/">Previous years</a>'''
FORM = '<form action="/register"><input type="email"><input type="password"><button>Register</button></form>'


class Pages:
    def __init__(self, page=PAGE, event=None, directory=None):
        self.page = page
        self.event = {**EVENT, **(event or {})}
        self.directory = directory
        self.requests = []

    def read(self, url, params=None):
        self.requests.append((url, params))
        if isinstance(self.directory, Exception):
            raise self.directory
        if self.directory is not None:
            return self.directory
        assert url in (API, API + str(self.event['id']) + '/')
        return json.dumps([self.event] if params else self.event).encode()

    def public_page(self, url, allowed_hosts=None):
        self.requests.append((url, None))
        assert url == PRIMARY and allowed_hosts == ['contest.example']
        if isinstance(self.page, Exception):
            raise self.page
        return self.page.encode()


def run(pages=None, db=None, source=None, now=NOW):
    db = db or connect(':memory:')
    return db, collect(db, [source or SOURCE], client=pages or Pages(), now=now)


def test_primary_verification_flows_through_collector_and_preserves_field_sources():
    pages = Pages()
    db, report = run(pages)
    state, = report['sources']
    assert state['status'] == 'ok' and state['discovered'] == state['accepted'] == 1
    assert [url for url, _ in pages.requests] == [API, API, PRIMARY]
    event, = events(db, NOW, window_days=45)
    assert event['geography'] == 'international_online' and event['topic'] == 'cybersecurity'
    assert event['section'] == 'watchlist' and event['registration_status'] == 'unknown'
    assert event['start']['value'] == '2035-12-05T02:00:00+08:00'
    assert event['end']['value'] == '2035-12-07T02:00:00+08:00'
    assert event['start']['precision'] == 'datetime' and event['start']['timezone'] == 'Asia/Manila'
    assert event['price'] == {'kind': 'unknown'} and event['registration_url'] is None
    assert event['deadline'] is event.get('submission_deadline') is event['registration_opens'] is None
    assert 'Philippine-specific eligibility terms are not stated' in event['eligibility']
    assert event['announcements'][0]['discovery_path'] == [API, LISTING, PRIMARY]
    proof = event['field_evidence']
    assert proof['organizer']['url'] == LISTING
    for field in ('name', 'start', 'end', 'eligibility', 'format', 'geography'):
        assert proof[field]['url'] == PRIMARY and proof[field]['quote']
    assert event['announcements'][0]['field_evidence']['edition']['url'] == PRIMARY
    assert proof['geography']['directory_url'] == LISTING
    assert 'registration_state' not in proof and 'price' not in proof
    assert event['posted_at'] is None
    db.close()


def test_legacy_ph_scope_remains_default_and_does_not_fetch_global_primary():
    pages = Pages()
    db, report = run(pages, source={k: v for k, v in SOURCE.items() if k != 'include_international_online'})
    assert report['events'] == 0
    assert all(url == API for url, _ in pages.requests)
    assert 'route_checks' not in report['sources'][0]
    db.close()


def test_opt_in_keeps_legacy_ph_organizer_metadata_without_primary_requirement():
    pages = Pages(page=FetchError('must not fetch'))
    db, report = run(pages, source={**SOURCE, 'organizer_names': ['Comet Team']})
    event, = events(db, NOW)
    assert report['sources'][0]['accepted'] == 1
    assert event['announcement_url'] == LISTING
    assert event['start']['value'] == EVENT['start']
    assert all(url == API for url, _ in pages.requests)
    db.close()


@pytest.mark.parametrize('page,reason,status', [
    (PAGE.replace('Comet CTF 2035</h1>', 'Comet CTF 2034</h1>'), 'exact directory edition', 'unverified'),
    (PAGE.replace('Comet CTF 2035</h1>', 'Other CTF 2035</h1>'), 'exact directory edition', 'unverified'),
    (PAGE.replace('Dec 4th 18:00 UTC until Dec 6th 18:00 UTC', 'December 4 to 6'), 'schedule is absent or unsupported', 'unverified'),
    (PAGE.replace('Dec 4th 18:00 UTC', 'Dec 4th 17:00 UTC'), 'conflict with the directory', 'unverified'),
    (PAGE.replace('Dec 4th 18:00 UTC', 'Dec 4th 2034 18:00 UTC'), 'year conflicts', 'unverified'),
    (PAGE.replace('18:00 UTC', '12:00 CT'), 'schedule is absent or unsupported', 'unverified'),
    (PAGE.replace('Dec 6th 18:00 UTC', 'Dec 6th 18:00 UTC+8'), 'schedule is absent or unsupported', 'unverified'),
    (PAGE.replace('Dec 6th 18:00 UTC', 'Dec 6th 18:00 GMT -04:00'), 'schedule is absent or unsupported', 'unverified'),
    ('<title>Comet CTF 2035</title><p>You need to enable JavaScript to run this app.</p>', 'requires JavaScript', 'javascript_only'),
    ('<h1>Comet CTF 2035</h1>', 'insufficient readable', 'unreadable'),
    ('<title>Access denied</title><p>Contact the administrator.</p>', 'access challenge', 'blocked'),
    (PAGE.replace('You are allowed to play either individually or with a team.', 'Rules are coming soon.'), 'participation rules', 'unverified'),
    (PAGE + '<p>Invitation-only tournament.</p>', 'participation rules', 'unverified'),
    (PAGE + '<p>US residents only.</p>', 'participation rules', 'unverified'),
    (PAGE + '<p>Participation is limited to residents of Canada.</p>', 'participation rules', 'unverified'),
    (PAGE + '<p>Not open to participants from the Philippines.</p>', 'participation rules', 'unverified'),
])
def test_unverified_primary_is_not_successful_zero(page, reason, status):
    db, report = run(Pages(page=page))
    state, = report['sources']
    assert state['status'] == 'partial' and state['discovered'] == 1 and state['accepted'] == 0
    assert state['decisions'][0]['unverified'] is True
    assert reason in state['decisions'][0]['reason']
    assert state['route_checks'][-1]['status'] == status
    assert report['events'] == 0
    db.close()


@pytest.mark.parametrize('failure,status', [
    (FetchError('HTTP 403'), 'blocked'),
    (FetchError('robots.txt disallows automated access'), 'blocked'),
    (FetchError('ReadTimeout'), 'error'),
    (RateLimited(60), 'rate_limited'),
])
def test_primary_network_failures_remain_audited(failure, status):
    db, report = run(Pages(page=failure))
    source, = report['sources']
    assert source['status'] == 'partial' and source['accepted'] == 0
    assert source['route_checks'][-1]['status'] == status
    assert source['decisions'][0]['unverified'] is True
    db.close()


@pytest.mark.parametrize('directory,status', [
    (FetchError('HTTP 403'), 'blocked'), (RateLimited(60), 'rate_limited'),
    (b'<html>Not an API</html>', 'error'), (b'{}', 'error'),
])
def test_directory_failure_is_not_empty_success(directory, status):
    db, report = run(Pages(directory=directory))
    source, = report['sources']
    assert source['status'] == status and source['route_checks'][0]['status'] == status
    assert source_states(db)[0]['last_success'] is None
    db.close()


def test_successful_empty_directory_is_distinct():
    pages = Pages(directory=b'[]')
    db, report = run(pages)
    assert report['sources'][0]['status'] == 'ok' and report['sources'][0]['discovered'] == 0
    assert source_states(db)[0]['last_success']
    assert all(url == API for url, _ in pages.requests)
    db.close()


@pytest.mark.parametrize('change', [{'onsite': True}, {'restrictions': 'Casual'}, {'start': (NOW - timedelta(seconds=1)).isoformat()},
                                     {'start': (NOW + timedelta(days=45)).isoformat()}])
def test_scope_and_window_are_checked_before_primary_fetch(change):
    pages = Pages(event=change)
    db, report = run(pages)
    assert report['sources'][0]['status'] == 'ok' and report['events'] == 0
    assert all(url == API for url, _ in pages.requests)
    db.close()


@pytest.mark.parametrize('addition', [
    '<a href="/register">Register now</a>', '<p>Register and use one account for your team.</p>',
    FORM.replace('<button>', '<button disabled>'),
    FORM.replace('<button>', '<button aria-disabled="true">'),
    FORM.replace('<button>', '<button type="button">'),
    FORM.replace('<input', '<fieldset disabled><input', 1).replace('</form>', '</fieldset></form>'),
    FORM.replace('/register', '/newsletter').replace('Register', 'Sign up'),
])
def test_signup_invitations_and_disabled_forms_do_not_prove_live_registration(addition):
    db, _ = run(Pages(page=PAGE + addition))
    event, = events(db, NOW, window_days=45)
    assert event['registration_status'] == 'unknown' and event['section'] == 'watchlist'
    db.close()


def test_live_registration_form_and_explicit_free_terms_are_independent_fields():
    db, report = run(Pages(page=PAGE + FORM + '<p>Registration is free.</p>'))
    event, = events(db, NOW, window_days=45)
    assert report['sources'][0]['status'] == 'ok'
    assert event['registration_status'] == 'open' and event['section'] == 'upcoming'
    assert event['registration_url'] == PRIMARY and event['account_required'] is True
    assert event['price'] == {'kind': 'free', 'amount': 0}
    assert event['field_evidence']['registration_state']['basis'] == 'live_registration_widget'
    assert event['deadline'] is None
    db.close()


def test_closed_registration_overrides_stale_enabled_form():
    db, _ = run(Pages(page=PAGE + FORM + '<p>Registration is closed.</p>'))
    assert events(db, NOW, window_days=45)[0]['registration_status'] == 'closed'
    db.close()


@pytest.mark.parametrize('terms', ['Participation is not free to play.', 'Registration is free for alumni only.',
                                  'There are free prizes.', 'If accepted, registration is free.'])
def test_negated_conditional_and_prize_free_copy_do_not_establish_price(terms):
    db, _ = run(Pages(page=PAGE + '<p>' + terms + '</p>'))
    assert events(db, NOW)[0]['price'] == {'kind': 'unknown'}
    db.close()


@pytest.mark.parametrize('url', ['http://127.0.0.1/', 'http://localhost/', 'http://10.0.0.1/',
                                'https://contest.example:8000/', 'http://service.internal/', 'http://[::1]/'])
def test_nonpublic_organizer_destinations_are_not_fetched(url):
    pages = Pages(event={'url': url})
    db, report = run(pages)
    assert report['sources'][0]['status'] == 'partial' and report['events'] == 0
    assert all(url == API for url, _ in pages.requests)
    db.close()


def test_replay_is_idempotent_and_failed_recheck_preserves_previous_listing():
    db, first = run()
    before = events(db, NOW)[0]
    _, second = run(db=db, now=NOW + timedelta(hours=1))
    after = events(db, NOW)[0]
    assert first['events'] == second['events'] == second['announcements'] == 1
    assert second['sources'][0]['new_announcements'] == 0
    assert before['id'] == after['id'] and before['first_seen'] == after['first_seen']
    assert after['announcements'][0]['revision_count'] == 1
    _, failed = run(Pages(page=FetchError('HTTP 403')), db=db, now=NOW + timedelta(hours=2))
    assert failed['sources'][0]['status'] == 'partial' and failed['events'] == 1
    assert events(db, NOW)[0]['start'] == before['start']
    db.close()
