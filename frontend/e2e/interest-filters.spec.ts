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
  test(`interest chips and dropdowns compose without clipping at ${width}px`, async ({page},testInfo) => {
    await page.setViewportSize({width,height:900});
    await page.route('**/api/events',route=>route.fulfill({json:{events,generated_at:'2035-11-01T00:00:00Z'}}));
    await page.goto('/');
    const controls = page.getByRole('region',{name:'Find events'});
    const search = page.getByRole('searchbox',{name:'Search events'});
    const interest = page.getByRole('combobox',{name:'Browse by interest'});
    const attend = page.getByRole('combobox',{name:'How to attend'});
    const chips = page.getByRole('group',{name:'Explore interests'});
    const cloud = chips.getByRole('button',{name:'Cloud',exact:true});
    await expect(controls.locator('.filter > span:first-child')).toHaveText(['Search events','Browse by interest','How to attend']);
    await expect(search).toHaveAttribute('placeholder','Event, organizer, or school');
    await expect(page.getByRole('combobox')).toHaveCount(2);
    await expect(interest.locator('option:checked')).toHaveText('All interests');
    await expect(attend.locator('option:checked')).toHaveText('Online, in person, or both');
    await expect(interest).toHaveClass('is-default');
    await expect(attend).toHaveClass('is-default');
    await expect(chips.getByRole('button')).toHaveText(['Cybersecurity','AI & Data','Cloud','Community']);
    await expect(page.locator('.event-card')).toHaveCount(7);
    await expect(page.locator('.directory-updated')).toHaveCount(0);
    for(const select of [interest,attend]) {
      await expect(select.locator('..').locator('svg')).toBeVisible();
      expect(await select.evaluate(element=>{
        const el=element as HTMLSelectElement;
        const style=getComputedStyle(el), canvas=document.createElement('canvas'),ctx=canvas.getContext('2d')!;
        ctx.font=style.font;
        return ctx.measureText(el.selectedOptions[0].text).width+parseFloat(style.paddingLeft)+parseFloat(style.paddingRight)<=el.clientWidth;
      })).toBeTruthy();
    }
    const boxes = await controls.locator('.filter').evaluateAll(elements=>elements.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};}));
    expect(boxes[0].width).toBeGreaterThanOrEqual(Math.max(boxes[1].width,boxes[2].width));
    if(width<=760) expect(boxes[1].y).toBeGreaterThanOrEqual(boxes[0].y+boxes[0].height);
    await page.screenshot({path:testInfo.outputPath(`defaults-${width}.png`),fullPage:false});
    await cloud.focus(); await page.keyboard.press('Space');
    await expect(cloud).toHaveAttribute('aria-pressed','true');
    await expect(cloud).toBeFocused();
    await expect(interest).toHaveValue('cloud');
    await expect(interest).not.toHaveClass('is-default');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await expect(chips.getByRole('button')).toHaveText(['Cybersecurity','AI & Data','Cloud','Community']);
    await interest.selectOption('ai_data');
    await expect(cloud).toHaveAttribute('aria-pressed','false');
    await expect(chips.getByRole('button',{name:'AI & Data',exact:true})).toHaveAttribute('aria-pressed','true');
    await expect(page.locator('.event-card')).toHaveCount(1);
    await interest.selectOption('');
    await expect(chips.locator('[aria-pressed=true]')).toHaveCount(0);
    await expect(page.locator('.event-card')).toHaveCount(7);
    await search.fill('Campus'); await attend.selectOption('online');
    await cloud.click();
    await expect(page.locator('.event-card h3')).toHaveText(['Campus cloud stream']);
    await expect(page.locator('.event-card .signup-fact')).toHaveText('Registration closed');
    await page.locator('.notice-select').click();
    await expect(page.locator('.signup-detail dd')).toHaveText('Registration closed');
    if(width<=760) await page.getByRole('button',{name:'Back to the board'}).click();
    await expect(interest).toHaveValue('cloud');
    await cloud.focus(); await page.keyboard.press('Enter');
    await expect(interest).toHaveValue('');
    await expect(cloud).toHaveAttribute('aria-pressed','false');
    await expect(search).toHaveValue('Campus');
    await expect(attend).toHaveValue('online');
    await expect(page.locator('.event-card')).toHaveCount(2);
    await attend.selectOption('');
    await expect(page.locator('.event-card')).toHaveCount(7);
    await page.getByRole('button',{name:'Clear filters',exact:true}).first().click();
    await expect(search).toHaveValue('');
    await expect(interest).toHaveValue('');
    await expect(attend).toHaveValue('');
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

test('chips use represented categories and fall back beyond the preferred four', async ({page}) => {
  let current = [{...base,id:'network',name:'Network session',topics:['networking_systems']}, {...base,id:'delivery',name:'Delivery session',topics:['devops']}];
  await page.route('**/api/events',route=>route.fulfill({json:{events:current,generated_at:'2035-11-01T00:00:00Z'}}));
  await page.goto('/');
  await expect(page.locator('.interest-chip')).toHaveText(['DevOps','Networking & Systems']);
  await page.getByRole('combobox',{name:'Browse by interest'}).selectOption('devops');
  await expect(page.locator('.interest-chip')).toHaveText(['DevOps','Networking & Systems']);
  current=[];
  await page.getByRole('button',{name:'Refresh saved listings'}).click();
  await expect(page.locator('.explore-interests')).toHaveCount(0);
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
