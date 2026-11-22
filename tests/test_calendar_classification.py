"""Calendar dates are not clock times, completion notices, or registration."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.db import connect, events, ingest, register_sources
from backend.domain import calendar_day_passed, lifecycle, parse_moment
from backend.extract import extract
from backend.metrics import evaluate_registration_observation

NOW = datetime(2032, 11, 22, 4, tzinfo=timezone.utc)
SOURCE = {'id': 'campus', 'name': 'Campus invitations', 'url': 'https://campus.example/feed/',
          'kind': 'rss', 'publisher_role': 'resharer', 'body_identity': True}
URL = 'https://campus.example/challenge'
BODY = '''Two tournaments: a cybersecurity Capture the Flag (CTF) tournament and an AI hackathon.
Pre-Tournament Workshops:
September 11–13, 2031
Event Details:
Date:
October 8, 2031
Time:
9:00 AM – 6:00 PM
Venue:
Technology Hall, Makati City
Respectfully yours,
The Kestrel Security Team'''


def invitation(body=BODY, title='University Skills Challenge'):
    return extract(title, body, URL, SOURCE, posted_at='2031-09-02T02:00:00+00:00')


def test_split_html_labels_retain_tournament_day_without_workshop_or_program_clocks():
    ann = invitation()
    assert ann['facts']['competition_date'] == parse_moment('October 8, 2031')
    assert ann['facts']['start'] is ann['facts']['end'] is None
    assert ann['facts']['deadline'] is None
    assert ann['posted_at'] == '2031-09-02T02:00:00+00:00'
    assert ann['field_evidence']['competition_date'] == {
        'url': URL, 'quote': 'Event Details:\nDate:\nOctober 8, 2031'}
    assert lifecycle(ann['facts'], NOW) == ('past_date', 'unknown', 'past')


@pytest.mark.parametrize('body,title', [
    (BODY.replace('October 8, 2031', 'October 8'), 'University Skills Challenge 2031'),
    (BODY.replace('October 8, 2031', '08/10/31'), 'University Skills Challenge 2031'),
    (BODY.replace('Event Details:', 'Workshop Details:'), 'University Skills Challenge 2031'),
    (BODY, 'Security Conference 2031'),
    (BODY, 'Security Workshop 2031'),
    (BODY.replace('Two tournaments:', 'A conference with two tournaments:'), 'Student Meeting 2031'),
])
def test_ambiguous_or_parent_dates_do_not_become_a_tournament_day(body, title):
    ann = invitation(body, title)
    assert ann is not None
    assert ann['facts']['competition_date'] is None
    assert lifecycle(ann['facts'], NOW)[2] == 'upcoming'


def test_explicit_tournament_label_on_following_line_is_supported():
    ann = invitation(BODY.replace('Event Details:\nDate:', 'Tournament date:'))
    assert ann is not None  # Body identifies the tournament despite a generic title.
    assert ann['facts']['competition_date']['value'] == '2031-10-08'


def test_future_dated_competition_and_genuine_future_teaser_remain_upcoming():
    ann = invitation(BODY.replace('2031', '2033'))
    assert lifecycle(ann['facts'], NOW) == ('scheduled', 'unknown', 'upcoming')
    teaser = invitation('A cybersecurity CTF competition. Coming soon! Venue: Makati City', 'University CTF 2033')
    assert teaser['kind'] == 'teaser'
    assert lifecycle(teaser['facts'], NOW) == ('schedule_tba', 'unknown', 'upcoming')


def test_unknown_timezone_day_is_not_archived_while_that_day_exists_somewhere():
    day = parse_moment('2032-11-21')
    assert not calendar_day_passed(day, datetime(2032, 11, 22, 0, tzinfo=timezone.utc))
    assert calendar_day_passed(day, datetime(2032, 11, 22, 13, tzinfo=timezone.utc))
    assert day['timezone'] is None and day['precision'] == 'date'
    assert 'T' not in day['value']


def test_past_date_does_not_assert_completion_or_registration_closure():
    facts = {'competition_date': parse_moment('2031-10-08')}
    assert lifecycle(facts, NOW) == ('past_date', 'unknown', 'past')
    assert lifecycle({**facts, 'registration_state': 'open'}, NOW) == ('past_date', 'unknown', 'past')
    assert lifecycle({**facts, 'registration_state': 'closed'}, NOW) == ('past_date', 'closed', 'past')
    assert lifecycle({**facts, 'lifecycle': 'finished'}, NOW) == ('finished', 'closed', 'finished')


def test_same_day_started_and_confirmed_multiday_live_are_not_archived():
    start = parse_moment('2032-11-22T01:00:00Z')
    assert lifecycle({'start': start}, NOW) == ('end_unconfirmed', 'unknown', 'upcoming')
    assert lifecycle({'start': parse_moment('2032-11-20T01:00:00Z'),
                      'end': parse_moment('2032-11-23T01:00:00Z')}, NOW)[0] == 'live'


def test_refresh_correction_retains_first_seen_and_registration_evidence():
    db = connect(':memory:')
    register_sources(db, [SOURCE])
    old = invitation()
    old['facts']['competition_date'] = None
    old['field_evidence'].pop('competition_date')
    eid, _ = ingest(db, SOURCE['id'], old, '2032-11-01T00:00:00+00:00')
    before = events(db, NOW)[0]
    ingest(db, SOURCE['id'], invitation(), NOW.isoformat())
    after = events(db, NOW)[0]
    assert before['status'] == 'schedule_tba' and after['status'] == 'past_date'
    assert after['id'] == eid and before['first_seen'] == after['first_seen']
    assert before['registration_status'] == after['registration_status'] == 'unknown'
    assert after['start'] is after['end'] is after['deadline'] is None
    assert len(after['announcements']) == 1 and after['announcements'][0]['revision_count'] == 2
    db.close()


@pytest.mark.parametrize('change', ['postponed', 'reschedule_day', 'reschedule_bounds'])
def test_postponement_and_reschedule_replace_past_calendar_evidence(change):
    db = connect(':memory:')
    register_sources(db, [SOURCE])
    original = invitation()
    ingest(db, SOURCE['id'], original, '2032-11-01T00:00:00+00:00')
    update = deepcopy(original)
    update['url'] += '/update'
    update['posted_at'] = NOW.isoformat()
    if change == 'postponed':
        update['facts']['lifecycle'] = 'postponed'
    elif change == 'reschedule_day':
        update['facts']['competition_date'] = parse_moment('2033-01-10')
    else:
        update['facts']['competition_date'] = None
        update['facts']['start'] = parse_moment('2033-01-10T01:00:00Z')
        update['facts']['end'] = parse_moment('2033-01-10T09:00:00Z')
    ingest(db, SOURCE['id'], update, NOW.isoformat())
    current = events(db, NOW)[0]
    assert current['section'] == 'upcoming'
    if change != 'reschedule_day':
        assert current['competition_date'] is None
    db.close()


def test_past_tournament_day_prevents_false_timely_registration_measurement():
    ann = invitation()
    ann['facts'].update(registration_state='open', deadline=parse_moment('2033-01-10T01:00:00Z'))
    assert 'announced_competition_date_passed_at_observation' in evaluate_registration_observation(
        ann['facts'], ann['field_evidence'], NOW.isoformat())


@pytest.mark.parametrize('reminder_day,expected', [('2032-11-22', 'live'), ('2033-01-10', 'scheduled')])
def test_date_only_reminder_preserves_matching_clock_bounds_but_reschedule_replaces_them(reminder_day, expected):
    db = connect(':memory:')
    register_sources(db, [SOURCE])
    original = invitation()
    original['facts'].update(competition_date=None,
                             start=parse_moment('2032-11-22T01:00:00Z'),
                             end=parse_moment('2032-11-22T10:00:00Z'))
    ingest(db, SOURCE['id'], original, '2032-11-01T00:00:00+00:00')
    reminder = invitation()
    reminder['url'] += '/reminder'
    reminder['posted_at'] = NOW.isoformat()
    reminder['facts']['competition_date'] = parse_moment(reminder_day)
    ingest(db, SOURCE['id'], reminder, NOW.isoformat())
    current = events(db, NOW)[0]
    assert current['status'] == expected
    if expected == 'live':
        assert current['start'] == original['facts']['start']
        assert current['end'] == original['facts']['end']
        assert current['competition_date'] is None
    else:
        assert current['start'] is current['end'] is None
        assert current['competition_date']['value'] == reminder_day
    db.close()
