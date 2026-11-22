"""Public-feed transport and persistent Retry-After behavior, with no live URLs."""
from datetime import datetime, timedelta, timezone

import pytest
import requests

from backend.adapters import Result
from backend.collect import collect
from backend.db import connect
from backend.network import Client, RateLimited


def test_public_robots_rate_limit_preserves_delay_and_blocks_followup_requests(monkeypatch):
    calls = []
    def send(session, request, **kwargs):
        calls.append(request)
        response = requests.Response()
        response.status_code = 429
        response._content = b'not retained'
        response._content_consumed = True
        response.headers['Retry-After'] = '120'
        return response
    monkeypatch.setattr(requests.Session, 'send', send)
    client = Client()
    with pytest.raises(RateLimited) as first:
        client.public_page('https://calendar.example/city')
    assert first.value.retry_after == 120
    with pytest.raises(RateLimited):
        client.public_page('https://calendar.example/feed.ics')
    assert len(calls) == 1


def test_redirect_rate_limit_keeps_header(monkeypatch):
    def send(session, request, **kwargs):
        response = requests.Response()
        response._content = b''
        response._content_consumed = True
        response.status_code = 302 if request.url.endswith('/old') else 429
        response.headers.update({'Location': '/new', 'Retry-After': '90'})
        return response
    monkeypatch.setattr(requests.Session, 'send', send)
    with pytest.raises(RateLimited) as error:
        Client().read('https://calendar.example/old')
    assert error.value.retry_after == 90


def test_collector_persists_cooldown_skips_request_and_continues_other_sources():
    db = connect(':memory:')
    sources = [{'id': name, 'name': name, 'kind': name, 'url': f'https://{name}.example/'} for name in ('limited', 'working')]
    calls = []
    def limited(*args):
        calls.append('limited')
        raise RateLimited(120)
    def working(*args):
        calls.append('working')
        return Result()
    adapters = {'limited': limited, 'working': working}
    now = datetime(2033, 2, 1, tzinfo=timezone.utc)
    one = collect(db, sources, adapters=adapters, now=now)
    two = collect(db, sources, adapters=adapters, now=now + timedelta(seconds=30))
    assert calls == ['limited', 'working', 'working']
    assert one['sources'][0]['status'] == two['sources'][0]['status'] == 'rate_limited'
    assert two['sources'][0]['next_retry_at'] == (now + timedelta(seconds=120)).isoformat()
    assert two['sources'][1]['status'] == 'ok'
    collect(db, sources, adapters=adapters, now=now + timedelta(seconds=121))
    assert calls[-2:] == ['limited', 'working']
    db.close()


def test_anonymous_public_read_does_not_reuse_cookies(monkeypatch):
    calls = []
    def send(session, request, **kwargs):
        calls.append(request)
        response = requests.Response()
        response.status_code = 200
        response._content = b'public'
        response._content_consumed = True
        return response
    monkeypatch.setattr(requests.Session, 'send', send)
    client = Client()
    client.session.cookies.set('private', 'value', domain='calendar.example')
    assert client.read('https://calendar.example/feed.ics') == b'public'
    assert 'Cookie' not in calls[0].headers
    assert client.session.trust_env is False


def test_changed_endpoint_cannot_reuse_old_verification_or_cooldown():
    from backend.db import register_sources
    db=connect(':memory:')
    source={'id':'publisher','name':'Publisher','kind':'rss','url':'https://old.example/feed'}
    register_sources(db,[source])
    db.execute("UPDATE sources SET last_success='2033-01-01T00:00:00+00:00', status='ok', next_retry_at='2033-02-01T00:00:00+00:00'")
    register_sources(db,[{**source,'url':'https://new.example/feed'}])
    state=db.execute('SELECT * FROM sources').fetchone()
    assert state['last_success'] is state['next_retry_at'] is None
    assert state['status']=='not_run'
    db.close()
