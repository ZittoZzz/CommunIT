import { test, expect, type Page } from '@playwright/test';

// Display-only fixtures stress navigation; never used by runtime discovery.
const day = (value: string) => ({ raw: value, value, precision: 'date', timezone: null });
const events = Array.from({ length: 18 }, (_, index) => ({
  id: `board-${index}`, name: `Community notice ${String(index + 1).padStart(2, '0')}`,
  organizer: 'Fixture organizer', region: 'Quezon City', format: 'in_person',
  geography: index < 14 ? 'PH' : 'international_online', topics: ['community'],
  section: 'upcoming', status: 'scheduled', start: day('2035-12-01'), end: null,
  competition_date: null, deadline: day('2035-11-29'), submission_deadline: day('2035-11-30'),
  registration_status: 'unknown', registration_url: null, registration_opens: null,
  announcement_url: 'https://organizer.example/notice', eligibility: null,
  first_seen: '2035-11-01T00:00:00Z', last_checked: '2035-11-01T00:00:00Z', posted_at: null,
  summary: null, description: index % 2 ? 'Short event description.' : 'Long description.\n'.repeat(80),
  price: { kind: 'unknown' }, notices: [], announcements: [], stage: 'main', edition: '2035',
}));
async function setup(page: Page, width: number) {
  await page.setViewportSize({ width, height: 844 });
  await page.route('**/api/events', route => route.fulfill({ json: { events, sources: [], generated_at: '2035-11-01T00:00:00Z' } }));
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(18);
}

test('desktop keyboard selection preserves list nodes, position and scroll across different paper lengths', async ({ page }) => {
  await setup(page, 1366);
  const card = page.locator('.notice-select').nth(6);
  await card.focus();
  const before = await page.locator('.board-list').evaluate(element => {
    (window as typeof window & { originalList?: Element }).originalList = element;
    return { y: window.scrollY, top: element.getBoundingClientRect().top, height: element.getBoundingClientRect().height };
  });
  await page.keyboard.press('Enter');
  await expect(page.locator('#paper-title')).toHaveText(events[6].name);
  await expect(card).toBeFocused();
  await page.locator('.paper-scroll').evaluate(element => { element.scrollTop = 250; });
  // preventScroll isolates the selection behavior from deliberate browser focus scrolling.
  await page.locator('.notice-select').nth(7).evaluate(element => (element as HTMLElement).focus({preventScroll:true}));
  await page.keyboard.press('Space');
  await expect(page.locator('#paper-title')).toHaveText(events[7].name);
  const after = await page.locator('.board-list').evaluate(element => ({
    y: window.scrollY, top: element.getBoundingClientRect().top, height: element.getBoundingClientRect().height,
    sameNode: element === (window as typeof window & { originalList?: Element }).originalList,
  }));
  expect(after).toEqual({ ...before, sameNode: true });
  expect(await page.locator('.paper-scroll').evaluate(element => element.scrollTop)).toBe(0);
  await expect(page.locator('.notice-select[aria-pressed=true]')).toHaveCount(1);
});

