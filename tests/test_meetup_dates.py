"""Offline saved-source regression, through extraction, SQLite and the normal API."""
from copy import deepcopy
from datetime import datetime
from html import escape
import json
from pathlib import Path

import pytest

from backend import domain
from backend.adapters import rss
from backend.app import create_app
from backend.db import connect, events, ingest, register_sources
from backend.domain import parse_moment
from backend.extract import extract

SAVED = json.loads((Path(__file__).parent / 'fixtures/htb_meetup_11.json').read_text())
SOURCE, ENTRY = SAVED['source'], SAVED['entry']
NOW = datetime.fromisoformat('2026-11-22T21:17:42.208565+08:00')


def announcement(body=None):
    return extract(ENTRY['title'], body or ENTRY['description'], ENTRY['link'], SOURCE,
                   posted_at='2026-10-18T06:45:09+00:00')


def fixed_clock(monkeypatch, at):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return at.astimezone(tz) if tz else at.replace(tzinfo=None)
    monkeypatch.setattr(domain, 'datetime', FixedDatetime)


def api_listing(tmp_path, monkeypatch, announcements, at=NOW):
    path = tmp_path / 'test.sqlite3'
    db = connect(path)
    register_sources(db, [SOURCE])
    for ann in announcements:
        ingest(db, SOURCE['id'], ann, NOW.isoformat())
    db.commit()
    db.close()
    monkeypatch.setenv('CTF_SOURCES', str(tmp_path / 'no-source-config'))
    fixed_clock(monkeypatch, at)
    app = create_app(path)
    return app.test_client().get('/api/events').get_json()['events']


def test_saved_rss_date_survives_extraction_storage_and_normal_listing(tmp_path, monkeypatch):
    # Reconstruct only the saved RSS envelope. The adapter cannot use the network.
    raw = ('<rss version="2.0"><channel><item>' + ''.join(
        f'<{tag}>{escape(ENTRY[key])}</{tag}>' for tag, key in
        [('title', 'title'), ('link', 'link'), ('pubDate', 'published'), ('description', 'description')]
    ) + '</item></channel></rss>').encode()
    class SavedFeed:
        def public_page(self, url):
            assert url == SOURCE['url']
            return raw
    result = rss(SOURCE, SavedFeed(), [], NOW)
    assert len(result.announcements) == 1
    ann = result.announcements[0]
    assert ann['facts']['competition_date'] == parse_moment('November 4, 2026')
    assert 'Happening on November 4, 2026' in ann['field_evidence']['competition_date']['quote']
    assert 'Capture the Flag (CTF) competition' in ann['field_evidence']['competition_date']['quote']
    event, = api_listing(tmp_path, monkeypatch, [ann])
    assert event['status'] == 'past_date' and event['section'] == 'past'
    assert event['start'] is event['end'] is event['deadline'] is None
    assert event['competition_date'] == parse_moment('November 4, 2026')
    assert event['registration_status'] == 'unknown'
    assert event['id'] == 'a6f4e09e73b9a682104e0b25'


@pytest.mark.parametrize('at,section', [
    ('2026-11-22T00:00:00+08:00', 'upcoming'),
    ('2026-11-22T23:59:59.999999+08:00', 'upcoming'),
    ('2026-11-22T16:00:00+00:00', 'past'),
])
def test_today_stays_eligible_until_manila_midnight_in_normal_api(tmp_path, monkeypatch, at, section):
    ann = announcement(ENTRY['description'].replace('November 4, 2026', 'November 22, 2026'))
    event, = api_listing(tmp_path, monkeypatch, [ann], datetime.fromisoformat(at))
    assert event['section'] == section
    assert event['competition_date'] == parse_moment('November 22, 2026')
    assert event['start'] is event['end'] is None


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('labels', [False, True])
def test_conflicting_days_preserve_evidence_without_upcoming_choice(tmp_path, monkeypatch, reverse, labels):
    parts = ['November 4, 2026', 'December 4, 2026']
    if reverse:
        parts.reverse()
    if labels:
        body = '\n'.join(f'Tournament date: {day}' for day in parts)
        body += '\nA CTF competition. Venue: Quezon City. Organized by the Example Club.'
    else:
        body = '\n'.join(ENTRY['description'].replace('November 4, 2026', day) for day in parts)
    ann = announcement(body)
    event, = api_listing(tmp_path, monkeypatch, [ann])
    assert event['status'] == 'date_conflict' and event['section'] == 'unconfirmed'
    assert event['start'] is event['end'] is event['competition_date'] is None
    assert {c['date']['value'] for c in event['date_conflicts']} == {'2026-11-04', '2026-12-04'}
    assert all(c['quote'] for c in event['date_conflicts'])
    assert all(day in event['field_evidence']['date_conflicts']['quote'] for day in parts)
    assert any('Conflicting event dates' in notice for notice in event['notices'])


