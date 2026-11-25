import {filterTrigger, chooseFilter, expectFilter} from './filter-helpers';
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

for (const viewport of [{ name: 'desktop', width: 1440, height: 1000 }, { name: 'mobile', width: 390, height: 844 }, { name: 'narrow phone', width: 320, height: 800 }]) {
  test(`brand and evidence-backed topic cards render on ${viewport.name}`, async ({ page }) => {
    const data = topicDirectory();
    await page.route('**/api/events', route => route.fulfill({ json: data }));
    await page.setViewportSize(viewport);
    await page.goto('/');
    await expect(page).toHaveTitle('Tech Board | CommunIT');
    await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href', '/communit.svg');
    const iconLoaded = await page.evaluate(async () => {
      const icon = new Image();
      icon.src = (document.querySelector('link[rel="icon"]') as HTMLLinkElement).href;
      await icon.decode();
      return icon.naturalWidth > 0 && icon.naturalHeight > 0;
    });
    expect(iconLoaded).toBe(true);
    await expect(page.locator('header .brand')).toHaveText('CommunIT');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Tech events');
    await expect(page.locator('.hero, .hero-description, .timezone')).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'CommunIT', exact: true })).toHaveAttribute('href', '#top');
    await expect(page.getByRole('img', { name: 'Philippines, Philippine Time' })).toHaveText('Philippines · PHT');
    await expect(page.locator('.country')).toBeVisible();
    await expect(page.locator('.board-logo')).toBeVisible();
    const geometry = await page.evaluate(() => {
      const nav = document.querySelector('.topbar')!.getBoundingClientRect();
      const brand = document.querySelector('.brand')!.getBoundingClientRect();
      const links = document.querySelector('.nav-links')!.getBoundingClientRect();
      const search = document.querySelector('.topbar input[type=search]')!.getBoundingClientRect();
      const h1 = document.querySelector('h1')!.getBoundingClientRect();
      return {searchInside:search.top>=nav.top && search.bottom<=nav.bottom, separate:brand.right < links.left,
        sameRow:Math.abs(brand.top+brand.height/2-links.top-links.height/2)<2,
        inside:links.right<=nav.right, hiddenHeading:h1.width<=1 && h1.height<=1,
        noOverflow:document.documentElement.scrollWidth<=innerWidth};
    });
    expect(geometry).toMatchObject({searchInside:true,separate:true,sameRow:true,inside:true,hiddenHeading:true,noOverflow:true});

    await expect(page.getByRole('link', { name: 'Events', exact: true })).toBeVisible();
    await expect(page.getByRole('searchbox', { name: 'Search events', exact: true })).toBeVisible();
    await expect(page.locator('.results-count')).toHaveText('5 events');
    const topic = filterTrigger(page, 'interest');
    await expectFilter(topic, '');
    await topic.click();
    await expect(page.locator('.filter-chip')).toHaveText([
      /All interests/, 'Cybersecurity', 'AI & Data', 'Cloud', 'DevOps', 'Software Development', 'Networking & Systems', 'Community', 'General IT',
    ]);
    await page.keyboard.press('Escape');

    const meetup = page.locator('.event-card').filter({ has: page.getByRole('heading', { includeHidden: true, name: data.events[1].name, exact: true }) });
    await expect(meetup).toBeVisible();
    await expect(meetup.locator('.notice-select')).toBeEnabled();
    await expect(meetup.locator('.event-date')).toContainText('2037');
    await selectPaper(meetup);
    await expect(page.locator('.paper .event-schedule')).not.toBeEmpty();
    await expect(meetup.locator('.event-topics')).toContainText('AI & Data');
    await expect(meetup.locator('.event-topics')).toContainText('Software Development');
    await expect(page.locator('.paper .event-schedule')).not.toContainText('Competition');
    if (viewport.width <= 760) await page.getByRole('button', {name:'Back to the board'}).click();
    const legacy = page.locator('.event-card').filter({ has: page.getByRole('heading', { includeHidden: true, name: data.events[3].name, exact: true }) });
    await expect(legacy).toBeVisible();
    await expect(legacy.locator('.event-topics')).toHaveCount(0);

    await chooseFilter(topic, 'community');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name, data.events[4].name]);
    await expect(page.locator('.event-card').getByRole('heading', { name: data.events[1].name, exact: true })).toHaveCount(1);
    for (const tags of await page.locator('.event-topics').all()) {
      await expect(tags).toContainText('Community');
      await expect(tags).not.toContainText('Careers');
    }
    await chooseFilter(topic, 'cybersecurity');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[0].name]);
    await expect(page.locator('.event-topics')).toContainText('Cybersecurity');
    await expect(page.locator('.results-count')).toHaveText('1 event matching your filters');
    await chooseFilter(topic, 'ai_data');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await expect(page.locator('.event-card').getByRole('heading', { name: data.events[1].name, exact: true })).toHaveCount(1);
    await chooseFilter(topic, 'software_development');
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
    const topic = filterTrigger(page, 'interest');
    const format = filterTrigger(page, 'attendance');
    await expect(page.getByRole('combobox', { name: 'Region', exact: true })).toHaveCount(0);
    await expect(page.getByRole('combobox', { name: 'Registration', exact: true })).toHaveCount(0);
    const search = page.getByRole('searchbox', { name: 'Search events', exact: true });
    await chooseFilter(topic, 'ai_data');
    await chooseFilter(format, 'in_person');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name]);
    await expect(page.locator('.event-card').getByRole('heading', { name: data.events[2].name, exact: true })).toHaveCount(0);
    await search.fill('Community');
    await expect(page.locator('.results-count')).toHaveText('1 event matching your filters');
    await expect(page.getByRole('tab', { name: /Upcoming/ }).locator('span')).toHaveText('1');
    await search.fill('no matching community here');
    await expect(page.locator('.event-card')).toHaveCount(0);
    await search.fill('Community');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name]);

    await chooseFilter(topic, '');
    await expectFilter(format, 'in_person');
    await expect(search).toHaveValue('Community');
    await expect(page.locator('.event-card h3')).toHaveText([data.events[1].name, data.events[3].name]);
    await expect(page.locator('.results-count')).toHaveText('2 events matching your filters');
    await expect(page.getByRole('tab', { name: /Upcoming/ }).locator('span')).toHaveText('2');
    await chooseFilter(topic, 'cybersecurity');
    await expect(page.locator('.event-card')).toHaveCount(0);
    await expect(page.locator('.results-count')).toHaveText('0 events matching your filters');
    await expect(page.getByRole('heading', { name: 'No matches for these filters.' })).toBeVisible();
    await expect(page.locator('.empty')).toContainText(/interest/i);
    await page.getByRole('button', { name: 'Clear filters', exact: true }).first().click();
    await expect(search).toHaveValue('');
    for (const filter of [topic, format]) await expectFilter(filter, '');
    await expect(page.locator('.event-card')).toHaveCount(5);
    await expect(page.locator('.results-count')).toHaveText('5 events');
    await page.getByRole('tab', { name: /Needs confirmation/ }).click();
    await expect(page.locator('.results-count')).toHaveText('0 events');
    await expect(page.getByRole('heading', { name: 'No events needing confirmation.' })).toBeVisible();
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
    await expect(page.locator('.paper .event-schedule')).toHaveText('May 11, 2037 · 12:30–10:00 AM PHT');
    await expect(page.locator('.paper')).toContainText(events[0].description);
    await expect(page.locator('.paper')).toContainText('Open to students.');
    await expect(page.locator('.paper .actions a').first()).toBeVisible();
    if (viewport.width <= 760) await page.getByRole('button', {name:'Back to the board'}).click();
    await unknown.locator('.notice-select').focus();
    await page.keyboard.press('Space');
    await expect(unknown.locator('.notice-select')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.paper')).not.toContainText('Registration unconfirmed');
    await expect(page.locator('.paper')).not.toContainText('Unknown');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}