for (const width of [390, 760]) {
  test(`mobile Back restores composed filters, scroll and selected-card focus at ${width}px`, async ({ page }) => {
    await setup(page, width);
    await page.getByRole('searchbox').fill('Community notice');
    await page.getByRole('combobox', {name:'Topic', exact:true}).selectOption('community');
    await page.getByRole('combobox', {name:'Format', exact:true}).selectOption('in_person');
    await page.getByRole('combobox', {name:'Registration', exact:true}).selectOption('unknown');
    const card = page.locator('.notice-select').nth(10);
    await card.focus();
    const originalY = await page.evaluate(() => window.scrollY);
    expect(originalY).toBeGreaterThan(500);
    await page.keyboard.press('Enter');
    await expect(page.locator('#paper-title')).toBeFocused();
    await expect(page.locator('.board-list')).not.toBeVisible();
    const back = page.getByRole('button', {name:'Back to the board'});
    await expect(back).toBeInViewport();
    const paper = await page.locator('.paper').boundingBox();
    const board = await page.locator('.board-split').boundingBox();
    expect(paper!.width).toBeCloseTo(board!.width, 0);
    await page.evaluate(() => window.scrollBy(0, 600));
    await back.click();
    await expect(card).toBeFocused();
    expect(await page.evaluate(() => window.scrollY)).toBe(originalY);
    await expect(page.getByRole('searchbox')).toHaveValue('Community notice');
    await expect(page.getByRole('combobox', {name:'Topic',exact:true})).toHaveValue('community');
    await expect(page.getByRole('combobox', {name:'Format',exact:true})).toHaveValue('in_person');
    await expect(page.getByRole('combobox', {name:'Registration',exact:true})).toHaveValue('unknown');
    await expect(card).toHaveAttribute('aria-pressed', 'true');
    await page.keyboard.press('Space');
    await expect(page.locator('#paper-title')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(card).toBeFocused();
    expect(await page.evaluate(() => window.scrollY)).toBe(originalY);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}

test('filtering replaces a hidden selection, clears stale details and retains both geography groups', async ({ page }) => {
  await setup(page, 1366);
  await page.locator('.notice-select').nth(15).click();
  await expect(page.locator('.paper .eyebrow')).toContainText('International online');
  await page.getByRole('searchbox').fill('notice 02');
  await expect(page.locator('.event-card')).toHaveCount(1);
  await expect(page.locator('#paper-title')).toHaveText(events[1].name);
  await expect(page.locator('.paper .facts')).toContainText('PriceUnknown');
  await expect(page.locator('.paper .registration')).toContainText('Registration unconfirmed');
  await expect(page.locator('.registration dt')).toHaveText(['Registration deadline', 'Submission deadline']);
  await expect(page.locator('.paper .actions a')).toHaveAttribute('href', events[1].announcement_url);
  await page.getByRole('searchbox').fill('no matching notices');
  await expect(page.locator('.paper')).toHaveCount(0);
  await expect(page.getByRole('heading', {name:'No matches for these filters.'})).toBeVisible();
  await page.getByRole('button', {name:'Clear filters'}).first().click();
  await expect(page.getByRole('region', {name:'PH opportunities'})).toBeVisible();
  await expect(page.getByRole('region', {name:'International online opportunities'})).toBeVisible();
  await expect(page.locator('.event-card')).toHaveCount(18);
});

test('resize from a mobile paper returns to an accessible board without losing selection', async ({ page }) => {
  await setup(page, 390);
  await page.locator('.notice-select').nth(4).click();
  await expect(page.locator('#paper-title')).toBeFocused();
  await page.setViewportSize({width:1280,height:844});
  await expect(page.locator('.board-list')).toBeVisible();
  await expect(page.locator('#paper-title')).toHaveText(events[4].name);
  await expect(page.locator('.notice-select').nth(4)).toBeFocused();
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator('.board-list')).toBeVisible();
  await expect(page.locator('.paper')).not.toBeVisible();
});


test('editing a filter while reading on mobile returns to results and keeps focus in the filter', async ({ page }) => {
  await setup(page, 390);
  await page.locator('.notice-select').nth(4).click();
  await expect(page.locator('#paper-title')).toBeFocused();
  const search = page.getByRole('searchbox');
  await search.fill('notice 02');
  await expect(page.locator('.board-list')).toBeVisible();
  await expect(page.locator('.paper')).not.toBeVisible();
  await expect(page.locator('.event-card')).toHaveCount(1);
  await expect(search).toBeFocused();
  await page.locator('.notice-select').click();
  await expect(page.locator('#paper-title')).toHaveText(events[1].name);
});

for (const width of [1366, 390]) {
  test(`section tabs stay neutral until selected and leave the board frame unchanged at ${width}px`, async ({page}) => {
    await setup(page, width);
    const filters = await page.locator('.controls').boundingBox();
    const tabs = await page.getByRole('tablist').boundingBox();
    const board = await page.locator('.board').boundingBox();
    expect(tabs!.y).toBeGreaterThanOrEqual(filters!.y + filters!.height);
    expect(board!.y - (tabs!.y + tabs!.height)).toBeLessThanOrEqual(1);
    const frame = await page.locator('.board').evaluate(element => getComputedStyle(element).borderColor);
    const colors = new Set<string>();
    for (const section of ['upcoming','all','finished','unconfirmed','watchlist','archived']) {
      const tab = page.locator(`#tab-${section}`);
      await tab.click();
      await expect(tab).toHaveAttribute('aria-selected','true');
      await expect(page.locator('.board-section')).toHaveAttribute('data-section', section);
      const accent = await tab.evaluate(element => getComputedStyle(element).backgroundColor);
      expect(await page.locator('.board').evaluate(element => getComputedStyle(element).borderColor)).toBe(frame);
      await page.mouse.move(0, 0);
      for (const other of await page.locator('[role=tab][aria-selected=false]').all()) {
        await expect(other).toHaveCSS('background-color', 'rgb(255, 255, 255)');
        await expect(other).toHaveCSS('color', 'rgb(85, 93, 78)');
      }
      colors.add(accent);
    }
    expect(colors.size).toBe(6);
    await page.keyboard.press('Home');
    await expect(page.locator('#tab-upcoming')).toBeFocused();
    await expect(page.locator('#tab-upcoming')).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });

  test(`review and source notes precede the facts and are visible when opening a paper at ${width}px`, async ({page}) => {
    await page.setViewportSize({width,height:900});
    const lead = {...events[0], id:'notes-lead', name:'Unverified regional community lead', section:'watchlist', status:'undated_lead', start:null,
      review:{required:true,expired:false,expires_at:null,reasons:['The event page could not be verified.']},
      notices:['Search result only. Full post was not accessed; confirm all details with the organizer.', 'An edition year is not a confirmed upcoming schedule or open registration.']};
    await page.route('**/api/events',route=>route.fulfill({json:{events:[lead],sources:[],generated_at:'2035-11-01T00:00:00Z'}}));
    await page.goto('/');
    await page.getByRole('tab',{name:/Watchlist/}).click();
    await expect(page.locator('.event-card .review-flag')).toBeVisible();
    await page.locator('.notice-select').click();
    const notes = page.getByRole('region',{name:'Important event notes'});
    await expect(notes.getByRole('heading',{name:'Important notes'})).toBeInViewport();
    await expect(notes.locator('.notices p').first()).toBeInViewport();
    await expect(notes.locator('.review-note')).toContainText('remains visible');
    const noteBox = await notes.boundingBox();
    const dates = await page.locator('.event-detail-body > .dates').boundingBox();
    expect(noteBox!.y + noteBox!.height).toBeLessThanOrEqual(dates!.y);
    expect(await page.locator('.paper-scroll').evaluate(element => element.scrollTop)).toBe(0);
    if (width < 761) {
      await page.getByRole('button',{name:'Back to the board'}).click();
      await expect(page.locator('.notice-select')).toBeFocused();
    }
  });
}

for (const width of [1366, 390]) {
  test(`cards follow Manila calendar dates within each geography at ${width}px`, async ({ page }) => {
    const base = {...events[0], description: null};
    const fixture = [
      {...base, id:'free-late', name:'Later free signup', start:day('2035-12-05'), registration_status:'open', price:{kind:'free'}},
      {...base, id:'undated', name:'Undated with deadline', start:null, deadline:day('2035-11-01')},
      {...base, id:'rollover', name:'UTC rolls into December 3', start:{raw:'2035-12-02T18:00:00Z',value:'2035-12-02T18:00:00Z',precision:'datetime',timezone:'UTC'}},
      {...base, id:'parent', name:'Parent event date', start:null, parent_event_start:day('2035-12-04')},
      {...base, id:'early', name:'Earlier unknown signup', start:day('2035-12-01')},
      {...base, id:'conflict', name:'Conflicting dates', status:'date_conflict', start:day('2035-11-01')},
      {...base, id:'competition', name:'Competition date', start:null, competition_date:day('2035-12-02')},
      {...base, id:'online-late', name:'Online later', geography:'international_online', start:day('2035-12-02'), registration_status:'open'},
      {...base, id:'online-early', name:'Online earlier', geography:'international_online', start:day('2035-11-30')},
    ];
    await page.setViewportSize({width,height:900});
    await page.route('**/api/events', route => route.fulfill({json:{events:fixture,sources:[],generated_at:'2035-11-01T00:00:00Z'}}));
    await page.goto('/');
    const expected = ['Earlier unknown signup','Competition date','UTC rolls into December 3','Parent event date','Later free signup','Undated with deadline','Conflicting dates','Online earlier','Online later'];
    await expect(page.locator('.event-card h3')).toHaveText(expected);
    await expect(page.locator('.event-card time.event-date').nth(2)).toHaveAttribute('datetime','2035-12-03');
    await page.getByRole('tab',{name:/All events/}).click();
    await expect(page.locator('.event-card h3')).toHaveText(expected);
    await page.getByRole('combobox',{name:'Topic',exact:true}).selectOption('community');
    await expect(page.locator('.event-card h3')).toHaveText(expected);
  });
}