def test_repeated_day_and_unrelated_parent_mentions():
    assert announcement(ENTRY['description'] + '\n' + ENTRY['description'])['facts']['competition_date']['value'] == '2026-11-04'
    body = ENTRY['description'].replace('the event will feature', 'learn about next year’s')
    assert announcement(body)['facts']['competition_date'] is None
    body = 'Happening on November 4, 2026, at Quezon City University, the event will feature talks about next year’s Capture the Flag (CTF) competition. Organized by the Example Club.'
    assert announcement(body)['facts']['competition_date'] is None


def test_conflict_clears_prior_bounds_survives_dateless_update_and_resolves():
    db = connect(':memory:')
    register_sources(db, [SOURCE])
    original = announcement()
    original['facts'].update(competition_date=None, start=parse_moment('2026-12-04T02:00:00Z'),
                             end=parse_moment('2026-12-04T10:00:00Z'))
    ingest(db, SOURCE['id'], original, NOW.isoformat())
    conflict = announcement(ENTRY['description'] + '\nTournament date: December 4, 2026')
    conflict['url'] += '/update'
    conflict['posted_at'] = '2026-11-23T00:00:00Z'
    ingest(db, SOURCE['id'], conflict, NOW.isoformat())
    current, = events(db, NOW)
    assert current['section'] == 'unconfirmed'
    assert current['start'] is current['end'] is current['competition_date'] is None
    dateless = deepcopy(original)
    dateless['url'] += '/dateless'
    dateless['posted_at'] = '2026-11-24T00:00:00Z'
    dateless['facts'].update(start=None, end=None)
    ingest(db, SOURCE['id'], dateless, NOW.isoformat())
    assert events(db, NOW)[0]['section'] == 'unconfirmed'
    corrected = announcement()
    corrected['url'] += '/correction'
    corrected['posted_at'] = '2026-11-25T00:00:00Z'
    ingest(db, SOURCE['id'], corrected, NOW.isoformat())
    current, = events(db, NOW)
    assert current['section'] == 'past' and current['date_conflicts'] == []
    assert 'date_conflicts' not in current['field_evidence']
    db.close()


def test_valid_range_and_manila_day_corroboration_do_not_conflict():
    prefix = 'A CTF competition. Venue: Quezon City. Organized by the Example Club.\n'
    ann = announcement(prefix + 'Competition dates: November 4–6, 2026')
    assert 'date_conflicts' not in ann['facts']
    assert ann['facts']['start']['value'] == '2026-11-04'
    assert ann['facts']['end']['value'] == '2026-11-06'
    ann = announcement(ENTRY['description'] + '\nCTF start: 2026-11-03T23:00:00Z')
    assert 'date_conflicts' not in ann['facts']
    assert ann['facts']['start']['precision'] == 'datetime'
    db = connect(':memory:')
    register_sources(db, [SOURCE])
    ingest(db, SOURCE['id'], ann, NOW.isoformat())
    reminder = announcement()
    reminder['url'] += '/reminder'
    reminder['posted_at'] = '2026-11-01T00:00:00Z'
    ingest(db, SOURCE['id'], reminder, NOW.isoformat())
    current, = events(db, NOW)
    assert current['start'] == ann['facts']['start'] and current['competition_date'] is None
    db.close()


@pytest.mark.parametrize('field', ['start', 'end'])
def test_repeated_clock_labels_do_not_silently_choose_one_date(field):
    ann = announcement(ENTRY['description'] + f'\nCTF {field}: 2026-11-04T02:00:00Z\nCTF {field}: 2026-12-04T02:00:00Z')
    assert ann['facts']['date_conflicts']
    assert ann['facts']['start'] is ann['facts']['end'] is None


def test_end_before_start_is_uncertain_instead_of_selected():
    body = 'A CTF competition. Venue: Quezon City. Organized by the Example Club.\nCTF start: December 4, 2026\nCTF end: November 4, 2026'
    ann = extract('Example CTF 2026', body, ENTRY['link'], SOURCE)
    assert ann['facts']['date_conflicts']
    assert ann['facts']['start'] is ann['facts']['end'] is None


def test_date_only_end_uses_manila_day_without_rewriting_source_timezone(tmp_path, monkeypatch):
    ann = announcement(ENTRY['description'].replace('November 4, 2026', 'November 22, 2026'))
    ann['facts']['end'] = {**parse_moment('November 22, 2026'), 'timezone': 'Pacific/Auckland'}
    event, = api_listing(tmp_path, monkeypatch, [ann], datetime.fromisoformat('2026-11-22T23:59:59+08:00'))
    assert event['section'] == 'upcoming'
    assert event['end']['timezone'] == 'Pacific/Auckland' and event['end']['precision'] == 'date'
