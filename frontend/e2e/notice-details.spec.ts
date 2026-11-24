import { test, expect, type Page } from '@playwright/test';

// Presentation fixtures only; never part of collection or benchmark discovery.
const day = (value: string) => ({raw:value, value, precision:'date', timezone:null});
const time = (value: string) => ({raw:value, value, precision:'datetime', timezone:'UTC'});
const base = {
  id:'sparse', name:'Sparse community meetup', organizer:'Community organizers', region:'NCR',
  format:'in_person', attendance_options:['Onsite'], geography:'PH', topics:[],
  section:'upcoming', status:'scheduled', start:time('2026-11-26T06:30:00Z'), end:time('2026-11-26T09:30:00Z'),
  announcement_url:'https://organizer.example/event', registration_url:'https://organizer.example/event',
  registration_status:'closed', deadline:null, submission_deadline:null, registration_opens:null,
  eligibility:'Public ticket options are listed; check their current availability.', price:{kind:'unknown'},
  account_required:null, description:'Unknown', summary:' ', posted_at:null, first_seen:'', last_checked:'',
  notices:[], announcements:[], stage:'main', edition:'2026',
  ticket_options:[{name:'Standard', access:'public', eligibility:null, attendance:null, registration_state:'closed', price:{kind:'unknown'}, deadline:null}],
};
const full = {...base, id:'full', topics:['community','cloud','cloud','unsupported'], name:'University workshop', start:day('2026-11-27'), end:null,
  eligibility:'University students', price:{kind:'paid', amount:250, currency:'PHP'}, account_required:true,
  registration_status:'open', deadline:day('2026-11-25'), submission_deadline:day('2026-11-29'),
  description:'Bring your laptop.', ticket_options:[]};
const multi = {...base, id:'multi', topics:['ai_data'], name:'Worldwide build week', region:'Philippines', format:'online', attendance_options:['Online'],
  start:time('2026-12-04T15:00:00Z'), end:time('2026-12-10T18:00:00Z'),
  eligibility:'Open to all', price:{kind:'paid', amount:0, currency:'PHP'}, account_required:false,
  registration_status:'unknown', ticket_options:[]};

async function select(page: Page, name: string) {
  const back = page.getByRole('button', {name:'Back to the board'});
  if (await back.isVisible()) await back.click();
  const button = page.getByRole('button', {name, exact:true});
  await button.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#paper-title')).toHaveText(name);
}
for (const width of [1366, 390, 320]) {
  test(`decision details omit missing facts, preserve supported facts and clear selection at ${width}px`, async ({page}, testInfo) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({width, height:900});
    await page.route('**/api/events', route => route.fulfill({json:{events:[base,full,multi],generated_at:'2026-11-24T00:00:00Z'}}));
    await page.goto('/');
    await expect(page.locator('.event-card').first().locator('.event-location')).toHaveText('NCR · In person');
    await select(page, full.name);
    await expect(page.locator('.interests-detail')).toHaveText('InterestsCommunity · Cloud');
    const collected = page.getByRole('region', {name:'What we can get'});
    await expect(collected).toBeVisible();
    await expect(collected).toHaveCSS('border-top-style','dotted');
    await expect(collected).toHaveCSS('border-bottom-style','dotted');
    await expect(collected).not.toContainText('Some details may be unavailable.');
    await expect(collected.locator('.actions')).toHaveCount(0);
    await expect(collected.locator('h3')).toHaveCSS('font-size','15px');
    await expect(page.locator('.schedule-detail dt')).toHaveText('When');
    await expect(page.locator('.location-detail dt')).toHaveText('Where');
    const when = await page.locator('.schedule-detail').boundingBox();
    const where = await page.locator('.location-detail').boundingBox();
    if(width > 480) {
      expect(Math.abs(when!.y - where!.y)).toBeLessThan(1);
      expect(where!.x).toBeGreaterThan(when!.x + when!.width);
    } else expect(where!.y).toBeGreaterThanOrEqual(when!.y + when!.height);

    await expect(page.locator('.collected-grid')).toContainText('University students');
    await expect(page.locator('.collected-grid')).toContainText('PHP 250');
    await expect(page.locator('.collected-grid')).toContainText('Required to register');
    await expect(page.locator('.deadline-detail dt')).toHaveText(['Registration deadline','Submission deadline']);
    await expect(page.locator('.event-schedule')).toHaveText('Nov 27, 2026');
    await expect(page.locator('.event-schedule')).not.toContainText(/PHT|12:00/);
    await page.screenshot({path:testInfo.outputPath(`full-${width}.png`),fullPage:width < 761});
    await select(page, base.name);
    await expect(page.locator('.interests-detail')).toHaveCount(0);
    await expect(page.locator('.event-schedule')).toHaveText('Nov 26, 2026 · 2:30–5:30 PM PHT');
    await expect(page.locator('.paper-location')).toHaveText('NCR');
    await expect(page.locator('.attendance-detail dd')).toHaveText('In person');
    await expect(page.locator('.signup-detail dd')).toHaveText('Registration closed');
    await expect(page.locator('.deadline-detail')).toHaveCount(0);
    await expect(page.locator('.fact-extra, .event-description, .ticket-options, .provenance, .history, .paper-status')).toHaveCount(0);
    await expect(page.locator('.paper')).not.toContainText(/Unknown|Who can join|Price|Account|University students|PHP 250|deadline|Upcoming/);
    await expect(page.locator('.paper .actions a')).toHaveCount(1);
    await expect(page.locator('.paper .actions a')).toHaveAccessibleName(/View organizer’s page/);
    await expect(page.locator('.paper .actions a')).toHaveAttribute('href',base.announcement_url);
    await page.screenshot({path:testInfo.outputPath(`sparse-${width}.png`),fullPage:width < 761});
    await select(page, multi.name);
    await expect(page.locator('.interests-detail dd')).toHaveText('AI & Data');
    await expect(page.locator('.event-schedule')).toContainText('Dec 4, 2026');
    await expect(page.locator('.event-schedule')).toContainText('Dec 11, 2026');
    await expect(page.locator('.event-schedule')).toContainText(/2:00\s*am PHT/i);
    await expect(page.locator('.paper-location')).toHaveText('Philippines');
    await expect(page.locator('.attendance-detail dd')).toHaveText('Online');
    await expect(page.locator('.collected-grid')).toContainText('Free');
    await expect(page.locator('.collected-grid')).toContainText('Open to all');
    await expect(page.locator('.collected-grid')).toContainText('Not required');
    await expect(page.locator('.signup-detail')).toHaveCount(0);
    await expect(page.locator('#notice-multi').locator('..').locator('..').locator('.price-free')).toHaveText('Free');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({path:testInfo.outputPath(`multi-${width}.png`),fullPage:width < 761});
    await select(page, base.name);
    await expect(page.locator('.interests-detail')).toHaveCount(0);
    await expect(page.locator('.fact-extra')).toHaveCount(0);
    await expect(page.locator('.paper')).not.toContainText('Open to all');
    expect(errors).toEqual([]);
  });
}

