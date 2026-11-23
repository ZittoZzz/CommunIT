"""Synthetic community discovery and primary-evidence regressions."""
import json
import socket
from datetime import datetime, timezone

import pytest

from backend.network import Client, FetchError
from backend.source_index import load_sources, SourceConfigurationError
from backend.standalone_event import parse_event
from backend.opportunity_pages import page_event_links
from backend import opportunity_search

NOW = datetime(2038, 12, 20, tzinfo=timezone.utc)
URL = 'https://conference.example/'


def conference(date='2039-01-04', extra_date=''):
    return f'''<meta property="og:title" content="Builders Conference 2039">
    <meta property="og:url" content="{URL}">
    <section id="about"><h1>What is Builders Conference 2039?</h1>
    <p>A cloud technology conference with software development workshops.</p></section>
    <section id="tickets"><article><h3>Standard</h3><time datetime="{date}">Jan 4</time>
    <p>PHP 250</p></article><article><h3>Plus</h3><time datetime="{extra_date or date}">Jan 4</time>
    <p>PHP 500</p></article><a href="https://tickets.example/buy">Get tickets</a></section>
    <section id="location">University Hall, Cebu City, Philippines</section>
    <section id="schedule"><h3>Registration</h3>8:00 AM<h3>Capture The Flag</h3></section>
    <section id="faq"><details><summary>Who is organizing this event?</summary>
    <p>The event is organized by Local Student Builders.</p></details></section>'''


def test_semantic_conference_preserves_ticket_date_and_unknown_inventory():
    ann, reason = parse_event(conference(), URL, {}, NOW)
    assert ann, reason
    facts = ann['facts']
    assert facts['name'] == 'Builders Conference 2039'
    assert facts['start']['precision'] == 'date' and facts['start']['timezone'] is None
    assert facts['deadline'] is None and facts['end'] is None
    assert facts['registration_state'] == 'unknown'
    assert facts['price'] == {'kind': 'paid', 'minimum_amount': 250, 'currency': 'PHP'}
    assert [t['price']['amount'] for t in facts['ticket_options']] == [250, 500]
    assert 'Capture The Flag' not in facts['description']


def test_conflicting_ticket_dates_and_unrelated_heading_remain_unverified():
    assert parse_event(conference(extra_date='2039-01-05'), URL, {}, NOW)[0] is None
    assert parse_event(conference().replace('What is Builders Conference 2039?', 'Another conference'), URL, {}, NOW)[0] is None


@pytest.mark.parametrize('label', [
    'Early bird sales end Jan 4', 'Registration closes Jan 4',
    'Book before Jan 4', 'Tickets valid until Jan 4',
    'Ticket release Jan 4', 'Applications open Jan 4',
])
def test_ticket_sales_and_signup_dates_are_not_event_start(label):
    raw = conference().replace('>Jan 4</time>', '>' + label + '</time>')
    ann, reason = parse_event(raw, URL, {}, NOW)
    assert ann is None
    assert 'sales or signup' in reason


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.1', '169.254.169.254', '::1', 'fd00::1'])
def test_discovered_targets_cannot_read_private_networks(monkeypatch, address):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(0,0,0,'',(address,443))])
    client = Client()
    monkeypatch.setattr(client, 'public_page', lambda *a, **k: pytest.fail('private request made'))
    with pytest.raises(FetchError, match='public addresses'):
        client.discovered_page('https://untrusted.example/')


def test_profile_inheritance_is_relative_preserves_parent_and_rejects_cycles(tmp_path):
    base = {'sources': [{'id': 'legacy', 'name': 'Legacy', 'kind': 'html', 'url': URL}]}
    (tmp_path/'base.json').write_text(json.dumps(base))
    child = {'extends': 'base.json', 'exclude_sources': ['legacy'], 'sources': [
        {'id': 'calendar', 'name': 'Calendar', 'kind': 'opportunity_calendar', 'url': 'https://luma.com/manila'}]}
    (tmp_path/'child.json').write_text(json.dumps(child))
    assert [s['id'] for s in load_sources(tmp_path/'child.json')] == ['calendar']
    assert json.loads((tmp_path/'base.json').read_text()) == base
    child['extends'] = 'child.json'
    (tmp_path/'child.json').write_text(json.dumps(child))
    with pytest.raises(SourceConfigurationError, match='cycle'):
        load_sources(tmp_path/'child.json')


def test_queries_cover_manila_month_and_year_rollover_without_event_seeds():
    class Search:
        def __init__(self): self.queries = []
        def post_json(self, url, payload, **kwargs):
            self.queries.append(payload['query'])
            return {'results': []}
    client = Search()
    source = {'url': 'https://api.tavily.com/search', 'kind': 'opportunity_search',
              'window_days':45, 'query_templates':['Philippines tech events {months}']}
    result = opportunity_search.opportunity_search(source, client, [], NOW)
    assert client.queries == ['Philippines tech events December 2038 January 2039 February 2039']
    assert result.searches[0]['status'] == 'ok' and not result.failed


def test_dated_calendar_links_and_luma_category_are_discovery_only():
    raw = '<a href="/edition"><time datetime="2039-01-04">Jan 4</time></a>'
    assert page_event_links(raw, URL, external_pages=True) == [URL+'edition']
    props = {'place': {'slug':'example'}, 'categoryPage': {'category':{}},
             'initialEvents': {'entries':[{'event':{'url':'example-event'}}]}}
    raw = '<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':props}})+'</script>'
    assert page_event_links(raw, 'https://luma.com/discover/example/tech') == ['https://luma.com/example-event']
