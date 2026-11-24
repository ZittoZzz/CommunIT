import { test, expect, type Page } from '@playwright/test';

// Display-only public API fixtures, never runtime or discovery data.
const day = (value: string) => ({raw:value, value, precision:'date', timezone:null});
const url = 'https://organizer.example/events/community-workshop';
const place = {'@type':'Place',name:'Community Learning and Technology Centre',address:{
  '@type':'PostalAddress',addressLocality:'Quezon City',
  streetAddress:'Fourth floor, East Wing, University Innovation Building, 123 Commonwealth Avenue',
}};
const base = {
  id:'workshop',name:'Community cloud workshop',organizer:'Campus community builders',
  region:'Philippines',format:'in_person',attendance_options:['Onsite'],geography:'PH',topics:['cloud'],
  section:'upcoming',status:'scheduled',start:day('2035-12-01'),end:null,
  competition_date:null,parent_event_start:null,parent_event_end:null,
  deadline:day('2035-11-28'),submission_deadline:null,registration_opens:null,
  registration_status:'open',registration_url:'https://signup.example/workshop',organizer_event_url:url,
  announcement_url:'https://publisher.example/announcement',price:{kind:'free'},eligibility:'University students',
  account_required:null,description:'Bring your laptop for the guided workshop.',summary:null,
  posted_at:null,first_seen:null,last_checked:null,notices:[],
  field_evidence:{format:{url,quote:`Schema.org eventAttendanceMode=OfflineEventAttendanceMode; location=${JSON.stringify(place)}`}},
  announcements:[{url,kind:'announcement',access:'full'}],
};
const long = {...base,id:'long',name:'Philippine Student Workshop on Cloud Infrastructure, Community Projects, and Reliable Software Delivery',start:day('2035-12-02')};

async function setup(page: Page, width: number, events: unknown[] = [base,long]) {
  await page.setViewportSize({width,height:900});
  await page.addInitScript(() => {
    document.addEventListener('animationstart', event => {
      if (event.animationName === 'stamp-in') {
        document.documentElement.dataset.stampStarts = String(Number(document.documentElement.dataset.stampStarts || 0) + 1);
      }
    });
  });
  await page.route('**/api/events',route=>route.fulfill({json:{events,generated_at:'2035-11-20T00:00:00Z'}}));
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(events.length);
}
async function matchingStamp(page: Page) {
  const card = page.locator('.event-card.is-selected .event-date');
  const notice = page.locator('.notice-lead .event-date');
  expect(await notice.innerHTML()).toBe(await card.innerHTML());
  for (const attribute of ['datetime','aria-label']) {
    expect(await notice.getAttribute(attribute)).toBe(await card.getAttribute(attribute));
  }
}
const stampStarts = (page: Page) => page.locator('html').getAttribute('data-stamp-starts').then(value=>Number(value || 0));

for (const width of [1366,390,320]) {
  test(`matching stamp, long title/address and distinct deadline wrap at ${width}px`, async ({page},testInfo) => {
    const errors: string[]=[]; page.on('pageerror',error=>errors.push(error.message));
    await setup(page,width);
    await page.locator('#notice-workshop').click();
    await matchingStamp(page);
    await page.screenshot({path:testInfo.outputPath(`notice-${width}.png`),fullPage:width<761});
    if (width<761) await page.getByRole('button',{name:'Back to the board'}).click();
    await page.locator('#notice-long').click();
    await expect(page.locator('#paper-title')).toHaveText(long.name);
    await matchingStamp(page);
    await expect(page.locator('.notice-lead .date-month')).toHaveCSS('background-color','rgb(41, 77, 60)');
    await expect(page.locator('.notice-lead .event-schedule')).toHaveText('Dec 2, 2035');
    await expect(page.locator('.notice-lead .event-schedule')).not.toContainText(/PHT|12:00/);
    await expect(page.locator('.paper .schedule-detail, .paper .location-detail')).toHaveCount(2);
    await expect(page.locator('.collected-grid .schedule-detail, .collected-grid .location-detail')).toHaveCount(0);
    await expect(page.locator('.venue-address')).toHaveText(place.address.streetAddress);
    await expect(page.locator('.deadline-detail')).toHaveText('Registration deadline2035-11-28');
    await expect(page.getByRole('link',{name:/View organizer’s page/})).toHaveAttribute('href',url);
    await expect(page.getByRole('link',{name:/^Register/})).toHaveAttribute('href',base.registration_url);
    for (const selector of ['#paper-title','.venue-address','.notice-lead','.actions']) {
      const box = await page.locator(selector).boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width);
      expect(await page.locator(selector).evaluate(el=>el.scrollWidth<=el.clientWidth)).toBeTruthy();
    }
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await page.screenshot({path:testInfo.outputPath(`long-${width}.png`),fullPage:width<761});
    expect(errors).toEqual([]);
  });
}