test('partial schedules, hybrid venues, placeholders and ticket requirements preserve evidence precision', async ({page}) => {
  const variants = [
    {...base,id:'am-pm',name:'Across noon',start:time('2026-11-26T03:30:00Z'),end:time('2026-11-26T05:00:00Z')},
    {...base,id:'date',name:'Date only',start:day('2026-11-26'),end:day('2026-11-26')},
    {...base,id:'start',name:'Start only',end:null},
    {...base,id:'partial',name:'Date with end time',start:day('2026-11-26')},
    {...base,id:'hybrid',name:'Hybrid workshop',format:'hybrid',attendance_options:['Onsite — Quezon City','Online','Online'],price:{kind:'paid',minimum_amount:199,currency:'PHP'}},
    {...base,id:'empty',name:'Undated notice',organizer:'Unknown',region:'Unspecified',format:'unknown',attendance_options:['Unknown'],start:null,end:null,eligibility:' Not announced ',price:null,registration_status:'unknown',description:null,ticket_options:[]},
    {...base,id:'tickets',name:'Ticket variants',ticket_options:[
      {name:'Students',access:'restricted',eligibility:'University students',attendance:'onsite',registration_state:'unknown',price:{kind:'paid',amount:0,currency:'PHP'},deadline:null},
      {name:'Professionals',access:'public',eligibility:'Open to all',attendance:'online',registration_state:'open',price:{kind:'paid',amount:500,currency:'PHP'},deadline:day('2026-11-25')},
    ]},
    {...base,id:'conflict',name:'Conflicting notice',status:'date_conflict'},
  ];
  await page.route('**/api/events', route=>route.fulfill({json:{events:variants,generated_at:'2026-11-24T00:00:00Z'}}));
  await page.goto('/');
  await select(page,'Across noon');
  await expect(page.locator('.event-schedule')).toHaveText('Nov 26, 2026 · 11:30 AM–1:00 PM PHT');
  await select(page,'Date only');
  await expect(page.locator('.event-schedule')).toHaveText('Nov 26, 2026');
  await select(page,'Start only');
  await expect(page.locator('.event-schedule')).toContainText(/2:30\s*pm PHT/i);
  await expect(page.locator('.event-schedule')).not.toContainText('5:30');
  await select(page,'Date with end time');
  await expect(page.locator('.event-schedule')).toHaveText('Nov 26, 2026 · ends 5:30 PM PHT');
  await select(page,'Hybrid workshop');
  await expect(page.locator('.paper-location')).toHaveText('NCR · Quezon City');
  await expect(page.locator('.attendance-detail dd')).toHaveText('Hybrid');
  await expect(page.locator('.collected-grid')).toContainText('From PHP 199');
  await select(page,'Undated notice');
  await expect(page.locator('.collected-details, .attendance-detail')).toHaveCount(0);
  await expect(page.locator('.paper .organizer, .paper-location, .event-schedule, .fact-extra, .signup-detail, .ticket-options, .event-description')).toHaveCount(0);
  await expect(page.locator('.event-card').filter({has:page.getByRole('button',{name:'Undated notice',exact:true})}).locator('.event-location, .preview-facts')).toHaveCount(0);
  await select(page,'Ticket variants');
  await expect(page.locator('.ticket-options')).not.toContainText(/Unknown|unconfirmed/);
  const student = page.locator('.ticket-options li').filter({hasText:'University students'});
  await expect(student).toContainText('Free');
  await expect(student).not.toContainText(/deadline|Registration/);
  await expect(page.locator('.ticket-options li').filter({hasText:'Professionals'})).toContainText('Registration deadline: 2026-11-25');
  await select(page,'Conflicting notice');
  await expect(page.locator('.event-schedule')).toHaveCount(0);
  await expect(page.locator('.paper-status')).toHaveText('Conflicting dates');
});
