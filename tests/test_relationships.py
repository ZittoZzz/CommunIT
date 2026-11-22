"""Synthetic relationship examples, never used by a live source."""
from bs4 import BeautifulSoup

from backend.relationships import publisher_leads_from_html, relationship_scope


URL = 'https://news.example/article'


def test_roles_are_local_to_their_clauses_and_keep_evidence():
    body = '''<p>The event was made possible by <a href="https://alpha.example/">Alpha</a>,
    <a href="https://beta.example/">Beta</a>. With Challenge Partners,
    <a href="https://gamma.example/">Gamma</a> and <a href="https://delta.example/">Delta</a>,
    held with the <a href="https://epsilon.example/">Epsilon Philippines</a> at the hall.</p>'''
    leads = publisher_leads_from_html(body, URL)
    assert [(x['name'], x['role']) for x in leads] == [
        ('Alpha', 'contributor'), ('Beta', 'contributor'),
        ('Gamma', 'challenge_partner'), ('Delta', 'challenge_partner'),
        ('Epsilon Philippines', 'contributor')]
    assert all(x['evidence']['url'] == URL for x in leads)
    assert relationship_scope(body, URL)['url'] == URL


def test_explicit_roles_are_not_inferred_from_unrelated_links():
    body = '''<p>Hosted by <a href="https://host.example/">Harbor Community</a>.</p>
    <p>Organized by <a href="https://org.example/">Byte Group</a>.</p>
    <p>Sponsored by <a href="https://sponsor.example/">Falcon Labs</a>.
    Read <a href="https://news.example/">Our News</a>.</p>
    <p><a href="https://unrelated.example/">Someone Else</a></p>'''
    assert [(x['name'], x['role']) for x in publisher_leads_from_html(body, URL)] == [
        ('Harbor Community', 'host'), ('Byte Group', 'organizer'), ('Falcon Labs', 'sponsor')]


def test_community_partner_label_and_unlinked_named_partnership():
    body = '''<p>Community Partner: <a href="https://www.facebook.com/example-community">Example Community Official Facebook</a></p>
    <p>Our learning partnership with the <strong>Example Data Society</strong> during the conference.</p>'''
    leads = publisher_leads_from_html(body, URL)
    assert leads[0]['name'] == 'Example Community'
    assert leads[0]['role'] == 'community_partner'
    assert leads[1]['name'] == 'Example Data Society' and 'url' not in leads[1]


def test_unlinked_sponsor_keeps_name_without_guessing_public_account():
    leads = publisher_leads_from_html('<p>The award was provided courtesy of our sponsor Example Academy.</p>', URL)
    assert len(leads) == 1
    assert leads[0]['name'] == 'Example Academy' and leads[0]['role'] == 'sponsor'
    assert 'url' not in leads[0] and 'account_id' not in leads[0]


def test_ignores_share_buttons_footers_author_and_nonaccount_links():
    body = '''<footer><p>Sponsored by <a href="https://footer.example/">Footer</a></p></footer>
    <aside><p>Hosted by <a href="https://aside.example/">Sidebar</a></p></aside>
    <div class="author"><p>Hosted by <a href="https://author.example/">Author</a></p></div>
    <p>Sponsored by <a href="https://facebook.com/sharer.php?u=x">Share</a>
    <a href="https://facebook.com/example/posts/123">Post</a>
    <a href="https://example.org/poster.pdf">Poster</a></p>'''
    assert publisher_leads_from_html(body, URL) == []


def test_preserves_distinct_public_accounts_despite_identical_names():
    body = '''<p>Hosted by <a href="https://one.example/">Same Name</a> and
    <a href="https://two.example/">Same Name</a>.</p>'''
    assert len(publisher_leads_from_html(body, URL)) == 2


def test_dedupes_same_link_and_role_without_mutating_input():
    soup = BeautifulSoup('<p>Community Partner: <a href="https://partner.example/">Copper Society</a></p>' * 2, 'html.parser')
    assert len(publisher_leads_from_html(soup, URL)) == 1
    assert len(soup.select('a')) == 2


def test_philippine_audience_and_author_bio_do_not_prove_organizer_scope():
    body = '''<p>Hosted by <a href="https://world.example/">World Group</a>. Students in the Philippines may join.</p>
    <footer><p>Hosted by <a href="https://local.example/">Local Philippines</a>.</p></footer>'''
    assert relationship_scope(body, URL) is None


def test_negated_and_prospective_relationships_do_not_create_leads():
    body = '''<p>We are looking for sponsors: <a href="https://maybe.example/">Maybe Company</a>.</p>
    <p>We are not hosted by <a href="https://wrong.example/">Wrong Host</a>.</p>'''
    assert publisher_leads_from_html(body, URL) == []


def test_evergreen_ctf_topic_has_no_publisher_relationship():
    assert publisher_leads_from_html('<p>CTF Challenges: improve your skills with <a href="https://labs.example/">Labs</a>.</p>', URL) == []


def test_announcement_link_is_not_a_publisher_identity():
    leads = publisher_leads_from_html(f'<p>Hosted by <a href="{URL}">Example Society</a>.</p>', URL)
    assert len(leads) == 1 and 'url' not in leads[0]


def test_foreign_competition_with_philippine_sponsor_does_not_establish_scope():
    body = '''<p>The CTF competition is held in London.</p>
    <p>Sponsored by <a href="https://sponsor.example/">Example Philippines</a>.</p>
    <p>Challenge Partner: <a href="https://partner.example/">Partner Philippines</a>.</p>
    <p>Made possible by <a href="https://contributor.example/">Contributor Philippines</a>.</p>'''
    assert len(publisher_leads_from_html(body, URL)) == 3
    assert relationship_scope(body, URL) is None


def test_linked_philippine_co_organizer_establishes_scope():
    body = '<p>Co-organized by <a href="https://organizer.example/">Example Philippines</a>.</p>'
    assert relationship_scope(body, URL)['url'] == URL
