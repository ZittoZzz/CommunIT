"""Historical measurement fixtures are fictional and never runtime inputs."""
from copy import deepcopy

import pytest

from backend.adapters import Result
from backend.collect import collect
from backend.db import connect, ingest, register_sources, withdraw
from backend.domain import parse_moment
from backend.metrics import evaluate_registration_observation, registration_observations


SOURCE = {'id': 'fictional', 'name': 'Fictional publisher', 'kind': 'rss',
          'url': 'https://publisher.example/feed/'}
OBSERVED = '2031-02-02T02:00:00+00:00'


def announcement():
    url = 'https://publisher.example/news/nebula-registration/'
    return {
        'url': url, 'title': 'Nebula CTF 2031 registration', 'access': 'full',
        'kind': 'registration', 'posted_at': '2031-01-01T02:00:00+00:00',
        'identity': {'organizer_key': 'nebula-club', 'series': 'Nebula CTF',
                     'edition': '2031', 'region': 'Unspecified', 'stage': 'main'},
        'facts': {'name': 'Nebula CTF 2031', 'registration_state': 'open',
                  'deadline': parse_moment('March 1, 2031 at 09:00 PHT')},
        'field_evidence': {
            'registration_state': {'url': url, 'quote': 'Registration is open.'},
            'deadline': {'url': url, 'quote': 'Registration deadline: March 1, 2031 at 09:00 PHT'},
        },
    }


@pytest.fixture
def db():
    connection = connect(':memory:')
    register_sources(connection, [SOURCE])
    yield connection
    connection.close()


def test_explicit_open_state_with_supported_timed_deadline_qualifies(db):
    ann = announcement()
    event_id, _ = ingest(db, SOURCE['id'], ann, OBSERVED)
    result = registration_observations(db)[0]
    assert result['event_id'] == event_id
    assert result['status'] == 'verified_timely'
    assert result['earliest_verified_at'] == OBSERVED
    assert result['registration_evidence']['deadline'] == ann['field_evidence']['deadline']
    assert result['reasons'] == []


@pytest.mark.parametrize('field,value,reason', [
    ('registration_state', 'closed', 'registration_not_confirmed_open'),
    ('registration_state', None, 'registration_not_confirmed_open'),
    ('deadline', None, 'registration_deadline_missing'),
    ('deadline', parse_moment('March 1, 2031'), 'registration_deadline_time_or_timezone_unconfirmed'),
    ('deadline', parse_moment('March 1, 2031 at 09:00'), 'registration_deadline_time_or_timezone_unconfirmed'),
    ('deadline', parse_moment('February 1, 2031 at 09:00 PHT'), 'registration_deadline_passed_at_observation'),
    ('deadline', parse_moment('2031-02-02T02:00:00Z'), 'registration_deadline_passed_at_observation'),
    ('registration_opens', parse_moment('February 1, 2031'), 'registration_opening_time_or_timezone_unconfirmed'),
    ('registration_opens', parse_moment('February 3, 2031 at 09:00 PHT'), 'registration_not_started_at_observation'),
    ('lifecycle', 'finished', 'event_finished_at_observation'),
    ('lifecycle', 'cancelled', 'event_cancelled_at_observation'),
    ('lifecycle', 'postponed', 'event_postponed_at_observation'),
    ('end', parse_moment('February 1, 2031 at 09:00 PHT'), 'competition_ended_at_observation'),
])
def test_incomplete_or_closed_windows_do_not_qualify(field, value, reason):
    ann = announcement()
    ann['facts'][field] = value
    reasons = evaluate_registration_observation(ann['facts'], ann['field_evidence'], OBSERVED)
    assert reason in reasons


@pytest.mark.parametrize('field', ['registration_state', 'deadline'])
def test_facts_without_their_historical_evidence_do_not_qualify(field):
    ann = announcement()
    del ann['field_evidence'][field]
    assert f'{field if field == "registration_state" else "registration_deadline"}_evidence_missing' in evaluate_registration_observation(
        ann['facts'], ann['field_evidence'], OBSERVED)


def test_explicit_opening_requires_confirmed_instant_and_its_evidence():
    ann = announcement()
    ann['facts']['registration_opens'] = parse_moment('February 1, 2031 at 09:00 PHT')
    assert 'registration_opening_evidence_missing' in evaluate_registration_observation(
        ann['facts'], ann['field_evidence'], OBSERVED)
    ann['field_evidence']['registration_opens'] = {
        'url': ann['url'], 'quote': 'Registration opens: February 1, 2031 at 09:00 PHT'}
    assert evaluate_registration_observation(ann['facts'], ann['field_evidence'], OBSERVED) == []


def test_event_first_seen_does_not_backdate_later_registration_evidence(db):
    teaser = announcement()
    teaser['facts']['registration_state'] = None
    teaser['facts']['deadline'] = None
    teaser['field_evidence'] = {}
    ingest(db, SOURCE['id'], teaser, '2031-01-01T00:00:00+00:00')
    ingest(db, SOURCE['id'], announcement(), OBSERVED)
    row = registration_observations(db)[0]
    assert row['first_seen'] == '2031-01-01T00:00:00+00:00'
    assert row['earliest_verified_at'] == OBSERVED
    assert row['observations_checked'] == 2


