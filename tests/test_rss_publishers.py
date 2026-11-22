"""New-publisher discovery through ordinary feeds, using fictional articles."""
from datetime import datetime, timezone
from html import escape

from backend.adapters import rss
from backend.collect import collect
from backend.db import connect, events

FEED = 'https://reporter.example/ctf/feed/'
ARTICLE = 'https://reporter.example/a-student-story/'
SOURCE = {'id':'reporter', 'name':'Reporter', 'kind':'rss', 'url':FEED,
          'publisher_role':'resharer', 'body_identity':True, 'discover_publishers':True,
          'relationship_scope':True, 'follow_articles':True, 'allowed_hosts':['reporter.example'],
          'title_from_metadata':True, 'article_selector':'article'}
BODY = '''<p>On April 4, 2033, students competed in a cybersecurity Capture-the-Flag (CTF) competition.</p>
<p>The event was made possible by <a href="https://club.example/">New Club</a>,
held with the <a href="https://host.example/">Student Security Philippines</a> at the community hall.</p>
<p>The event closed with the Awarding Ceremony. Register now!</p>
<p>Prizes courtesy of our sponsor Example Academy.</p>'''


class Pages:
    def public_page(self, url, allowed_hosts=None):
        if url == FEED:
            return f'<rss version="2.0"><channel><title>News</title><item><title>A student story</title><link>{ARTICLE}</link><description>{escape(BODY)}</description></item></channel></rss>'.encode()
        assert url == ARTICLE
        return ('<meta property="og:title" content="Student Security CTF"><article>'+BODY+'</article>').encode()


def test_unmonitored_publishers_discovered_from_recurring_feed_and_recap_stays_closed():
    db=connect(':memory:')
    now=datetime(2033,5,1,tzinfo=timezone.utc)
    one=collect(db,[SOURCE],client=Pages(),now=now)
    two=collect(db,[SOURCE],client=Pages(),now=now)
    event=events(db,now)[0]
    assert one['events']==two['events']==1 and two['announcements']==1
    assert event['status']=='finished' and event['registration_status']=='closed'
    assert event['organizer']=='Organizer not confirmed'
    assert event['announcements'][0]['discovery_path']==[FEED,ARTICLE]
    assert len(two['publisher_candidates'])==3
    assert two['sources'][0]['publisher_candidates']['new_candidates']==0
    assert two['sources'][0]['publisher_candidates']['new_relationships']==0
    assert all(c['event_ids']==[event['id']] for c in two['publisher_candidates'])
    assert all(c['relationships'][0]['evidence']['discovery_path']==[FEED,ARTICLE] for c in two['publisher_candidates'])
    assert two['verified_timely_count']==0
    db.close()


def test_philippine_sponsor_only_cannot_make_foreign_event_in_scope():
    foreign=BODY.replace('held with the', 'sponsored by the')
    class Foreign(Pages):
        def public_page(self,url,allowed_hosts=None):
            return super().public_page(url,allowed_hosts).replace(BODY.encode(),foreign.encode()).replace(escape(BODY).encode(),escape(foreign).encode())
    result=rss(SOURCE,Foreign(),[],datetime(2033,5,1,tzinfo=timezone.utc))
    assert result.announcements==[]


def test_completion_evidence_survives_long_unrelated_workshop_description():
    prefix = '<p>' + ('The workshop covered security topics in detail. ' * 30) + 'The workshop ended with questions.</p>'
    class LongRecap(Pages):
        def public_page(self, url, allowed_hosts=None):
            return super().public_page(url, allowed_hosts).replace(b'<article>', ('<article>' + prefix).encode())
    result = rss(SOURCE, LongRecap(), [], datetime(2033, 5, 1, tzinfo=timezone.utc))
    assert len(result.announcements) == 1
    proof = result.announcements[0]['field_evidence']
    for field in ('lifecycle', 'registration_state'):
        assert 'event closed with the Awarding Ceremony' in proof[field]['quote']
        assert 'Register now' not in proof[field]['quote']