test('uncertainty, parent-event dates and deadlines stay distinct; empty residual grids are omitted', async ({page}) => {
  const sparse = {...base,id:'unknown',name:'Unconfirmed schedule',start:null,region:null,format:'unknown',attendance_options:[],topics:[],
    price:null,eligibility:null,registration_status:'unknown',deadline:null,field_evidence:{},registration_url:url};
  const conflict = {...sparse,id:'conflict',name:'Conflicting schedule',status:'date_conflict',start:day('2035-12-03'),
    review:{required:true,reasons:['The published dates disagree. Check with the organizer.']},notices:['The event date is unresolved.']};
  const parent = {...sparse,id:'parent',name:'CTF within a conference',parent_event_start:day('2035-12-04'),parent_event_end:day('2035-12-06'),deadline:day('2035-11-30')};
  await setup(page,1366,[sparse,conflict,parent]);
  for (const event of [sparse,conflict]) {
    await page.locator(`#notice-${event.id}`).click();
    await matchingStamp(page);
    await expect(page.locator('.notice-lead .date-unconfirmed')).toHaveText('Date unconfirmed');
    await expect(page.locator('.event-schedule, .collected-details')).toHaveCount(0);
  }
  const notes = await page.locator('.event-alerts').boundingBox();
  const lead = await page.locator('.notice-lead').boundingBox();
  expect(notes!.y+notes!.height).toBeLessThan(lead!.y);
  await expect(page.locator('.paper-status')).toHaveText('Conflicting dates');
  await page.locator('#notice-parent').click();
  await matchingStamp(page);
  await expect(page.locator('.notice-lead .event-date')).toHaveAttribute('aria-label',/Parent event date/);
  await expect(page.locator('.notice-lead .parent-schedule')).toContainText('Parent event schedule');
  await expect(page.locator('.parent-schedule')).toContainText('These dates do not establish the complete CTF schedule.');
  await expect(page.locator('.event-schedule')).toHaveCount(0);
  await expect(page.locator('.deadline-detail')).toHaveText('Registration deadline2035-11-30');
  await expect(page.locator('.paper .actions a')).toHaveCount(1);
});

for (const width of [1366,390]) {
  test(`stamp presses once on event selection and mobile reopening at ${width}px`, async ({page}) => {
    await page.emulateMedia({reducedMotion:'no-preference'});
    await setup(page,width);
    if(width>760) await expect.poll(()=>stampStarts(page)).toBe(1);
    const before = await stampStarts(page);
    await page.locator('#notice-long').click();
    await expect.poll(()=>stampStarts(page)).toBe(before+1);
    const stamp = page.locator('.notice-lead .event-date');
    await expect(stamp).toHaveCSS('animation-duration','0.21s');
    await expect(stamp).toHaveCSS('animation-iteration-count','1');
    await expect(stamp).toHaveCSS('transform','none');
    await matchingStamp(page);
    if(width<761) {
      await page.getByRole('button',{name:'Back to the board'}).click();
      await expect(page.locator('#notice-long')).toBeFocused();
      await page.keyboard.press('Enter');
    } else await page.locator('#notice-workshop').click();
    await expect.poll(()=>stampStarts(page)).toBe(before+2);
    await expect(stamp).toHaveCSS('transform','none');
    await matchingStamp(page);
  });
}

test('reduced motion suppresses stamp and link movement while keyboard focus remains visible', async ({page}) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  await setup(page,390);
  await page.locator('#notice-long').click();
  await expect(page.locator('.notice-lead .event-date')).toHaveCSS('animation-name','none');
  expect(await stampStarts(page)).toBe(0);
  // Mobile selection focuses the title; Tab proceeds to the first real action.
  await expect(page.locator('#paper-title')).toBeFocused();
  await page.keyboard.press('Tab');
  const primary = page.getByRole('link',{name:/View organizer’s page/});
  await expect(primary).toBeFocused();
  await expect(primary).toHaveCSS('outline-style','solid');
  await expect(primary).toHaveCSS('outline-width','3px');
  await primary.hover();
  await expect(primary).toHaveCSS('transform','none');
  await expect(primary).toHaveCSS('transition-duration','0s');
  await page.mouse.down();
  await expect(primary).toHaveCSS('transform','none');
  await page.mouse.move(0,0); await page.mouse.up();
});
