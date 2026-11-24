import { test, expect, type Page } from '@playwright/test';

// Display-only fixtures. Venue evidence is the collector's retained Event.location,
// not an organizer address or a discovery input.
const url = 'https://www.meetup.com/example/events/123456789/';
const place = {'@type':'Place',name:'Community Lab , Inc.',address:{'@type':'PostalAddress',addressLocality:'Pasig',streetAddress:'20th Floor, Example Building, Example Rd, Ortigas Center, Pasig, Metro Manila, Philippines, Pasig'}};
const proof = (location: unknown, source = url) => ({url:source,quote:`Schema.org eventAttendanceMode=https://schema.org/OfflineEventAttendanceMode; location=${JSON.stringify(location)}`});
const day = (value: string) => ({raw:value,value,precision:'date',timezone:null});
const base = {
  id:'venue',name:'Community data workshop',organizer:'Community builders',region:'Philippines',format:'in_person',
  attendance_options:['Onsite'],geography:'PH',topics:['community'],status:'scheduled',section:'upcoming',
  start:day('2035-12-01'),end:null,deadline:null,submission_deadline:null,registration_opens:null,
  registration_status:'unknown',registration_url:null,announcement_url:'https://publisher.example/announcement',organizer_event_url:url,
  eligibility:null,price:{kind:'unknown'},account_required:null,description:null,summary:null,
  posted_at:null,first_seen:'2035-11-01T00:00:00Z',last_checked:'2035-11-02T00:00:00Z',notices:[],
  field_evidence:{format:proof(place)},announcements:[{url,kind:'announcement',access:'full',revision_count:10}],
};
async function select(page: Page, name: string) {
  const back = page.getByRole('button',{name:'Back to the board'});
  if(await back.isVisible()) await back.click();
  const card = page.getByRole('button',{name,exact:true});
  await card.focus(); await page.keyboard.press('Enter');
  await expect(page.locator('#paper-title')).toHaveText(name);
}
for (const width of [1366,390]) {
  test(`public notices show event venues, clean links and no evidence dropdown at ${width}px`, async ({page},testInfo) => {
    const errors: string[]=[]; page.on('pageerror',error=>errors.push(error.message));
    const online = {...base,id:'online',name:'Online community talk',format:'online',attendance_options:['Online'],organizer_event_url:'https://organizer.example/online',registration_url:'https://signup.example/online'};
    const broad = {...base,id:'broad',name:'National community gathering',organizer_event_url:'https://organizer.example/national',field_evidence:{organizer:{url,quote:JSON.stringify(place)}}};
    const input={events:[base,online,broad],generated_at:'2035-11-02T00:00:00Z'};
    const original=JSON.stringify(input);
    await page.route('**/api/events',route=>route.fulfill({json:input}));
    await page.setViewportSize({width,height:900}); await page.goto('/');
    await expect(page.locator('.event-card').first().locator('.event-location')).toHaveText('Pasig · In person');
    await select(page,base.name);
    await expect(page.locator('.paper-location')).toHaveText('Community Lab, Inc. · Ortigas Center, Pasig');
    await expect(page.locator('.venue-address')).toHaveText('20th Floor, Example Building, Example Rd');
    await expect(page.locator('.attendance-detail dd')).toHaveText('In person');
    await expect(page.locator('.paper .actions a')).toHaveCount(1);
    await expect(page.getByRole('link',{name:/View organizer’s page/})).toHaveAttribute('href',url);
    await expect(page.locator('.paper details,.history,.field-evidence,.related-links,.checked')).toHaveCount(0);
    await expect(page.locator('.paper')).not.toContainText(/Sources & updates|Evidence for listed details|Last observed|Revision|Rescheduled/);
    await expect(page.locator('.paper .paper-status')).toHaveCount(0);
    await expect(page.locator('.paper').getByRole('link',{name:'Source',exact:true})).toHaveCount(0);
    await page.screenshot({path:testInfo.outputPath(`venue-${width}.png`),fullPage:width===390});
    await select(page,online.name);
    await expect(page.locator('.paper-location')).toHaveText('Philippines');
    await expect(page.locator('.attendance-detail dd')).toHaveText('Online');
    await expect(page.locator('.venue-address,.venue-format')).toHaveCount(0);
    await expect(page.locator('.paper')).not.toContainText('Pasig');
    await expect(page.getByRole('link',{name:/View organizer’s page/})).toHaveAttribute('href',online.organizer_event_url);
    await expect(page.getByRole('link',{name:/^Register/})).toHaveAttribute('href',online.registration_url);
    await page.screenshot({path:testInfo.outputPath(`online-${width}.png`),fullPage:width===390});
    await select(page,broad.name);
    await expect(page.locator('.paper-location')).toHaveText('Philippines');
    await expect(page.locator('.paper .actions a')).toHaveCount(1);
    await expect(page.getByRole('link',{name:/View organizer’s page/})).toHaveAttribute('href',broad.organizer_event_url);
    await expect(page.locator('.venue-address,.venue-format')).toHaveCount(0);
    await expect(page.locator('.paper')).not.toContainText(/Community Lab|Pasig/);
    await page.screenshot({path:testInfo.outputPath(`broad-${width}.png`),fullPage:width===390});
    await select(page,base.name);
    await expect(page.locator('.paper-location')).toContainText('Pasig');
    await expect(page.getByRole('link',{name:/View organizer’s page/})).toHaveAttribute('href',url);
    expect(JSON.stringify(input)).toBe(original);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    expect(errors).toEqual([]);
  });
}

