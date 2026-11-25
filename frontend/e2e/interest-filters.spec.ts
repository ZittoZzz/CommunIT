import {filterTrigger, chooseFilter, expectFilter} from './filter-helpers';
import { test, expect } from '@playwright/test';

// UI-only fixtures, never discovery inputs.
const day = {raw:'2035-12-01',value:'2035-12-01',precision:'date',timezone:null};
const base = {
  organizer:'Campus builders',region:'Philippines',geography:'PH',format:'in_person',
  section:'upcoming',status:'scheduled',start:day,end:null,deadline:null,registration_opens:null,
  registration_status:'open',registration_url:null,announcement_url:'https://organizer.example/event',
  eligibility:null,price:{kind:'unknown'},summary:null,description:null,posted_at:null,first_seen:'',last_checked:'',
  notices:[],announcements:[],stage:'main',edition:'2035',
};
const events = [
  {...base,id:'cloud-room',name:'Campus cloud workshop',topics:['cloud']},
  {...base,id:'cloud-online',name:'Campus cloud stream',topics:['cloud'],format:'online',registration_status:'closed'},
  {...base,id:'security',name:'Campus security meetup',topics:['cybersecurity'],format:'online',registration_status:'unknown'},
  {...base,id:'ai',name:'Campus AI workshop',topics:['ai_data'],registration_status:'waitlisted'},
  {...base,id:'community',name:'Campus community social',topics:['community'],format:'hybrid'},
  {...base,id:'devops',name:'Campus deployment workshop',topics:['devops']},
  {...base,id:'none',name:'Campus general gathering',topics:[]},
];
for(const width of [1366,760,390,320]) {
  test(`navbar search and labeled dropdowns compose without clipping at ${width}px`, async ({page},testInfo) => {
    await page.setViewportSize({width,height:900});
    await page.route('**/api/events',route=>route.fulfill({json:{events,generated_at:'2035-11-01T00:00:00Z'}}));
    await page.goto('/');
    const controls = page.getByRole('region',{name:'Find events'});
    const search = page.getByRole('searchbox',{name:'Search events'});
    const interest = filterTrigger(page, 'interest');
    const attend = filterTrigger(page, 'attendance');
    await expect(page.locator('.topbar').getByRole('searchbox',{name:'Search events'})).toHaveCount(1);
    await expect(interest).toHaveAccessibleName('Browse by interest');
    await expect(attend).toHaveAccessibleName('How to attend');
    await expect(search).toHaveAttribute('placeholder','Event, organizer, or school');
    await expect(page.locator('.filter-trigger')).toHaveCount(2);
    for(const control of [interest,attend]) {
      await expectFilter(control, '');
      await expect(control).not.toHaveClass(/is-active/);
      await expect(control).toBeVisible();
      expect(await control.evaluate(el=>el.getBoundingClientRect().height)).toBe(width <= 760 ? 40 : 36);
      const box=(await control.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x+box.width).toBeLessThanOrEqual(width);
    }
    await expect(interest).toHaveText('Browse by interest');
    await expect(attend).toHaveText('How to attend');
    await expect(controls.locator('.filter-trigger > svg')).toHaveCount(2);
    await expect(page.locator('.event-card')).toHaveCount(7);
    await expect(page.locator('.directory-updated')).toHaveCount(0);
    const searchBox = await search.boundingBox();
    const boxes = await controls.locator('.filter-trigger').evaluateAll(elements=>elements.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};}));
    expect(boxes[0].y).toBeGreaterThanOrEqual(searchBox!.y+searchBox!.height);
    expect(boxes[1].y).toBe(boxes[0].y);
    expect(boxes[1].x).toBeGreaterThanOrEqual(boxes[0].x+boxes[0].width);
    const tabs = await page.getByRole('tablist').boundingBox();
    expect(tabs!.y).toBeGreaterThanOrEqual(Math.max(...boxes.map(box=>box.y+box.height)));
    await page.screenshot({path:testInfo.outputPath(`defaults-${width}.png`),fullPage:false});
    await chooseFilter(interest, 'cloud');
    await expectFilter(interest, 'cloud');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await chooseFilter(interest, 'ai_data');
    await expect(page.locator('.event-card')).toHaveCount(1);
    await expect(page.locator('.event-card h3')).toHaveText(['Campus AI workshop']);
    await chooseFilter(interest, '');
    await expect(page.locator('.event-card')).toHaveCount(7);
    await search.fill('Campus'); await chooseFilter(attend, 'online');
    await chooseFilter(interest, 'cloud');
    await expect(page.locator('.event-card h3')).toHaveText(['Campus cloud stream']);
    await expect(page.locator('.event-card .signup-fact')).toHaveText('Registration closed');
    await page.locator('.notice-select').click();
    await expect(page.locator('.signup-detail dd')).toHaveText('Registration closed');
    if(width<=760) await page.getByRole('button',{name:'Back to the board'}).click();
    await expectFilter(interest, 'cloud');
    await chooseFilter(interest, '');
    await expect(search).toHaveValue('Campus');
    await expectFilter(attend, 'online');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await chooseFilter(attend, '');
    await expect(page.locator('.event-card')).toHaveCount(7);
    await page.getByRole('button',{name:'Clear filters',exact:true}).first().click();
    await expect(search).toHaveValue('');
    await expectFilter(interest, '');
    await expectFilter(attend, '');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  });
}

