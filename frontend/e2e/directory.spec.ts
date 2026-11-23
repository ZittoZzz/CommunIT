import { test, expect, type Locator } from '@playwright/test';

async function selectPaper(card: Locator) {
  const page = card.page();
  const back = page.getByRole('button', { name: 'Back to the board' });
  if (await back.isVisible()) await back.click();
  const name = await card.locator('h3').textContent() || '';
  await card.locator('.notice-select').click();
  await expect(page.locator('.notice-select[aria-pressed=true]')).toHaveText(name);
  await expect(page.locator('#paper-title')).toHaveText(name);
  await expect(page.locator('.paper')).toBeVisible();
}

// These are API display fixtures, not collector inputs or benchmark editions.
// The backend owns evidence-based topic classification; the UI consumes topics.
const topicDirectory = () => {
  const day = (value: string) => ({ raw: value, value, precision: 'date', timezone: null });
  const base = {
    organizer: 'Example community', region: 'NCR', geography: 'PH', format: 'in_person',
    eligibility: 'Open to students.', announcement_url: 'https://organizer.example/meetup',
    registration_url: null, registration_status: 'open', status: 'scheduled', section: 'upcoming',
    start: day('2037-05-10'), end: day('2037-05-10'), deadline: null,
    registration_opens: null, posted_at: null, first_seen: '2037-05-01T00:00:00Z',
    last_checked: '2037-05-01T00:00:00Z', summary: null, stage: 'main', edition: '2037',
    notices: [], announcements: [], price: { kind: 'unknown' },
  };
  return {
    events: [
      { ...base, id: 'topic-ctf', name: 'Campus Capture The Flag 2037', format: 'online',
        topic: 'cybersecurity', topics: ['cybersecurity'],
        field_evidence: { topic: { url: 'https://organizer.example/ctf', quote: 'A cybersecurity Capture The Flag competition for students.' } } },
      { ...base, id: 'topic-ai-workshop', name: 'Community AI App-building Meetup 2037',
        topic: 'ai', topics: ['ai_data', 'software_development', 'community'],
        summary: 'Build an AI app with Python, then meet fellow builders and share projects in a community showcase.',
        field_evidence: { topic: { url: 'https://organizer.example/meetup', quote: 'Build an AI app with Python, then meet fellow builders and share projects in a community showcase.' } } },
      { ...base, id: 'topic-online-ai', name: 'Online AI research talks 2037',
        format: 'online', region: 'Worldwide', geography: 'international_online',
        topic: 'ai', topics: ['ai_data'] },
      { ...base, id: 'topic-legacy', name: 'Community meetup 2037', organizer: 'Example chapter', topics: [] },
      { ...base, id: 'topic-social', name: 'Developer peer showcase social 2037', organizer: 'Local builders',
        summary: 'Meet local developers, share your projects and get to know other people interested in technology.', topics: ['community'] },
    ],
    sources: [], generated_at: '2037-05-01T00:00:00Z',
  };
};

const collectionFixture = (state: 'idle' | 'running' | 'completed' | 'failed', checked = 0, message = '') => ({
  enabled: true, state, started_at: state === 'idle' ? null : '2037-05-01T00:00:00Z',
  finished_at: ['completed', 'failed'].includes(state) ? '2037-05-01T00:01:00Z' : null,
  completed_sources: checked, total_sources: 3, warning_count: 0,
  message: message || (state === 'idle' ? 'Ready to fetch events.' : 'Checking public organizer pages.'),
});

test('manual fetching is absent when the server does not enable it', async ({ page }) => {
  const data = topicDirectory();
  let explicitlyDisabled = false;
  let collectionCalls = 0;
  await page.route('**/api/events', route => route.fulfill({ json: { ...data, ...(explicitlyDisabled ? { manual_collection: { enabled: false } } : {}) } }));
  await page.route('**/api/collection', route => { collectionCalls++; return route.fulfill({ status: 403 }); });
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(5);
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Refresh saved listings' })).toBeVisible();
  explicitlyDisabled = true;
  await page.reload();
  await expect(page.locator('.event-card')).toHaveCount(5);
  await expect(page.locator('.collection-status')).toHaveCount(0);
  expect(collectionCalls).toBe(0);
});

