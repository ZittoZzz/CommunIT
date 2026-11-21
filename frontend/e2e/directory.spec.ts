import { test, expect } from '@playwright/test';

test('real collected listings, filters, history, and source health', async ({ page, request }) => {
  const response = await request.get('/api/events');
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Find your next/ })).toBeVisible();
  const upcoming = data.events.filter((e: {section: string}) => e.section === 'upcoming');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.length);
  if (upcoming.length) {
    const card = page.locator('.event-card').first();
    await expect(card.locator('.actions a').first()).toHaveAttribute('href', /^https?:\/\//);
    await card.locator('.history > summary').click();
    await expect(card.locator('.history-link').first()).toBeVisible();
  }
  await page.getByRole('searchbox').fill('not-a-real-competition-abcdef');
  await expect(page.getByRole('heading', { name: 'No matches for these filters.' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).first().click();
  await page.getByRole('combobox', { name: 'Format', exact: true }).selectOption('online');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.filter((e: {format: string}) => e.format === 'online').length);
  await page.getByRole('combobox', { name: 'Format', exact: true }).selectOption('');
  await page.getByRole('combobox', { name: 'Registration', exact: true }).selectOption('open');
  await expect(page.locator('.event-card')).toHaveCount(upcoming.filter((e: {registration_status: string}) => e.registration_status === 'open').length);
  await page.getByRole('combobox', { name: 'Registration', exact: true }).selectOption('');
  await page.getByRole('tab', { name: /Finished/ }).click();
  await expect(page.locator('.event-card')).toHaveCount(data.events.filter((e: {section: string}) => e.section === 'finished').length);
  await page.getByRole('link', { name: 'Our sources' }).click();
  await expect(page.locator('.source-row')).toHaveCount(data.sources.length);
  await expect(page.getByText('Needs credentials', { exact: true })).toBeVisible();
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
  await expect(page.locator('.actions .primary')).toContainText('Search result · verify source');
  await expect(page.locator('.organizer')).toHaveText('Organizer unconfirmed');
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
  await expect(page.getByRole('tab',{name:/Finished/})).toHaveAttribute('aria-selected','true');
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
  await expect(page.getByText('Cancelled',{exact:true})).toBeVisible();
  const dates = page.locator('.dates');
  await expect(dates).toContainText('November 21, 2026');
  await expect(dates).toContainText('9:00');
  await expect(dates).toContainText('PHT');
  await expect(dates).not.toContainText('12:00');
});