test('real collected listings, filters, and original event links', async ({ page, request }) => {
  const response = await request.get('/api/events');
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Tech events', exact: true })).toBeVisible();
  const upcoming = data.events.filter((e: {section: string}) => e.section === 'upcoming');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.length);
  if (upcoming.length) {
    const card = page.locator('.event-card').first();
    await selectPaper(card);
    await expect(page.locator('.paper .actions a').first()).toHaveAttribute('href', /^https?:\/\//);
    await expect(page.locator('.paper .history, .paper .field-evidence')).toHaveCount(0);
    await expect(page.locator('.paper .actions .primary')).toContainText('View organizer’s page');
  }
  await page.getByRole('searchbox').fill('not-a-real-event-abcdef');
  await expect(page.getByRole('heading', { name: 'No matches for these filters.' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).first().click();
  await chooseFilter(filterTrigger(page, 'attendance'), 'online');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.filter((e: {format: string}) => e.format === 'online').length);
  await chooseFilter(filterTrigger(page, 'attendance'), '');
  await expect(page.getByRole('combobox', { name: 'Registration', exact: true })).toHaveCount(0);
  await expect(page.locator('.event-card')).toHaveCount(upcoming.length);
  await page.getByRole('tab', { name: /Past/ }).click();
  await expect(page.locator('.event-card')).toHaveCount(data.events.filter((e: {section: string}) => ['past', 'finished'].includes(e.section)).length);
  await expect(page.getByRole('link', { name: 'Our sources' })).toHaveCount(0);
  expect(data).not.toHaveProperty('sources');
  expect(data).not.toHaveProperty('manual_collection');
  expect(errors).toEqual([]);
});

test('linked-only evidence stays out of the public notice (browser-only fixture)', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const article = 'https://university.example/news/campus-ctf';
  const post = 'https://www.facebook.com/story.php?id=222&story_fbid=333';
  const evidence = {name:{url:article,quote:'Example Campus CTF 2028'}};
  const event = {...live.events[0], id:'discovery-ui-fixture', name:'TEST FIXTURE • Discovery', section:'upcoming', organizer_event_url:article, announcement_url:article, registration_url:null,
    field_evidence:evidence, announcements:[{...live.events[0].announcements[0], url:article,
      title:'Example Campus CTF 2028', discovery_path:['https://university.example/feed/',article],
      related_links:[{url:post,label:'Facebook announcement',access:'linked_only',discovered_on:article}],
      field_evidence:evidence}]};
  await page.route('**/api/events', route => route.fulfill({json:{...live,events:[event]}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await selectPaper(page.locator('.event-card').first());
  await expect(page.locator('.history, .field-evidence, .related-links')).toHaveCount(0);
  await expect(page.locator('.paper .actions a')).toHaveAttribute('href',article);
  await expect(page.locator(`a[href="${post}"]`)).toHaveCount(0);
  await expect(page.locator('.discovery-path')).toHaveCount(0);
  await expect(page.locator('a[href*="/feed/"]')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('search uncertainty remains visible while original queries stay internal (browser-only fixture)', async ({ page, request }) => {
  const live = await (await request.get('/api/events')).json();
  const url = 'https://facebook.com/example/posts/333';
  const queries = ['Philippines cybersecurity CTF competition', 'site:facebook.com Philippines CTF registration'];
  const event = {...live.events[0], id:'search-ui-fixture', name:'TEST FIXTURE • Search discovery',
    section:'upcoming', organizer:'Organizer unconfirmed', announcement_url:url, organizer_event_url:null, registration_url:null,
    notices:['Search result only. Full post was not accessed; confirm all details with the organizer.'],
    announcement_label:'Search result · verify source', field_evidence:{},
    announcements:[{...live.events[0].announcements[0], url, access:'search_only',
      title:'Example CTF 2031', source_name:'Generic search', evidence:null, related_links:[],
      discovery_path:['https://search.example/',url], discovery_query:queries[0], discovery_queries:queries}]};
  await page.route('**/api/events', route => route.fulfill({json:{...live,events:[event]}}));
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await selectPaper(page.locator('.event-card').first());
  await expect(page.locator('.actions .primary')).toHaveAttribute('href',url);
  await expect(page.locator('.actions .primary')).toContainText('View organizer’s page');
  await expect(page.locator('.paper > .organizer')).toHaveCount(0);
  await expect(page.locator('.notices')).toContainText('Search result only. Full post was not accessed');
  await expect(page.locator('.history')).toHaveCount(0);
  await expect(page.locator('.discovery-path')).toHaveCount(0);
  for (const query of queries) await expect(page.getByText(query, {exact:true})).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('mobile layout fits viewport and tabs work from keyboard', async ({ page }) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.locator('.event-card').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.getByRole('tab', {name:/Upcoming/}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Past/})).toHaveAttribute('aria-selected','true');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Needs confirmation/})).toHaveAttribute('aria-selected','true');
  await expect(page.getByRole('link',{name:'Our sources'})).toHaveCount(0);
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
  await expect(page.getByRole('heading',{name:'Couldn’t open the board'})).toBeVisible();
  fails = false;
  await page.getByRole('button',{name:'Retry',exact:true}).click();
  await expect(page.locator('.event-card').getByText('Cancelled',{exact:true})).toBeVisible();
  await selectPaper(page.locator('.event-card').first());
  const dates = page.locator('.event-schedule');
  await expect(dates).toContainText('Nov 21, 2026');
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
  await expect(page.locator('.paper .event-schedule')).toHaveCount(0);
  await expect(page.locator('.paper-status')).toHaveText('Undated search lead');
  await page.getByRole('tab',{name:/Past/}).click();
  await expect(page.locator('.event-card')).toHaveCount(2);
  const past = page.locator('.event-past_date');
  await selectPaper(past);
  await expect(past.locator('.badge')).toHaveText('Past date · completion unconfirmed');
  await expect(page.locator('.signup-detail')).toHaveCount(0);
  await expect(page.locator('.paper .event-schedule')).not.toBeEmpty();
  await expect(page.locator('.paper .event-schedule')).toContainText('Feb 14, 2024');
  await expect(page.locator('.paper .event-schedule')).not.toContainText('12:00');
  await expect(page.locator('.event-finished .state-finished')).toHaveText('Finished');
  await page.getByRole('searchbox').fill('Campus Security Tournament');
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
  await page.getByRole('tab',{name:/Past/}).click();
  await expect(page.locator('.event-card')).toHaveCount(0);
  await page.getByRole('tab',{name:/Needs confirmation/}).click();
  await expect(page.locator('.event-card')).toHaveCount(1);
  await expect(page.locator('.state-date_conflict')).toHaveText('Conflicting dates');
  await selectPaper(page.locator('.event-card').first());
  await expect(page.locator('.notices')).toContainText('November 4, 2026, December 4, 2026');
  await expect(page.locator('.event-schedule')).toHaveCount(0);
  await expect(page.locator('.history, .field-evidence')).toHaveCount(0);
  await page.getByRole('tab',{name:/Needs confirmation/}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Archive/})).toHaveAttribute('aria-selected','true');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab',{name:/Upcoming/})).toHaveAttribute('aria-selected','true');
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
  await page.getByRole('tab',{name:/Needs confirmation/}).click();
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
  await expect(page.locator('.collected-grid')).toContainText('Free');
  await expect(page.locator('.collected-grid')).toContainText('Required to register');
  await expect(page.locator('.collected-grid')).toContainText(international.eligibility);
  await expect(page.locator('.signup-detail dd')).toHaveText('Registration open');
  await expect(page.locator('.deadline-detail').filter({hasText:'Registration deadline'})).toHaveCount(0);
  await expect(page.locator('.deadline-detail').filter({hasText:'Submission deadline'})).toHaveCount(0);
  await expect(page.locator('.paper .event-schedule')).not.toBeEmpty();
  await expect(page.locator('.paper .event-schedule')).toContainText('Dec 3, 2032');
  await expect(page.locator('.paper .event-schedule')).toContainText('Dec 10, 2032');
  await expect(page.locator('.paper .event-schedule')).toContainText(/2:00\s*am PHT/i);
  await expect(page.locator('.paper .event-schedule')).not.toContainText('Competition');
  await expect(page.locator('.actions').getByRole('link',{name:/^Register/})).toHaveAttribute('href',international.registration_url);
  const ctf = page.locator('.event-card').filter({has:page.getByRole('heading', { includeHidden: true, name: base.name})});
  await selectPaper(ctf);
  await expect(page.locator('.paper .event-schedule')).not.toBeEmpty();
  await expect(page.locator('.deadline-detail').filter({hasText:'Submission deadline'})).toHaveCount(0);
  await expect(page.locator('.fact-extra').filter({hasText:'Price'})).toHaveCount(0);
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
  await expect(page.locator('.signup-detail dd')).toHaveText('Applications open · approval required');
  await expect(page.locator('.deadline-detail').filter({hasText:'Registration deadline'})).toHaveCount(0);
  await expect(page.locator('.paper-location')).toHaveText('NCR · Quezon City');
  await expect(page.locator('.attendance-detail dd')).toHaveText('Hybrid');
  await expect(page.locator('.fact-extra').filter({hasText:'Price'})).toHaveCount(0);
  await expect(page.locator('.fact-extra').filter({hasText:'Account'})).toHaveCount(0);
  await expect(page.locator('.paper .event-schedule')).not.toBeEmpty();
  await expect(page.locator('.paper .event-schedule')).not.toContainText('Competition');
  const publicTickets = page.locator('.paper .ticket-options > div').filter({has:page.getByRole('heading',{includeHidden:true,name:'Standard public tickets'})});
  const restrictedTickets = page.locator('.paper .ticket-options > div').filter({has:page.getByRole('heading',{includeHidden:true,name:'Restricted tickets',exact:true})});
  await expect(publicTickets.locator('li')).toHaveCount(2);
  await expect(publicTickets).toContainText('Standard - Onsite');
  await expect(publicTickets).toContainText('Standard - Online');
  await expect(publicTickets).not.toContainText('completed the training');
  await expect(restrictedTickets.locator('li')).toHaveCount(1);
  await expect(restrictedTickets).toContainText('Only for fellows who completed the training.');
  await expect(page.locator('.paper .actions a')).toHaveAttribute('href',event.announcement_url);
  await expect(page.locator('.paper .actions a')).toHaveCount(1);
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
  await expect(page.locator('.signup-detail dd')).toHaveText('Applications open · approval required');
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
    await expect(page.locator('.deadline-detail').filter({hasText:'Registration deadline'})).toHaveCount(0);
    const cutoff = page.locator('.deadline-detail').filter({hasText:'Submission deadline'});
    await expect(cutoff).toContainText('Dec 2, 2035');
    await expect(cutoff).toContainText(/12:00\s*am PHT/i);
    await expect(page.locator('.paper .event-schedule')).toContainText('Dec 3, 2035');
  }
});