test('manual fetch sends one token-bearing request, reports progress, and reloads results without clearing filters', async ({ page }) => {
  const data = topicDirectory();
  const added = { ...data.events[1], id: 'manual-new-event', name: 'Community AI coding workshop 2037' };
  let phase: 'idle' | 'running' | 'progress' | 'completed' = 'idle';
  let postCount = 0;
  let eventReads = 0;
  await page.route('**/api/events', route => {
    eventReads++;
    return route.fulfill({ json: { ...data, events: phase === 'completed' ? [...data.events, added] : data.events, manual_collection: { enabled: true, token: 'browser-test-token' } } });
  });
  await page.route('**/api/collection', route => {
    if (route.request().method() === 'POST') {
      postCount++;
      expect(route.request().headers()['x-collection-token']).toBe('browser-test-token');
      expect(route.request().postDataJSON()).toEqual({});
      phase = 'running';
      return route.fulfill({ status: 202, json: collectionFixture('running') });
    }
    const state = phase === 'progress' ? 'running' : phase;
    return route.fulfill({ json: collectionFixture(state, phase === 'completed' ? 3 : phase === 'progress' ? 2 : 0,
      phase === 'completed' ? 'Saved the latest public events.' : 'Checking public organizer pages.') });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const topic = page.getByRole('combobox', { name: 'Topic', exact: true });
  const format = page.getByRole('combobox', { name: 'Format', exact: true });
  const registration = page.getByRole('combobox', { name: 'Registration', exact: true });
  const search = page.getByRole('searchbox');
  await topic.selectOption('ai_data');
  await format.selectOption('in_person');
  await registration.selectOption('open');
  await search.fill('Community');
  await expect(page.locator('.event-card')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toBeEnabled();
  const initialReads = eventReads;
  await page.getByRole('button', { name: 'Fetch events', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Fetching events…', exact: true })).toBeDisabled();
  await expect(page.locator('.collection-status')).toContainText('Checked 0 of 3 sources');
  phase = 'progress';
  await expect(page.locator('.collection-status')).toContainText('Checked 2 of 3 sources');
  await expect(page.locator('.collection-status')).toContainText('Checking public organizer pages.');
  phase = 'completed';
  await expect(page.locator('.collection-status')).toContainText('Fetch complete');
  await expect(page.locator('.collection-status')).toContainText('Saved the latest public events.');
  await expect(page.locator('.event-card')).toHaveCount(2);
  await expect(topic).toHaveValue('ai_data');
  await expect(format).toHaveValue('in_person');
  await expect(registration).toHaveValue('open');
  await expect(search).toHaveValue('Community');
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toBeEnabled();
  expect(eventReads).toBe(initialReads + 1);
  expect(postCount).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('failed collection remains retryable and reloads saved partial results', async ({ page }) => {
  const data = topicDirectory();
  let started = false;
  let eventReads = 0;
  const partial = { ...data.events[0], id: 'saved-before-source-failure', name: 'Saved partial collection result' };
  await page.route('**/api/events', route => { eventReads++; return route.fulfill({ json: { ...data, events: started ? [...data.events, partial] : data.events, manual_collection: { enabled: true, token: 'browser-test-token' } } }); });
  await page.route('**/api/collection', route => {
    if (route.request().method() === 'POST') { started = true; return route.fulfill({ status: 202, json: collectionFixture('running') }); }
    return route.fulfill({ json: collectionFixture(started ? 'failed' : 'idle', started ? 3 : 0, started ? 'Public sources could not be reached.' : 'Ready.') });
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toBeEnabled();
  const initialReads = eventReads;
  await page.getByRole('button', { name: 'Fetch events', exact: true }).click();
  await expect(page.locator('.collection-status [role=alert]')).toContainText('Public sources could not be reached.');
  await expect(page.locator('.collection-status [role=alert]')).toContainText('Saved events are still shown.');
  for (const event of data.events) await expect(page.locator('.event-card').getByRole('heading', { name: event.name, exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toBeEnabled();
  await expect(page.locator('.event-card')).toHaveCount(6);
  await expect(page.locator('.event-card').getByRole('heading', { name: partial.name, exact: true })).toBeVisible();
  expect(eventReads).toBe(initialReads + 1);
});

test('an already running collection resumes polling after page reload without starting another job', async ({ page }) => {
  const data = topicDirectory();
  let posts = 0;
  await page.route('**/api/events', route => route.fulfill({ json: { ...data, manual_collection: { enabled: true, token: 'browser-test-token' } } }));
  await page.route('**/api/collection', route => {
    if (route.request().method() === 'POST') posts++;
    return route.fulfill({ json: collectionFixture('running', 1, 'A fetch is already running.') });
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Fetching events…', exact: true })).toBeDisabled();
  await expect(page.locator('.collection-status')).toContainText('Checked 1 of 3 sources');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Fetching events…', exact: true })).toBeDisabled();
  await expect(page.locator('.collection-status')).toContainText('A fetch is already running.');
  await expect(page.locator('.event-card')).toHaveCount(5);
  expect(posts).toBe(0);
});

test('a concurrent-start conflict reconciles through status without posting twice', async ({ page }) => {
  const data = topicDirectory();
  let posts = 0;
  await page.route('**/api/events', route => route.fulfill({ json: { ...data, manual_collection: { enabled: true, token: 'browser-test-token' } } }));
  await page.route('**/api/collection', route => {
    if (route.request().method() === 'POST') { posts++; return route.fulfill({ status: 409, json: collectionFixture('running') }); }
    return route.fulfill({ json: collectionFixture(posts ? 'running' : 'idle', posts ? 1 : 0) });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Fetch events', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Fetching events…', exact: true })).toBeDisabled();
  await expect(page.locator('.collection-status')).toContainText('Checked 1 of 3 sources');
  await expect(page.locator('.collection-status [role=alert]')).toHaveCount(0);
  expect(posts).toBe(1);
});

test('a lost start response requires a status check before another collection can be submitted', async ({ page }) => {
  const data = topicDirectory();
  let posts = 0;
  await page.route('**/api/events', route => route.fulfill({ json: { ...data, manual_collection: { enabled: true, token: 'browser-test-token' } } }));
  await page.route('**/api/collection', route => {
    if (route.request().method() === 'POST') { posts++; return route.abort('failed'); }
    return route.fulfill({ json: collectionFixture(posts ? 'running' : 'idle', posts ? 1 : 0) });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Fetch events', exact: true }).click();
  await expect(page.locator('.collection-status [role=alert]')).toContainText('Couldn’t confirm the event fetch.');
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toBeDisabled();
  await expect(page.locator('.event-card')).toHaveCount(5);
  await page.getByRole('button', { name: 'Check fetch status', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Fetching events…', exact: true })).toBeDisabled();
  await expect(page.locator('.collection-status')).toContainText('Checked 1 of 3 sources');
  expect(posts).toBe(1);
});

test('a failed status request can be retried without erasing saved results', async ({ page }) => {
  const data = topicDirectory();
  let gets = 0;
  let posts = 0;
  await page.route('**/api/events', route => route.fulfill({ json: { ...data, manual_collection: { enabled: true, token: 'browser-test-token' } } }));
  await page.route('**/api/collection', route => {
    if (route.request().method() === 'POST') posts++;
    gets++;
    return gets === 1 ? route.fulfill({ status: 503 }) : route.fulfill({ json: collectionFixture('idle') });
  });
  await page.goto('/');
  await expect(page.locator('.collection-status [role=alert]')).toContainText('Couldn’t check fetch status.');
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toBeDisabled();
  await expect(page.locator('.event-card')).toHaveCount(5);
  await page.getByRole('button', { name: 'Check fetch status', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Fetch events', exact: true })).toBeEnabled();
  await expect(page.locator('.collection-status [role=alert]')).toHaveCount(0);
  expect(posts).toBe(0);
});

for (const viewport of [{ name: 'desktop', width: 1440, height: 1000 }, { name: 'mobile', width: 390, height: 844 }]) {
  test(`brand and evidence-backed topic cards render on ${viewport.name}`, async ({ page }) => {
    const data = topicDirectory();
    await page.route('**/api/events', route => route.fulfill({ json: data }));
    await page.setViewportSize(viewport);
    await page.goto('/');
    await expect(page).toHaveTitle('The Tech Board | CommunITy PH');
    await expect(page.locator('header .brand')).toHaveText('CommunITy PH');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('The Tech Board');
    await expect(page.locator('.hero h1 + .hero-description')).toHaveText('Your next tech meetup, hackathon, or conference might be right here.');
    await expect(page.locator('.hero .eyebrow')).toHaveCount(0);
    await expect(page.locator('.hero .timezone')).toHaveText('Asia/Manila · PHT');
    await expect(page.getByRole('link', { name: 'Events', exact: true })).toBeVisible();
    await expect(page.getByRole('searchbox', { name: 'Search events', exact: true })).toBeVisible();
    await expect(page.locator('.results-count')).toHaveText('5 events');
    const topic = page.getByRole('combobox', { name: 'Topic', exact: true });
    await expect(topic).toHaveValue('');
    await expect(topic.locator('option')).toHaveText([
      'All topics', 'Cybersecurity', 'AI & Data', 'Cloud', 'DevOps',
      'Software Development', 'Networking & Systems', 'Community', 'General IT',
    ]);

    const meetup = page.locator('.event-card').filter({ has: page.getByRole('heading', { includeHidden: true, name: data.events[1].name, exact: true }) });
    await expect(meetup).toBeVisible();
    await expect(meetup.locator('.notice-select')).toBeEnabled();
    await expect(meetup.locator('.event-date')).toContainText('2037');
    await selectPaper(meetup);
    await expect(page.locator('.paper .dates dt')).toHaveText(['Starts', 'Ends']);
    await expect(meetup.locator('.event-topics')).toContainText('AI & Data');
    await expect(meetup.locator('.event-topics')).toContainText('Software Development');
    await expect(page.locator('.paper .dates')).not.toContainText('Competition');
    if (viewport.width <= 760) await page.getByRole('button', {name:'Back to the board'}).click();
    const legacy = page.locator('.event-card').filter({ has: page.getByRole('heading', { includeHidden: true, name: data.events[3].name, exact: true }) });
    await expect(legacy).toBeVisible();
    await expect(legacy.locator('.event-topics')).toHaveCount(0);

    await topic.selectOption('community');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name, data.events[4].name]);
    await expect(page.locator('.event-card').getByRole('heading', { name: data.events[1].name, exact: true })).toHaveCount(1);
    for (const tags of await page.locator('.event-topics').all()) {
      await expect(tags).toContainText('Community');
      await expect(tags).not.toContainText('Careers');
    }
    await topic.selectOption('cybersecurity');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[0].name]);
    await expect(page.locator('.event-topics')).toContainText('Cybersecurity');
    await expect(page.locator('.results-count')).toHaveText('1 event matching your filters');
    await topic.selectOption('ai_data');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await expect(page.locator('.event-card').getByRole('heading', { name: data.events[1].name, exact: true })).toHaveCount(1);
    await topic.selectOption('software_development');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name]);
    await expect(page.locator('.event-card').getByRole('heading', { name: data.events[1].name, exact: true })).toHaveCount(1);
    await expect(page.locator('.event-topics')).toContainText('AI & Data');
    await expect(page.locator('.event-topics')).toContainText('Software Development');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });

  test(`topic composes with every existing filter and reset on ${viewport.name}`, async ({ page }) => {
    const data = topicDirectory();
    await page.route('**/api/events', route => route.fulfill({ json: data }));
    await page.setViewportSize(viewport);
    await page.goto('/');
    const topic = page.getByRole('combobox', { name: 'Topic', exact: true });
    const format = page.getByRole('combobox', { name: 'Format', exact: true });
    await expect(page.getByRole('combobox', { name: 'Region', exact: true })).toHaveCount(0);
    const registration = page.getByRole('combobox', { name: 'Registration', exact: true });
    const search = page.getByRole('searchbox', { name: 'Search events', exact: true });
    await topic.selectOption('ai_data');
    await format.selectOption('in_person');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name]);
    await expect(page.locator('.event-card').getByRole('heading', { name: data.events[2].name, exact: true })).toHaveCount(0);
    await registration.selectOption('open');
    await search.fill('Community');
    await expect(page.locator('.results-count')).toHaveText('1 event matching your filters');
    await expect(page.getByRole('tab', { name: /Upcoming & live/ }).locator('span')).toHaveText('1');
    await registration.selectOption('unknown');
    await expect(page.locator('.event-card')).toHaveCount(0);
    await registration.selectOption('open');
    await search.fill('no matching community here');
    await expect(page.locator('.event-card')).toHaveCount(0);
    await search.fill('Community');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name]);

    await topic.selectOption('');
    await expect(format).toHaveValue('in_person');
    await expect(registration).toHaveValue('open');
    await expect(search).toHaveValue('Community');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name, data.events[3].name]);
    await expect(page.locator('.results-count')).toHaveText('2 events matching your filters');
    await expect(page.getByRole('tab', { name: /Upcoming & live/ }).locator('span')).toHaveText('2');
    await topic.selectOption('cybersecurity');
    await expect(page.locator('.event-card')).toHaveCount(0);
    await expect(page.locator('.results-count')).toHaveText('0 events matching your filters');
    await expect(page.getByRole('heading', { name: 'No matches for these filters.' })).toBeVisible();
    await expect(page.locator('.empty')).toContainText(/topic/i);
    await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click();
    for (const filter of [topic, format, registration, search]) await expect(filter).toHaveValue('');
    await expect(page.locator('.event-card')).toHaveCount(5);
    await expect(page.locator('.results-count')).toHaveText('5 events');
    await page.getByRole('tab', { name: /Watchlist/ }).click();
    await expect(page.locator('.results-count')).toHaveText('0 events');
    await expect(page.getByRole('heading', { name: 'No watchlist events recorded yet.' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}

for (const viewport of [{ name: 'desktop', width: 1440, height: 1000 }, { name: 'mobile', width: 390, height: 844 }]) {
  test(`compact rows expose decisions and select from the keyboard on ${viewport.name}`, async ({ page }) => {
    const data = topicDirectory();
    const base = data.events[1];
    const moment = (value: string) => ({ raw: value, value, precision: 'datetime', timezone: 'UTC' });
    const events = [
      { ...base, id: 'compact-paid', name: 'A developer gathering with a deliberately long official title about practical AI applications and sharing projects with local peers',
        description: 'Build practical AI applications, meet local developers and share projects.',
        price: { kind: 'paid', currency: 'PHP', amount: 500 }, registration_status: 'waitlisted',
        start: moment('2037-05-10T16:30:00Z'), end: moment('2037-05-11T02:00:00Z') },
      { ...base, id: 'compact-unknown', name: 'Gathering with an unconfirmed schedule', registration_status: 'unknown',
        start: null, end: null, price: { kind: 'unknown' }, topics: [], summary: null },
      { ...base, id: 'compact-submit', name: 'Ongoing student security challenge', status: 'live',
        topic: 'cybersecurity', topics: ['cybersecurity'], format: 'online', price: { kind: 'free', amount: 0 },
        start: moment('2037-05-01T00:00:00Z'), end: moment('2037-05-12T16:00:00Z'),
        deadline: null, submission_deadline: moment('2037-05-12T16:00:00Z') },
      { ...base, id: 'compact-register', name: 'Developer social with a registration cutoff', topics: ['community'],
        deadline: moment('2037-05-11T15:00:00Z'), submission_deadline: null },
    ];
    await page.route('**/api/events', route => route.fulfill({ json: { ...data, events } }));
    await page.setViewportSize(viewport);
    await page.goto('/');
    const cards = page.locator('.event-card');
    await expect(cards).toHaveCount(4);
    await expect(page.locator('.event-card .event-detail-body')).toHaveCount(0);
    await expect(page.locator('.event-card .state-scheduled')).toHaveCount(0);
    await expect(page.getByRole('combobox', { name: 'Region', exact: true })).toHaveCount(0);
    const byName = (name: string) => cards.filter({ has: page.getByRole('heading', { includeHidden: true, name, exact: true }) });
    const paid = byName(events[0].name);
    const preview = paid.locator('.event-preview');
    await expect(preview).toContainText(events[0].name);
    await expect(preview).toContainText('Example community');
    await expect(preview).toContainText('NCR');
    await expect(preview).toContainText('AI & Data');
    await expect(preview).toContainText('Community');
    await expect(preview).toContainText('Paid');
    await expect(preview).toContainText('Waitlisted');
    await expect(preview).not.toContainText('Unknown');
    // 16:30 UTC on May 10 is already May 11 in Manila. The preview keeps date precision.
    await expect(paid.locator('.event-date')).toHaveAttribute('aria-label', /Starts May 11, 2037 \(Asia\/Manila\)/);
    await expect(paid.locator('.event-date')).not.toContainText(/\d:\d|PHT/);
    await expect(paid.locator('.dates')).toHaveCount(0);
    await expect(paid.locator('.actions')).toHaveCount(0);

    const unknown = byName(events[1].name);
    await expect(unknown.locator('.event-date')).toHaveText('Date unconfirmed');
    await expect(unknown.locator('.event-preview .registration')).toHaveCount(0);
    await expect(unknown.locator('.preview-facts')).not.toBeVisible();
    await expect(unknown.locator('.event-preview')).not.toContainText(/Unknown|Register by|Submit by/);
    const ongoing = byName(events[2].name).locator('.event-preview');
    await expect(ongoing).toContainText('Free');
    await expect(ongoing).toContainText(/Submit by.*May 13, 2037/);
    await expect(ongoing).not.toContainText('Register by');
    const registration = byName(events[3].name).locator('.event-preview');
    await expect(registration).toContainText(/Register by.*May 11, 2037/);
    await expect(registration).not.toContainText('Submit by');

    await cards.first().evaluate(element => element.scrollIntoView({ block: 'start', behavior: 'instant' }));
    const boxes = await cards.evaluateAll(elements => elements.map(element => {
      const { x, y, width, height } = element.getBoundingClientRect();
      return { x, y, width, height };
    }));
    // Rows stay in one column and at least two can be read without expanding anything.
    expect(new Set(boxes.map(box => Math.round(box.x))).size).toBe(1);
    expect(new Set(boxes.map(box => Math.round(box.width))).size).toBe(1);
    expect(boxes.filter(box => box.y >= 0 && box.y + box.height <= viewport.height).length).toBeGreaterThanOrEqual(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();

    const control = paid.locator('.notice-select');
    await expect(control).toHaveAccessibleName(events[0].name);
    await control.focus();
    await page.keyboard.press('Enter');
    await expect(control).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.paper .dates')).toContainText(/12:30\s*am PHT/i);
    await expect(page.locator('.paper')).toContainText(events[0].description);
    await expect(page.locator('.paper')).toContainText('Open to students.');
    await expect(page.locator('.paper .actions a').first()).toBeVisible();
    if (viewport.width <= 760) await page.getByRole('button', {name:'Back to the board'}).click();
    await unknown.locator('.notice-select').focus();
    await page.keyboard.press('Space');
    await expect(unknown.locator('.notice-select')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.paper')).toContainText('Registration unconfirmed');
    await expect(page.locator('.paper .facts')).toContainText('Unknown');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}

test('real collected listings, filters, history, and source health', async ({ page, request }) => {
  const response = await request.get('/api/events');
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /The Tech Board/ })).toBeVisible();
  const upcoming = data.events.filter((e: {section: string}) => e.section === 'upcoming');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.length);
  if (upcoming.length) {
    const card = page.locator('.event-card').first();
    await selectPaper(card);
    await expect(page.locator('.paper .actions a').first()).toHaveAttribute('href', /^https?:\/\//);
    await page.locator('.paper .history > summary').click();
    await expect(page.locator('.paper .history-link').first()).toBeVisible();
  }
  await page.getByRole('searchbox').fill('not-a-real-event-abcdef');
  await expect(page.getByRole('heading', { name: 'No matches for these filters.' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).first().click();
  await page.getByRole('combobox', { name: 'Format', exact: true }).selectOption('online');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.filter((e: {format: string}) => e.format === 'online').length);
  await page.getByRole('combobox', { name: 'Format', exact: true }).selectOption('');
  await page.getByRole('combobox', { name: 'Registration', exact: true }).selectOption('open');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.filter((e: {registration_status: string}) => e.registration_status === 'open').length);
  await page.getByRole('combobox', { name: 'Registration', exact: true }).selectOption('');
  await page.getByRole('tab', { name: /Past & finished/ }).click();
  await expect(page.locator('.event-card')).toHaveCount(data.events.filter((e: {section: string}) => ['past', 'finished'].includes(e.section)).length);
  await page.getByRole('link', { name: 'Our sources' }).click();
  await expect(page.locator('.source-row')).toHaveCount(data.sources.length);
  for (const status of new Set(data.sources.map((source: {status: string}) => source.status))) {
    await expect(page.locator(`.source-row .health-${status}`)).toHaveCount(data.sources.filter((source: {status: string}) => source.status === status).length);
  }
  expect(errors).toEqual([]);
});

test('linked post discovery stays separate from fetched evidence (browser-only fixture)', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const article = 'https://university.example/news/campus-ctf';
  const post = 'https://www.facebook.com/story.php?id=222&story_fbid=333';
  const evidence = {name:{url:article,quote:'Example Campus CTF 2028'}};
  const event = {...live.events[0], id:'discovery-ui-fixture', name:'TEST FIXTURE • Discovery', section:'upcoming',
    field_evidence:evidence, announcements:[{...live.events[0].announcements[0], url:article,
      title:'Example Campus CTF 2028', discovery_path:['https://university.example/feed/',article],
      related_links:[{url:post,label:'Facebook announcement',access:'linked_only',discovered_on:article}],
      field_evidence:evidence}]};
  await page.route('**/api/events', route => route.fulfill({json:{...live,events:[event]}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await selectPaper(page.locator('.event-card').first());
  await page.locator('.history > summary').click();
  await expect(page.getByText('Linked only · Full post not accessed')).toBeVisible();
  await expect(page.locator('.related-links .history-link')).toHaveAttribute('href',post);
  await expect(page.locator('.field-evidence')).toContainText('Example Campus CTF 2028');
  await page.getByText('How this announcement was found').click();
  await expect(page.locator('.discovery-path')).toContainText('https://university.example/feed/');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('search discovery labels and original queries are visible (browser-only fixture)', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const url = 'https://facebook.com/example/posts/333';
  const queries = ['Philippines cybersecurity CTF competition', 'site:facebook.com Philippines CTF registration'];
  const event = {...live.events[0], id:'search-ui-fixture', name:'TEST FIXTURE • Search discovery',
    section:'upcoming', organizer:'Organizer unconfirmed', announcement_url:url,
    announcement_label:'Search result · verify source', field_evidence:{},
    announcements:[{...live.events[0].announcements[0], url, access:'search_only',
      title:'Example CTF 2031', source_name:'Generic search', evidence:null, related_links:[],
      discovery_path:['https://search.example/',url], discovery_query:queries[0], discovery_queries:queries}]};
  await page.route('**/api/events', route => route.fulfill({json:{...live,events:[event]}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await selectPaper(page.locator('.event-card').first());
  await expect(page.locator('.actions .primary')).toContainText('Search result · verify source');
  await expect(page.locator('.paper > .organizer')).toHaveText('Organizer unconfirmed');
  await page.locator('.history > summary').click();
  await expect(page.getByText('Search result only', {exact:true})).toBeVisible();
  await page.getByText('How this announcement was found').click();
  await expect(page.locator('.discovery-path q')).toHaveText(queries);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('mobile layout fits viewport and tabs work from keyboard', async ({ page }) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.locator('.event-card').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole('tab', {name:/Upcoming & live/}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/All events/})).toHaveAttribute('aria-selected','true');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Past & finished/})).toHaveAttribute('aria-selected','true');
  await page.getByRole('link',{name:'Our sources'}).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('date precision, cancellation, and error recovery render correctly (browser-only fixture)', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const event = {...live.events[0], id:'ui-fixture', name:'TEST FIXTURE • Date precision', status:'cancelled', section:'upcoming', registration_status:'closed', start:{raw:'November 21, 2026',value:'2026-11-21',precision:'date',timezone:null},end:{raw:'2026-11-21T01:00:00Z',value:'2026-11-21T01:00:00Z',precision:'datetime',timezone:'UTC'},deadline:null,notices:[]};
  let fails = true;
  await page.route('**/api/events', async route => {
    if (fails) await route.fulfill({status:503,body:'unavailable'});
    else await route.fulfill({json:{...live,events:[event]}});
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toBeVisible();
  fails = false;
  await page.getByRole('button',{name:'Try again'}).click();
  await expect(page.locator('.event-card').getByText('Cancelled',{exact:true})).toBeVisible();
  await selectPaper(page.locator('.event-card').first());
  const dates = page.locator('.dates');
  await expect(dates).toContainText('November 21, 2026');
  await expect(dates).toContainText('9:00');
  await expect(dates).toContainText('PHT');
  await expect(dates).not.toContainText('12:00');
});

test('past dates, future teasers, and undated search leads stay distinct (browser-only fixture)', async ({ page }) => {
  const article = 'https://university.example/announcements/security-tournament';
  const base = {
    id:'classification-fixture', name:'TEST FIXTURE • Campus Security Tournament', organizer:'Example university',
    region:'NCR', format:'online', eligibility:null, announcement_url:article, registration_url:null,
    registration_status:'unknown', status:'past_date', section:'past',
    competition_date:{raw:'February 14, 2024',value:'2024-02-14',precision:'date',timezone:null},
    start:null, end:null, deadline:null, registration_opens:null, posted_at:'2024-01-03',
    first_seen:'2026-11-22T00:00:00Z', last_checked:'2026-11-22T00:00:00Z', summary:null,
    stage:'main', edition:'2024', notices:[], announcements:[],
  };
  const events = [base,
    {...base,id:'teaser-fixture',name:'TEST FIXTURE • Future teaser',status:'schedule_tba',section:'upcoming',
      competition_date:null,posted_at:'2026-11-22',edition:'2027'},
    {...base,id:'undated-fixture',name:'TEST FIXTURE • Undated lead',status:'undated_lead',section:'upcoming',
      competition_date:null,posted_at:null,edition:'',announcement_label:'Search result · verify source'},
    {...base,id:'completed-fixture',name:'TEST FIXTURE • Completed tournament',status:'finished',section:'finished',
      registration_status:'closed'},
  ];
  await page.route('**/api/events', route => route.fulfill({json:{events,sources:[],generated_at:'2026-11-22T00:00:00Z'}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(2);
  await expect(page.locator('.event-card').getByRole('heading', { name: base.name})).toHaveCount(0);
  await expect(page.locator('.event-schedule_tba .event-date')).toHaveText('Date unconfirmed');
  await expect(page.locator('.event-undated_lead .event-date')).toHaveText('Date unconfirmed');
  await selectPaper(page.locator('.event-undated_lead'));
  await expect(page.locator('.paper .dates')).toContainText('Not confirmed');
  await expect(page.locator('.paper .dates')).not.toContainText('Schedule TBA');
  await page.getByRole('tab',{name:/Past & finished/}).click();
  await expect(page.locator('.event-card')).toHaveCount(2);
  const past = page.locator('.event-past_date');
  await selectPaper(past);
  await expect(past.locator('.badge')).toHaveText('Past date · completion unconfirmed');
  await expect(page.locator('.paper .registration > strong')).toHaveText('Registration unconfirmed');
  await expect(page.locator('.paper .dates dt')).toHaveText(['Starts', 'Ends']);
  await expect(page.locator('.paper .dates')).toContainText('February 14, 2024');
  await expect(page.locator('.paper .dates')).not.toContainText('12:00');
  await expect(page.locator('.event-finished .state-finished')).toHaveText('Finished');
  await page.getByRole('combobox',{name:'Registration',exact:true}).selectOption('unknown');
  await expect(page.locator('.event-card')).toHaveCount(1);
  await expect(page.locator('.event-past_date')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});


test('conflicting dates stay visible outside Upcoming and Past (browser-only fixture)', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const event = {...live.events[0], id:'conflicting-date-fixture', name:'TEST FIXTURE • Conflicting dates',
    status:'date_conflict', section:'unconfirmed', registration_status:'unknown', competition_date:null,
    start:null, end:null, summary:'Conflicting competition dates in the source. Schedule unconfirmed.',
    notices:['Conflicting competition dates: November 4, 2026, December 4, 2026. The schedule is unconfirmed; verify with the organizer.'],
    field_evidence:{date_conflicts:{url:'https://organizer.example/event',
      quote:'Tournament date: November 4, 2026; Tournament date: December 4, 2026'}}};
  await page.route('**/api/events', route => route.fulfill({json:{...live,events:[event]}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(0);
  await page.getByRole('tab',{name:/Past & finished/}).click();
  await expect(page.locator('.event-card')).toHaveCount(0);
  await page.getByRole('tab',{name:/Date unconfirmed/}).click();
  await expect(page.locator('.event-card')).toHaveCount(1);
  await expect(page.locator('.state-date_conflict')).toHaveText('Conflicting dates');
  await selectPaper(page.locator('.event-card').first());
  await expect(page.locator('.notices')).toContainText('November 4, 2026, December 4, 2026');
  await expect(page.locator('.dates')).not.toContainText('December 4');
  await page.locator('.history > summary').click();
  await expect(page.locator('.history > .field-evidence')).toContainText('Conflicting date evidence');
  await page.getByRole('tab',{name:/Date unconfirmed/}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Watchlist/})).toHaveAttribute('aria-selected','true');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Archived leads/})).toHaveAttribute('aria-selected','true');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Upcoming & live/})).toHaveAttribute('aria-selected','true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('watchlisted leads are absent from Upcoming and remain inspectable', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const event = {...live.events[0], id:'watchlist-ui-fixture', name:'TEST FIXTURE • Undated lead',
    section:'watchlist', status:'schedule_tba', registration_status:'unknown',
    start:null, end:null, competition_date:null, deadline:null, submission_deadline:null,
    notices:['Watchlist: no confirmed start or cutoff in the next 45 days, or recurring signup is unverified.']};
  await page.route('**/api/events', route => route.fulfill({json:{...live,events:[event]}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(0);
  await page.getByRole('tab',{name:/Watchlist/}).click();
  await expect(page.locator('.event-card')).toHaveCount(1);
  await selectPaper(page.locator('.event-card').first());
  await expect(page.locator('.notices')).toContainText('no confirmed start or cutoff');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('general IT editions have an international group and separate participation facts (browser-only fixture)', async ({ page }) => {
  const base = {
    id:'ctf-ui-fixture', name:'TEST FIXTURE • Campus CTF', organizer:'Example campus', region:'NCR',
    format:'online', eligibility:'Campus students', announcement_url:'https://campus.example/ctf',
    registration_url:null, registration_status:'unknown', status:'scheduled', section:'upcoming',
    start:{raw:'2032-12-09T02:00:00Z',value:'2032-12-09T02:00:00Z',precision:'datetime',timezone:'UTC'},
    end:{raw:'2032-12-09T08:00:00Z',value:'2032-12-09T08:00:00Z',precision:'datetime',timezone:'UTC'},
    deadline:null, registration_opens:null, posted_at:null, first_seen:'2032-11-22T00:00:00Z',
    last_checked:'2032-11-22T00:00:00Z', summary:null, stage:'main', edition:'2032', notices:[], announcements:[],
  };
  const international = {...base, id:'general-it-ui-fixture', name:'TEST FIXTURE • Global learning edition',
    organizer:'Major League Hacking', region:'Worldwide', geography:'international_online', topic:'general_it', topics:['general_it'],
    announcement_url:'https://calendar.example/events/learning-edition', registration_url:'https://signup.example/events/42',
    registration_status:'open', eligibility:'Worldwide, including university students; conditions apply to minors.',
    start:{raw:'2032-12-03T10:00:00-05:00',value:'2032-12-03T10:00:00-05:00',precision:'datetime',timezone:'UTC-05:00'},
    end:{raw:'2032-12-09T13:00:00-05:00',value:'2032-12-09T13:00:00-05:00',precision:'datetime',timezone:'UTC-05:00'},
    price:{kind:'free',amount:0}, account_required:true, submission_deadline:null,
  };
  await page.route('**/api/events', route => route.fulfill({json:{events:[international,base],sources:[],generated_at:'2032-11-22T00:00:00Z'}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  const group = page.getByRole('region',{name:'International online opportunities'});
  const card = group.locator('.event-card');
  await expect(group.getByRole('heading',{name:'International online opportunities'})).toBeVisible();
  await expect(card).toHaveCount(1);
  await expect(card.getByRole('heading',{name:international.name})).toBeVisible();
  await expect(card.locator('.event-preview')).toContainText('General IT');
  await selectPaper(card);
  await expect(page.locator('.paper .facts')).toContainText('Free');
  await expect(page.locator('.paper .facts')).toContainText('Required to register');
  await expect(page.locator('.paper .facts')).toContainText(international.eligibility);
  await expect(page.locator('.paper .registration > strong')).toHaveText('Registration open');
  await expect(page.locator('.paper .registration dl > div').filter({hasText:'Registration deadline'})).toHaveText('Registration deadlineUnknown');
  await expect(page.locator('.paper .registration dl > div').filter({hasText:'Submission deadline'})).toHaveText('Submission deadlineUnknown');
  await expect(page.locator('.paper .dates')).toContainText('Starts');
  await expect(page.locator('.paper .dates')).toContainText('Ends');
  await expect(page.locator('.paper .dates')).toContainText('Dec 10, 2032');
  await expect(page.locator('.paper .dates')).toContainText(/2:00\s*am PHT/i);
  await expect(page.locator('.paper .dates')).not.toContainText('Competition');
  await expect(page.locator('.paper').getByRole('link',{name:'Registration',exact:false})).toHaveAttribute('href',international.registration_url);
  const ctf = page.locator('.event-card').filter({has:page.getByRole('heading', { includeHidden: true, name: base.name})});
  await selectPaper(ctf);
  await expect(page.locator('.paper .dates')).toContainText('Starts');
  await expect(page.locator('.paper .registration dl > div').filter({hasText:'Submission deadline'})).toHaveText('Submission deadlineUnknown');
  await expect(page.locator('.paper .facts > div').filter({hasText:'Price'})).toHaveText('PriceUnknown');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('a PH hybrid AI event keeps public applications separate from restricted tickets (browser-only fixture)', async ({ page }) => {
  const event = {
    id:'hybrid-ai-ui-fixture', name:'TEST FIXTURE • Community AI demonstrations', organizer:'Example AI community',
    region:'NCR', geography:'PH', topic:'ai', topics:['ai_data'], format:'hybrid',
    eligibility:'Standard tickets are open to the public; organizer approval required. Fellow/member restrictions apply only to their named tickets.',
    attendance_options:['Onsite — Quezon City','Online'],
    announcement_url:'https://luma.com/synthetic-ai-event', registration_url:'https://luma.com/synthetic-ai-event',
    registration_status:'approval_required', status:'scheduled', section:'upcoming',
    start:{raw:'2032-12-05T07:00:00Z',value:'2032-12-05T15:00:00+08:00',precision:'datetime',timezone:'Asia/Manila'},
    end:{raw:'2032-12-05T10:00:00Z',value:'2032-12-05T18:00:00+08:00',precision:'datetime',timezone:'Asia/Manila'},
    price:{kind:'unknown'}, deadline:null, registration_opens:null, posted_at:null, account_required:null,
    first_seen:'2032-11-22T00:00:00Z', last_checked:'2032-11-22T00:00:00Z',
    summary:null, stage:'main', edition:'synthetic-ai', notices:[], announcements:[],
    ticket_options:[
      {name:'Standard - Onsite',access:'public',eligibility:'Open to the public.',attendance:'onsite',registration_state:'approval_required',price:{kind:'unknown'},deadline:null},
      {name:'Standard - Online',access:'public',eligibility:'Open to the public.',attendance:'online',registration_state:'approval_required',price:{kind:'unknown'},deadline:null},
      {name:'Fellows - Onsite',access:'restricted',eligibility:'Only for fellows who completed the training.',attendance:'onsite',registration_state:'approval_required',price:{kind:'unknown'},deadline:null},
    ],
  };
  await page.route('**/api/events', route => route.fulfill({json:{events:[event],sources:[],generated_at:'2032-11-22T00:00:00Z'}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  const ph = page.getByRole('region',{name:'PH opportunities'});
  const card = ph.locator('.event-card');
  await expect(card).toHaveCount(1);
  await expect(page.getByRole('region',{name:'International online opportunities'})).toHaveCount(0);
  await expect(card.locator('.event-preview')).toContainText('Hybrid');
  await expect(card.locator('.event-preview')).toContainText(/approval required/i);
  await expect(card.locator('.event-preview')).toContainText('AI & Data');
  await selectPaper(card);
  await expect(page.locator('.paper .registration > strong')).toHaveText('Applications open · approval required');
  await expect(page.locator('.paper .registration dl > div').filter({hasText:'Registration deadline'})).toHaveText('Registration deadlineUnknown');
  await expect(page.locator('.paper .facts > div').filter({hasText:'Attendance'})).toHaveText('AttendanceOnsite — Quezon City · Online');
  await expect(page.locator('.paper .facts > div').filter({hasText:'Price'})).toHaveText('PriceUnknown');
  await expect(page.locator('.paper .facts > div').filter({hasText:'Account'})).toHaveText('AccountUnknown');
  await expect(page.locator('.paper .dates')).toContainText('Starts');
  await expect(page.locator('.paper .dates')).not.toContainText('Competition');
  const publicTickets = page.locator('.paper .ticket-options > div').filter({has:page.getByRole('heading',{includeHidden:true,name:'Standard public tickets'})});
  const restrictedTickets = page.locator('.paper .ticket-options > div').filter({has:page.getByRole('heading',{includeHidden:true,name:'Restricted tickets',exact:true})});
  await expect(publicTickets.locator('li')).toHaveCount(2);
  await expect(publicTickets).toContainText('Standard - Onsite');
  await expect(publicTickets).toContainText('Standard - Online');
  await expect(publicTickets).not.toContainText('completed the training');
  await expect(restrictedTickets.locator('li')).toHaveCount(1);
  await expect(restrictedTickets).toContainText('Only for fellows who completed the training.');
  await expect(page.locator('.paper').getByRole('link',{name:'Registration',exact:false})).toHaveAttribute('href',event.registration_url);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('event dates precede registration status in listing order', async ({ page }) => {
  const live = topicDirectory();
  const base = {...live.events[0], section:'upcoming', geography:'PH', status:'scheduled', notices:[]};
  const day = (value:string) => ({raw:value,value,precision:'date',timezone:null});
  const events = [
    {...base,id:'unconfirmed-early',name:'TEST FIXTURE • Unconfirmed early event',registration_status:'unknown',start:day('2035-12-01')},
    {...base,id:'approval-next',name:'TEST FIXTURE • Public application',registration_status:'approval_required',start:day('2035-12-02')},
    {...base,id:'open-later',name:'TEST FIXTURE • Open registration',registration_status:'open',start:day('2035-12-03')},
  ];
  await page.route('**/api/events', route => route.fulfill({json:{...live,events}}));
  await page.goto('/');
  await expect(page.locator('.event-card h3')).toHaveText([events[0].name,events[1].name,events[2].name]);
  await selectPaper(page.locator('.event-card').nth(1));
  await expect(page.locator('.paper .registration > strong')).toHaveText('Applications open · approval required');
});

test('event dates precede free pricing in listing order', async ({ page }) => {
  const live = topicDirectory();
  const base = {...live.events[0], section:'upcoming', geography:'international_online', status:'scheduled', registration_status:'open', notices:[]};
  const day = (value:string) => ({raw:value,value,precision:'date',timezone:null});
  const events = [
    {...base,id:'unknown-earlier',name:'TEST FIXTURE • Unknown fee',price:{kind:'unknown'},start:day('2035-12-01')},
    {...base,id:'free-later',name:'TEST FIXTURE • Verified free',price:{kind:'free',amount:0},start:day('2035-12-02')},
  ];
  await page.route('**/api/events', route => route.fulfill({json:{...live,events}}));
  await page.goto('/');
  await expect(page.locator('.event-card h3')).toHaveText([events[0].name,events[1].name]);
});

test('AI and cybersecurity cards show submission cutoffs separately from registration and event end', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const base = {...live.events[0], section:'upcoming', geography:'international_online', status:'live',
    registration_status:'open', deadline:null, notices:[], summary:null, ticket_options:[]};
  const date = (value:string) => ({raw:value,value,precision:'datetime',timezone:'UTC'});
  const events = ['ai','cybersecurity'].map(topic => ({...base,id:`typed-cutoff-${topic}`, topic,
    name:`TEST FIXTURE • ${topic} submission`, start:date('2035-11-21T01:00:00Z'),
    end:date('2035-12-03T12:00:00Z'), submission_deadline:date('2035-12-01T16:00:00Z')}));
  await page.route('**/api/events', route => route.fulfill({json:{...live,events}}));
  await page.goto('/');
  for (const event of events) {
    const card = page.locator('.event-card').filter({has:page.getByRole('heading', { includeHidden: true, name: event.name})});
    await expect(card.locator('.event-preview')).toContainText('Submit by');
    await expect(card.locator('.event-preview')).not.toContainText('Register by');
    await selectPaper(card);
    await expect(page.locator('.paper .registration dl > div').filter({hasText:'Registration deadline'})).toHaveText('Registration deadlineUnknown');
    const cutoff = page.locator('.paper .registration dl > div').filter({hasText:'Submission deadline'});
    await expect(cutoff).toContainText('Dec 2, 2035');
    await expect(cutoff).toContainText(/12:00\s*am PHT/i);
    await expect(page.locator('.paper .dates')).toContainText('Dec 3, 2035');
  }
});

for (const [layout, width] of [['desktop', 1366], ['mobile', 390]] as const) {
  test(`All events includes every section once and composes with filters on ${layout}`, async ({ page }) => {
    const data = topicDirectory();
    const events = [...data.events,
      { ...data.events[0], id: 'past-cyber', name: 'Past security competition', section: 'past', status: 'past_date', format: 'in_person', registration_status: 'closed' },
      { ...data.events[0], id: 'watch-cyber', name: 'Hack4Gov regional lead', section: 'watchlist', status: 'undated_lead', format: 'unknown', registration_status: 'unknown' },
      { ...data.events[3], id: 'date-unknown', name: 'Schedule pending meetup', section: 'unconfirmed', status: 'date_conflict', registration_status: 'unknown' },
    ];
    await page.route('**/api/events', route => route.fulfill({ json: { ...data, events } }));
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
    await expect(page.locator('.event-card')).toHaveCount(5);
    const all = page.getByRole('tab', { name: /All events/ });
    await expect(all).toContainText('8');
    await all.click();
    await expect(page.locator('.event-card')).toHaveCount(8);
    expect(new Set(await page.locator('.event-card h3').allTextContents()).size).toBe(8);
    await expect(page.locator('.results-count')).toContainText('8 events');
    await page.getByRole('combobox', { name: 'Topic', exact: true }).selectOption('cybersecurity');
    await expect(page.locator('.event-card')).toHaveCount(3);
    await expect(all).toContainText('3');
    await expect(page.getByRole('heading', { name: 'Hack4Gov regional lead', exact: true })).toBeVisible();
    await page.getByRole('combobox', { name: 'Format', exact: true }).selectOption('in_person');
    await expect(page.locator('.event-card')).toHaveCount(1);
    await page.getByRole('combobox', { name: 'Registration', exact: true }).selectOption('open');
    await expect(page.locator('.event-card')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'No matches for these filters.' })).toBeVisible();
    await expect(page.locator('.results-count')).toContainText('0 events matching your filters');
    await page.getByRole('combobox', { name: 'Topic', exact: true }).selectOption('');
    await expect(page.getByRole('combobox', { name: 'Format', exact: true })).toHaveValue('in_person');
    await expect(page.getByRole('combobox', { name: 'Registration', exact: true })).toHaveValue('open');
    await expect(all).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('.event-card')).toHaveCount(3);
    await page.getByRole('searchbox').fill('App-building');
    await expect(page.locator('.event-card')).toHaveCount(1);
    await page.getByRole('tab', { name: /Upcoming & live/ }).click();
    await expect(page.locator('.event-card')).toHaveCount(1);
    await all.click();
    await expect(page.getByRole('searchbox')).toHaveValue('App-building');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  });
}

test('All events has a truthful empty-directory message', async ({ page }) => {
  await page.route('**/api/events', route => route.fulfill({ json: { events: [], sources: [], generated_at: '2037-05-01T00:00:00Z' } }));
  await page.goto('/');
  await page.getByRole('tab', { name: /All events/ }).click();
  await expect(page.getByRole('heading', { name: 'No events recorded yet.', exact: true })).toBeVisible();
  await expect(page.locator('.results-count')).toContainText('0 events');
});

for (const width of [1366, 390]) {
  test(`directory controls and completion messages stay below the board at ${width}px`, async ({page}) => {
    const data = topicDirectory();
    let reads = 0;
    let failRefresh = false;
    let posts = 0;
    await page.route('**/api/events', route => {
      reads++;
      return failRefresh ? route.fulfill({status:503,body:'unavailable'}) : route.fulfill({json:{...data,manual_collection:{enabled:true,token:'fixture-token'}}});
    });
    await page.route('**/api/collection', route => {
      if (route.request().method() === 'POST') posts++;
      return route.fulfill({json:{...collectionFixture('completed',3,'Saved the latest public events.'),warning_count:1}});
    });
    await page.setViewportSize({width,height:900});
    await page.goto('/');
    const panel = page.getByRole('region',{name:'Directory updates'});
    await expect(panel.locator('.collection-status')).toContainText('Fetch complete');
    await expect(panel.getByRole('button',{name:'Fetch events',exact:true})).toBeEnabled();
    await expect(page.locator('.board .results-heading, .board .result-tools, .board .collection-status')).toHaveCount(0);
    await expect(page.locator('.board').getByRole('heading',{name:'Upcoming & live',exact:true})).toHaveCount(0);
    await expect(page.getByRole('tab',{name:/Upcoming & live/})).toContainText('5');
    const coverageBox = await page.locator('.coverage').boundingBox();
    const panelBox = await panel.boundingBox();
    expect(panelBox!.y).toBeGreaterThanOrEqual(coverageBox!.y + coverageBox!.height);
    await panel.scrollIntoViewIfNeeded();
    await page.screenshot({path:test.info().outputPath('directory-updates.png')});
    const before = reads;
    await panel.getByRole('button',{name:'Refresh saved listings'}).click();
    await expect.poll(() => reads).toBe(before + 1);
    expect(posts).toBe(0);
    failRefresh = true;
    await panel.getByRole('button',{name:'Refresh saved listings'}).click();
    await expect(panel.getByRole('alert')).toContainText('Previous results are still shown');
    await expect(page.locator('.event-card')).toHaveCount(5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}

for (const width of [1366, 390]) {
  test(`listing freshness is visible on arrival and uses source success time at ${width}px`, async ({page}) => {
    const data = topicDirectory();
    const source = {id:'latest',name:'Example source',url:'https://organizer.example',kind:'website',status:'error',last_success:'2026-11-23T13:07:00Z',last_attempt:'2026-11-24T02:00:00Z',message:'Fetch failed',discovered:0,accepted:0};
    let successes: (string | null)[] = [source.last_success,'2026-11-23T20:00:00+08:00',null];
    let reads = 0;
    await page.route('**/api/events', route => {
      reads++;
      return route.fulfill({json:{...data,generated_at:`2037-05-0${reads}T00:00:00Z`,sources:successes.map((last_success,index)=>({...source,id:`source-${index}`,last_success}))}});
    });
    await page.setViewportSize({width,height:900});
    await page.goto('/');
    const stamp = page.locator('.directory-updated');
    await expect(stamp).toBeInViewport();
    await expect(stamp).toContainText('Nov 23, 2026, 9:07 PM PHT');
    await expect(stamp.locator('time')).toHaveAttribute('datetime',source.last_success);
    await page.screenshot({path:test.info().outputPath('last-updated.png')});
    const initialReads = reads;
    await page.getByRole('button',{name:'Refresh saved listings',exact:true}).click();
    await expect.poll(()=>reads).toBe(initialReads + 1);
    await expect(stamp).toContainText('Nov 23, 2026, 9:07 PM PHT');
    successes = ['2026-11-24T01:00:00Z'];
    await page.getByRole('button',{name:'Refresh saved listings',exact:true}).click();
    await expect(stamp).toContainText('Nov 24, 2026, 9:00 AM PHT');
    successes = [null,'invalid','2026-11-24'];
    await page.getByRole('button',{name:'Refresh saved listings',exact:true}).click();
    await expect(stamp).toContainText('Not recorded yet');
    await expect(stamp.locator('time')).toHaveCount(0);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  });
}