test('venues require current fetched event evidence; malformed, unrelated and organizer locations stay broad', async ({page}) => {
  const variations = [
    {...base,id:'search',name:'Search only',announcements:[{url,kind:'announcement',access:'search_only'}]},
    {...base,id:'malformed',name:'Truncated evidence',field_evidence:{format:{url,quote:'Schema.org eventAttendanceMode=OfflineEventAttendanceMode; location={"@type":"Place",'}}},
    {...base,id:'other',name:'Another event location',field_evidence:{format:proof(place,'https://www.meetup.com/example/events/987654321/')}},
    {...base,id:'organizer',name:'Organizer address',field_evidence:{organizer:proof(place)}},
    {...base,id:'old',name:'Old venue',field_evidence:{},announcements:[{...base.announcements[0],field_evidence:base.field_evidence}]},
    {...base,id:'virtual',name:'Virtual address',field_evidence:{format:proof({...place,'@type':'VirtualLocation'})}},
  ];
  await page.route('**/api/events',route=>route.fulfill({json:{events:variations,generated_at:'2035-11-02T00:00:00Z'}}));
  await page.goto('/');
  for (const event of variations) {
    await select(page,event.name);
    await expect(page.locator('.paper-location')).toHaveText('Philippines');
    await expect(page.locator('.venue-address')).toHaveCount(0);
    await expect(page.locator('.paper')).not.toContainText('Community Lab');
  }
});

test('event links deduplicate tracking and Meetup aliases while preserving distinct registration destinations', async ({page}) => {
  const same={...base,registration_url:'https://meetup.com/renamed-group/events/123456789/?utm_source=notice'};
  const separate={...base,id:'register',name:'Separate registration',registration_url:'https://organizer.example/register?event=42'};
  const fallback={...base,id:'fallback',name:'Original announcement fallback',organizer_event_url:null,announcement_url:'https://organizer.example/events/42'};
  await page.route('**/api/events',route=>route.fulfill({json:{events:[same,separate,fallback],generated_at:'2035-11-02T00:00:00Z'}}));
  await page.goto('/');
  await select(page,same.name);
  await expect(page.locator('.actions a')).toHaveCount(1);
  await select(page,separate.name);
  await expect(page.locator('.actions a')).toHaveCount(2);
  await expect(page.getByRole('link',{name:/^Register/})).toHaveAttribute('href',separate.registration_url);
  await select(page,fallback.name);
  await expect(page.getByRole('link',{name:/View organizer’s page/})).toHaveAttribute('href',fallback.announcement_url);
});

for (const width of [1366,390]) {
  test(`only current confirmed schedule changes appear beside the schedule at ${width}px`, async ({page}) => {
    const update={...base,id:'rescheduled',name:'Rescheduled workshop',lifecycle:'scheduled',
      field_evidence:{...base.field_evidence,lifecycle:{url,quote:'The workshop has been rescheduled to December 1, 2035.'}},
      announcements:[{url,access:'full',kind:'reschedule'}]};
    const cancelled={...base,id:'cancelled',name:'Cancelled workshop',status:'cancelled',lifecycle:'cancelled'};
    const postponed={...base,id:'postponed',name:'Postponed workshop',status:'postponed',lifecycle:'postponed',start:null};
    const routine={...base,id:'routine',name:'Recently refreshed workshop'};
    const older={...update,id:'older',name:'Old reschedule',field_evidence:base.field_evidence};
    const uncertain={...update,id:'uncertain',name:'Possible reschedule',field_evidence:{lifecycle:{url,quote:'The workshop may be rescheduled.'}}};
    await page.route('**/api/events',route=>route.fulfill({json:{events:[update,cancelled,postponed,routine,older,uncertain],generated_at:'2035-11-02T00:00:00Z'}}));
    await page.setViewportSize({width,height:900}); await page.goto('/');
    for (const [event, text] of [[update,'Rescheduled'],[cancelled,'Cancelled'],[postponed,'Postponed']] as const) {
      await select(page,event.name);
      await expect(page.locator('.notice-lead .paper-status')).toHaveText(text);
      if(event.start) await expect(page.locator('.notice-lead .event-schedule')).toHaveText('Dec 1, 2035');
    }
    for (const event of [routine,older,uncertain]) {
      await select(page,event.name);
      await expect(page.locator('.paper-status')).toHaveCount(0);
      await expect(page.locator('.paper')).not.toContainText(/Last observed|Revision/);
    }
  });
}