for (const [layout, width] of [['desktop', 1366], ['mobile', 320]] as const) {
  test(`Needs confirmation merges unresolved sections and preserves filters on ${layout}`, async ({ page }) => {
    const data = topicDirectory();
    const events = [...data.events,
      {...data.events[0],id:'past',section:'past',status:'past_date'},
      {...data.events[0],id:'watch',name:'Pending security meetup',section:'watchlist',status:'undated_lead',format:'online',start:null},
      {...data.events[0],id:'conflict',name:'Pending security workshop',section:'unconfirmed',status:'date_conflict',format:'online',start:null},
      {...data.events[3],id:'unconfirmed',name:'Unscheduled meetup',section:'unconfirmed',status:'schedule_tba',start:null},
      {...data.events[0],id:'archive',section:'archived',status:'undated_lead'},
    ];
    await page.route('**/api/events',route=>route.fulfill({json:{...data,events}}));
    await page.setViewportSize({width,height:900}); await page.goto('/');
    await expect(page.getByRole('tab')).toHaveText(['Upcoming5','Past1','Needs confirmation3','Archive1']);
    const tab=page.getByRole('tab',{name:/Needs confirmation/}); await tab.click();
    await expect(page.locator('.event-card')).toHaveCount(3);
    expect(new Set(await page.locator('.notice-select').evaluateAll(nodes=>nodes.map(n=>n.id))).size).toBe(3);
    await chooseFilter(filterTrigger(page, 'interest'), 'cybersecurity');
    await expect(tab.locator('span')).toHaveText('2');
    await chooseFilter(filterTrigger(page, 'attendance'), 'online');
    await page.getByRole('searchbox').fill('workshop');
    await expect(page.locator('.event-card')).toHaveCount(1);
    const card=page.locator('#notice-conflict'); await card.focus(); await page.keyboard.press('Enter');
    await expect(page.locator('.paper')).toContainText('Pending security workshop');
    await expect(page.locator('.paper')).toContainText('Conflicting dates');
    if(width<=760){await page.getByRole('button',{name:'Back to the board'}).click();await expect(card).toBeFocused();}
    await page.getByRole('tab',{name:/Upcoming/}).click();
    await expect(page.locator('.event-card')).toHaveCount(0); await tab.click();
    await expect(page.getByRole('searchbox')).toHaveValue('workshop');
    await expect(page.locator('.event-card')).toHaveCount(1);
    await page.getByRole('button',{name:'Clear filters',exact:true}).click();
    await expect(page.locator('.event-card')).toHaveCount(3);
    await expect(tab).toHaveAttribute('aria-selected','true');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  });
}

