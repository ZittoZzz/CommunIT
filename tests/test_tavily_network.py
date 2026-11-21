"""Anonymous API transport tests; no live queries or competition seeds."""
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest
import requests

from backend.network import Client, FetchError, RateLimited, USER_AGENT, retry_seconds


ENDPOINT = 'https://api.tavily.com/search'


def stub_response(monkeypatch, body=b'{"results": []}', status=200, headers=None):
    calls = []

    def send(session, request, **kwargs):
        calls.append((session, request, kwargs))
        response = requests.Response()
        response.status_code = status
        response._content = body
        response._content_consumed = True
        response.headers.update(headers or {})
        response.request = request
        return response

    monkeypatch.setattr(requests.Session, 'send', send)
    return calls


def test_keyless_post_cannot_inherit_session_or_netrc_credentials(monkeypatch):
    calls = stub_response(monkeypatch)
    client = Client()
    client.session.auth = ('private-user', 'private-password')
    client.session.headers['Authorization'] = 'Bearer private-token'
    client.session.cookies.set('private-cookie', 'value', domain='api.tavily.com')

    def forbidden_netrc(*args, **kwargs):
        raise AssertionError('Anonymous transport must not consult .netrc')

    monkeypatch.setattr(requests.sessions, 'get_netrc_auth', forbidden_netrc)
    monkeypatch.setenv('HTTP_PROXY', 'http://private-user:private-password@proxy.example')
    monkeypatch.setenv('TAVILY_API_KEY', 'private-token')
    payload = {'query': 'Philippines cybersecurity competitions', 'include_answer': False}
    assert client.post_json(ENDPOINT, payload, headers={'X-Tavily-Access-Mode': 'keyless'}) == {'results': []}
    session, request, options = calls[0]
    assert session is not client.session and session.trust_env is False
    assert request.method == 'POST' and request.url == ENDPOINT
    assert json.loads(request.body) == payload
    assert request.headers['X-Tavily-Access-Mode'] == 'keyless'
    assert request.headers['User-Agent'] == USER_AGENT
    assert not {'Authorization', 'Cookie', 'Proxy-Authorization'} & set(request.headers)
    assert options['allow_redirects'] is False
    assert options['stream'] is True and options['timeout'] == (5, 15)
    assert not options.get('proxies')


@pytest.mark.parametrize('header', ['Authorization', 'authorization', 'Proxy-Authorization', 'Cookie'])
def test_anonymous_post_rejects_explicit_credentials(monkeypatch, header):
    calls = stub_response(monkeypatch)
    with pytest.raises(FetchError, match='cannot include credentials'):
        Client().post_json(ENDPOINT, {}, headers={header: 'private-token'})
    assert calls == []


@pytest.mark.parametrize('url', ['https://user:password@api.tavily.com/search',
                                 'file:///tmp/data', 'https://www.facebook.com/story.php'])
def test_anonymous_post_rejects_credentials_and_direct_facebook_requests(monkeypatch, url):
    calls = stub_response(monkeypatch)
    with pytest.raises(FetchError):
        Client().post_json(url, {})
    assert calls == []


def test_post_never_follows_redirects(monkeypatch):
    calls = stub_response(monkeypatch, status=302, headers={'Location': 'https://another.example/'})
    with pytest.raises(FetchError, match='redirects are disabled'):
        Client().post_json(ENDPOINT, {})
    assert len(calls) == 1


def test_rate_limit_is_an_error_with_retry_delay_and_no_automatic_retry(monkeypatch):
    calls = stub_response(monkeypatch, body=b'{"detail": "daily_cap_reached"}', status=429,
                          headers={'Retry-After': '15'})
    with pytest.raises(RateLimited) as error:
        Client().post_json(ENDPOINT, {})
    assert error.value.retry_after == 15
    assert str(error.value) == 'HTTP 429; retry after 15 seconds'
    assert len(calls) == 1


def test_rate_limit_missing_delay_does_not_invent_a_retry(monkeypatch):
    stub_response(monkeypatch, status=429)
    with pytest.raises(RateLimited) as error:
        Client().post_json(ENDPOINT, {})
    assert error.value.retry_after is None


def test_retry_after_http_date_and_invalid_values():
    future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60))
    assert 58 <= retry_seconds(future) <= 60
    assert retry_seconds('no delay available') is None
    assert retry_seconds('-5') is None


def test_post_enforces_size_limit_before_parsing_json(monkeypatch):
    stub_response(monkeypatch, body=b'x' * 4_000_001)
    with pytest.raises(FetchError, match='exceeds 4 MB'):
        Client().post_json(ENDPOINT, {})


@pytest.mark.parametrize('body,message', [(b'not JSON', 'not valid JSON'), (b'[]', 'not a JSON object')])
def test_post_requires_json_object(monkeypatch, body, message):
    stub_response(monkeypatch, body=body)
    with pytest.raises(FetchError, match=message):
        Client().post_json(ENDPOINT, {})


def test_http_errors_do_not_expose_remote_response_body(monkeypatch):
    stub_response(monkeypatch, status=500, body=b'private response contents')
    with pytest.raises(FetchError) as error:
        Client().post_json(ENDPOINT, {})
    assert str(error.value) == 'HTTP 500'


def test_transport_errors_do_not_expose_request_details(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError('private proxy credentials and request details')

    monkeypatch.setattr(requests.Session, 'send', fail)
    with pytest.raises(FetchError) as error:
        Client().post_json(ENDPOINT, {})
    assert str(error.value) == 'ConnectionError'