def test_later_closure_does_not_erase_historically_timely_evidence(db):
    ann = announcement()
    ingest(db, SOURCE['id'], ann, OBSERVED)
    closed = deepcopy(ann)
    closed['facts'].update(registration_state='closed', lifecycle='finished')
    closed['field_evidence']['registration_state']['quote'] = 'Registration closed.'
    ingest(db, SOURCE['id'], closed, '2031-03-02T00:00:00+00:00')
    result = registration_observations(db)[0]
    assert result['status'] == 'verified_timely'
    assert result['earliest_verified_at'] == OBSERVED
    assert result['registration_evidence']['registration_state']['quote'] == 'Registration is open.'


def test_later_source_change_does_not_relabel_the_qualifying_observation(db):
    ann = announcement()
    ingest(db, SOURCE['id'], ann, OBSERVED)
    second_source = {**SOURCE, 'id': 'different-monitor'}
    register_sources(db, [second_source])
    changed = deepcopy(ann)
    changed['facts']['registration_state'] = 'closed'
    ingest(db, second_source['id'], changed, '2031-03-02T00:00:00+00:00')
    assert registration_observations(db)[0]['source_id'] == SOURCE['id']


def test_latest_evidence_cannot_retroactively_validate_old_missing_proof(db):
    old = announcement()
    old['field_evidence'] = {}
    ingest(db, SOURCE['id'], old, OBSERVED)
    ingest(db, SOURCE['id'], announcement(), '2031-03-02T00:00:00+00:00')
    result = registration_observations(db)[0]
    assert result['status'] == 'not_verified'
    assert result['earliest_verified_at'] is None
    assert 'registration_deadline_passed_at_observation' in result['reasons']
    assert 'registration_state_evidence_missing' in result['reasons']


def test_completion_from_another_announcement_blocks_stale_open_invitation(db):
    ann = announcement()
    ingest(db, SOURCE['id'], ann, OBSERVED)
    cancellation = deepcopy(ann)
    cancellation['url'] = 'https://publisher.example/news/nebula-cancelled/'
    cancellation['facts'] = {'name': 'Nebula CTF 2031', 'lifecycle': 'cancelled'}
    cancellation['field_evidence'] = {'lifecycle': {'url': cancellation['url'], 'quote': 'The competition is cancelled.'}}
    ingest(db, SOURCE['id'], cancellation, OBSERVED)
    result = registration_observations(db)[0]
    assert result['status'] == 'not_verified'
    assert 'event_cancelled_already_observed' in result['reasons']


def test_withdrawn_source_evidence_is_not_used(db):
    ann = announcement()
    ann['external_id'] = 'fictional-post'
    ingest(db, SOURCE['id'], ann, OBSERVED)
    withdraw(db, SOURCE['id'], 'fictional-post', OBSERVED)
    assert registration_observations(db) == []


def test_normal_report_includes_measurement(db):
    from datetime import datetime
    def adapter(*args):
        result = Result()
        result.announcements = [announcement()]
        return result
    report = collect(db, [SOURCE], adapters={'rss': adapter}, now=datetime.fromisoformat(OBSERVED))
    assert report['verified_timely_count'] == 1
    assert report['registration_observations'][0]['status'] == 'verified_timely'


def test_live_observation_after_slow_fetch_cannot_backdate_registration_availability(db, monkeypatch):
    """A response arriving after the cutoff must not inherit the job start time."""
    import importlib
    from datetime import datetime
    collector = importlib.import_module('backend.collect')
    before = datetime.fromisoformat('2031-03-01T00:59:50+00:00')
    after = datetime.fromisoformat('2031-03-01T01:00:10+00:00')

    class Clock:
        current = before

        @classmethod
        def now(cls, tz):
            return cls.current.astimezone(tz)

    monkeypatch.setattr(collector, 'datetime', Clock)

    def slow_adapter(source, client, known, requested_at):
        assert requested_at == before
        Clock.current = after
        result = Result()
        result.announcements = [announcement()]  # Deadline is 01:00 UTC.
        return result

    report = collector.collect(db, [SOURCE], adapters={'rss': slow_adapter})
    assert report['started_at'] == before.isoformat()
    assert report['sources'][0]['attempted_at'] == before.isoformat()
    assert report['sources'][0]['observed_at'] == after.isoformat()
    assert db.execute('SELECT first_seen FROM events').fetchone()[0] == after.isoformat()
    assert db.execute('SELECT observed_at FROM revisions').fetchone()[0] == after.isoformat()
    assert db.execute('SELECT last_success FROM sources').fetchone()[0] == after.isoformat()
    assert report['verified_timely_count'] == 0
    assert 'registration_deadline_passed_at_observation' in report['registration_observations'][0]['reasons']


def test_explicit_collection_time_stays_fixed_when_adapter_clock_advances(db, monkeypatch):
    import importlib
    from datetime import datetime
    collector = importlib.import_module('backend.collect')
    injected = datetime.fromisoformat(OBSERVED)

    class Clock:
        @staticmethod
        def now(tz):
            raise AssertionError('An explicitly injected collection time must be used')

    monkeypatch.setattr(collector, 'datetime', Clock)

    def adapter(source, client, known, requested_at):
        assert requested_at == injected
        result = Result()
        result.announcements = [announcement()]
        return result

    report = collector.collect(db, [SOURCE], adapters={'rss': adapter}, now=injected)
    assert report['started_at'] == report['finished_at'] == OBSERVED
    assert report['sources'][0]['observed_at'] == OBSERVED
    assert db.execute('SELECT observed_at FROM revisions').fetchone()[0] == OBSERVED
    assert report['verified_timely_count'] == 1