test('legacy URL and saved registration values never filter the directory', async ({page}) => {
  await page.addInitScript(()=>{
    localStorage.setItem('filters',JSON.stringify({registration:'open',registration_status:'open'}));
    localStorage.setItem('registration','open');
    sessionStorage.setItem('filters',JSON.stringify({registration:'closed'}));
  });
  const requests: string[]=[];
  await page.route('**/api/events*',route=>{requests.push(route.request().url());return route.fulfill({json:{events,generated_at:'2035-11-01T00:00:00Z'}});});
  await page.goto('/?registration=open&registration_status=closed&status=waitlisted#registration=unknown');
  await expect(page.locator('.event-card')).toHaveCount(7);
  await expect(page.getByRole('combobox',{name:'Registration',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Clear filters',exact:true})).toHaveCount(0);
  await expect(page.locator('.signup-fact.registration-closed')).toHaveCount(1);
  await expect(page.locator('.signup-fact.registration-waitlisted')).toHaveCount(1);
  await page.reload();
  await expect(page.locator('.event-card')).toHaveCount(7);
  expect(requests.every(url=>new URL(url).search==='')).toBeTruthy();
});

test('represented interest choices remain available and empty refresh clears details', async ({page}) => {
  let current = [{...base,id:'network',name:'Network session',topics:['networking_systems']}, {...base,id:'delivery',name:'Delivery session',topics:['devops']}];
  await page.route('**/api/events',route=>route.fulfill({json:{events:current,generated_at:'2035-11-01T00:00:00Z'}}));
  await page.goto('/');
  await expect(page.locator('.event-card .event-topics')).toHaveText(['Networking & Systems','DevOps']);
  await expect(page.locator('.interest-chip, .explore-interests')).toHaveCount(0);
  const interest = filterTrigger(page, 'interest');
  await chooseFilter(interest, 'devops');
  await expect(page.locator('.event-card h3')).toHaveText(['Delivery session']);
  await chooseFilter(interest, 'networking_systems');
  await expect(page.locator('.event-card h3')).toHaveText(['Network session']);
  current=[];
  await page.getByRole('button',{name:'Refresh saved listings'}).click();
  await expect(page.locator('.event-card, .paper')).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'No matches for these filters.'})).toBeVisible();
  await expectFilter(interest, 'networking_systems');
});

test('missing and invalid freshness timestamps omit the whole line', async ({page}) => {
  let verified: unknown=null;
  await page.route('**/api/events',route=>route.fulfill({json:{events,listings_updated_at:verified,generated_at:'2035-11-01T00:00:00Z'}}));
  await page.goto('/');
  for(const value of [null,undefined,'','invalid','2026-02-30T10:00:00Z','2026-11-24',123]) {
    verified=value; await page.reload();
    await expect(page.locator('.event-card')).toHaveCount(7);
    await expect(page.locator('.directory-updated')).toHaveCount(0);
    await expect(page.locator('.controls')).not.toContainText(/Listings last updated|Checking|Not recorded yet/);
  }
  verified='2026-11-24T01:00:00Z'; await page.reload();
  await expect(page.locator('.directory-updated')).toContainText('Nov 24, 2026, 9:00 AM PHT');
  await expect(page.locator('.directory-updated time')).toHaveAttribute('datetime',verified as string);
});
