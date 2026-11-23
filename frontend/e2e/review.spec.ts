import { test, expect } from '@playwright/test';

const day = (value: string) => ({raw: value, value, precision: 'date', timezone: null});
const base = {
  id: 'lead', name: 'Unverified community lead', organizer: 'Organizer unconfirmed',
  region: 'Philippines', format: 'unknown', topics: [], section: 'watchlist', status: 'undated_lead',
  start: null, end: null, competition_date: null, deadline: null, registration_opens: null,
  registration_status: 'unknown', registration_url: null, eligibility: null,
  announcement_url: 'https://example.org/event', first_seen: '2035-01-01T00:00:00Z',
  last_checked: '2035-01-04T00:00:00Z', posted_at: null, summary: null,
  notices: [], announcements: [], stage: 'main', edition: '2035',
  review: {required: true, expired: false, expires_at: '2035-02-15T00:00:00Z',
    reasons: ['Source content could not be verified. Confirm the schedule and signup with the organizer.']},
  verification: {last_observed_at: '2035-01-04T00:00:00Z', last_content_fetched_at: null,
    last_event_page_checked_at: null, basis: 'search_only'},
};

for (const width of [1280, 390]) {
  test(`public review notes, archive and separate topics at ${width}px`, async ({page}) => {
    let collectionPosts = 0;
    page.on('request', request => {if (request.method() === 'POST' && request.url().includes('/api/collection')) collectionPosts++;});
    const events = [base,
      {...base, id: 'expired', name: 'Expired unverified lead', section: 'archived',
        review: {...base.review, expired: true, reasons: ['Unresolved for 45 days since first discovery. Archived as an unverified lead; this does not confirm the event ended.']}},
      {...base, id: 'cloud', name: 'Cloud workshop', topics: ['cloud'], section: 'upcoming', status: 'scheduled', start: day('2035-02-01'), review: {required:false}},
      {...base, id: 'devops', name: 'Delivery automation workshop', topics: ['devops'], section: 'upcoming', status: 'scheduled', start: day('2035-02-01'), review: {required:false}},
      {...base, id: 'both', name: 'Cloud delivery workshop', topics: ['cloud','devops'], section: 'upcoming', status: 'scheduled', start: day('2035-02-01'), review: {required:false}},
      {...base, id: 'completed', name: 'Completed CTF with parent event date', section:'finished', status:'finished', registration_status:'closed', parent_event_start:day('2034-10-04'), review:{required:false}},
    ];
    await page.route('**/api/events', route => route.fulfill({json:{events, sources:[], generated_at:'2035-01-04T00:00:00Z'}}));
    await page.setViewportSize({width, height:900});
    await page.goto('/');
    await expect(page.locator('.event-card')).toHaveCount(3);
    await page.getByRole('combobox', {name:/Topic/}).selectOption('cloud');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await expect(page.locator('.event-card').filter({hasText:'Delivery automation workshop'})).toHaveCount(0);
    await page.getByRole('combobox', {name:/Topic/}).selectOption('devops');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await page.getByRole('combobox', {name:/Topic/}).selectOption('');
    await expect(page.getByRole('option', {name:'Cloud & DevOps', exact:true})).toHaveCount(0);
    await page.getByRole('tab', {name:/Watchlist/}).click();
    await expect(page.locator('.event-card')).toHaveCount(1);
    await expect(page.locator('.preview-facts')).toContainText('Flagged for review');
    await page.locator('.event-details>summary').click();
    await expect(page.locator('.review-note')).toContainText('remains visible');
    await page.locator('.history>summary').click();
    await expect(page.locator('.checked')).toContainText('Last observed');
    await expect(page.locator('.checked')).toContainText('Search observations do not verify');
    await expect(page.locator('.checked')).not.toContainText('Last checked');
    await page.getByRole('tab', {name:/Archived leads/}).click();
    await expect(page.locator('.event-card')).toHaveCount(1);
    await expect(page.locator('.preview-facts')).toContainText('Verification expired');
    await expect(page.locator('.preview-facts')).not.toContainText('Finished');
    await page.locator('.event-details>summary').click();
    await expect(page.locator('.review-note')).toContainText('does not confirm the event ended');
    await page.getByRole('tab', {name:/Past & finished/}).click();
    await expect(page.locator('.event-date')).toContainText('Event date');
    await expect(page.locator('.event-date')).toHaveAttribute('datetime','2034-10-04');
    await page.locator('.event-details>summary').click();
    await expect(page.locator('.parent-schedule')).toContainText('do not establish the complete CTF schedule');
    await expect(page.locator('.event-detail-body>.dates')).toContainText('CTF starts');
    await page.getByRole('tab', {name:/All events/}).click();
    await expect(page.locator('.event-card')).toHaveCount(6);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    expect(collectionPosts).toBe(0);
    await expect(page.getByRole('button', {name:/admin/i})).toHaveCount(0);
  });
}