test('each section has a truthful empty-directory message', async ({page})=>{
  await page.route('**/api/events',route=>route.fulfill({json:{events:[],generated_at:'2037-05-01T00:00:00Z'}}));
  await page.goto('/');
  for(const [tab,message] of [['Upcoming','No upcoming events recorded yet.'],['Past','No past events recorded yet.'],['Needs confirmation','No events needing confirmation.'],['Archive','No archived leads.']]) {
    await page.getByRole('tab',{name:new RegExp(tab)}).click();
    await expect(page.getByRole('heading',{name:message,exact:true})).toBeVisible();
    await expect(page.locator('.results-count')).toHaveText('0 events');
  }
});

for (const width of [1366, 390]) {
  test(`saved-list refresh stays below the board without collection diagnostics at ${width}px`, async ({page}) => {
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
      return route.fulfill({status:404});
    });
    await page.setViewportSize({width,height:900});
    await page.goto('/');
    const panel = page.getByRole('region',{name:'Directory updates'});
    await expect(panel.locator('.collection-status')).toHaveCount(0);
    await expect(panel.getByRole('button',{name:'Fetch events',exact:true})).toHaveCount(0);
    await expect(page.locator('.board .results-heading, .board .result-tools, .board .collection-status')).toHaveCount(0);
    await expect(page.locator('.board').getByRole('heading',{name:'Upcoming',exact:true})).toHaveCount(0);
    await expect(page.getByRole('tab',{name:/Upcoming/})).toContainText('5');
    const coverageBox = await page.locator('.board').boundingBox();
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
    await expect(page.locator('.refresh-slip')).toContainText('Couldn’t refresh · Showing saved listings');
    await expect(page.locator('.event-card')).toHaveCount(5);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}

for (const width of [1366, 390]) {
  test(`listing freshness is visible on arrival and uses verified event-page time at ${width}px`, async ({page}) => {
    const data = topicDirectory();
    const source = {id:'latest',name:'Example source',url:'https://organizer.example',kind:'website',status:'error',last_success:'2026-11-23T13:07:00Z',last_attempt:'2026-11-24T02:00:00Z',message:'Fetch failed',discovered:0,accepted:0};
    let verified: string | null = source.last_success;
    let reads = 0;
    await page.route('**/api/events', route => {
      reads++;
      return route.fulfill({json:{...data,generated_at:`2037-05-0${reads}T00:00:00Z`,listings_updated_at:verified,sources:[{...source,last_success:'2040-01-01T00:00:00Z'}]}});
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
    verified = '2026-11-24T01:00:00Z';
    await page.getByRole('button',{name:'Refresh saved listings',exact:true}).click();
    await expect(stamp).toContainText('Nov 24, 2026, 9:00 AM PHT');
    verified = null;
    await page.getByRole('button',{name:'Refresh saved listings',exact:true}).click();
    await expect(stamp).toHaveCount(0);
    await expect(stamp.locator('time')).toHaveCount(0);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  });
}
