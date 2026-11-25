import {filterTrigger, chooseFilter} from './filter-helpers';
import {test, expect, type Page} from '@playwright/test';

// Browser-only fixtures, never saved or used by collection.
const day = (value: string) => ({raw:value,value,precision:'date',timezone:null});
const base = {
  organizer:'Community builders',region:'Quezon City',geography:'PH',format:'in_person',topics:['community'],
  section:'upcoming',status:'scheduled',start:day('2026-11-25'),end:null,deadline:day('2026-11-20'),
  submission_deadline:day('2026-11-21'),registration_status:'unknown',registration_url:null,
  announcement_url:'https://organizer.example/event',price:{kind:'unknown'},notices:[],announcements:[],
};
const events = [
  {...base,id:'wed-1',name:'Community workshop one'},
  {...base,id:'fri-1',name:'Cloud workshop one',start:day('2026-11-27'),topics:['cloud']},
  {...base,id:'wed-2',name:'Community workshop two'},
  {...base,id:'wed-3',name:'Community workshop three',start:{raw:'2026-11-24T18:00:00Z',value:'2026-11-24T18:00:00Z',precision:'datetime',timezone:'UTC'}},
  {...base,id:'fri-2',name:'Cloud workshop two',start:day('2026-11-27'),topics:['cloud']},
  // A second geography supplies enough trailing content to see the full handoff.
  ...Array.from({length:6},(_,i)=>({...base,id:`international-${i}`,name:`International workshop ${i+1}`,geography:'international_online',format:'online'})),
  {...base,id:'review-known',name:'Review with supported event date',section:'unconfirmed'},
  {...base,id:'review-unknown',name:'Review with only a registration cutoff',section:'unconfirmed',start:null},
  {...base,id:'review-conflict',name:'Review with conflicting event dates',section:'unconfirmed',status:'date_conflict'},
  {...base,id:'parent',name:'Review with parent event schedule',section:'unconfirmed',start:null,parent_event_start:day('2026-11-27')},
];
async function setup(page: Page,width=1366) {
  await page.setViewportSize({width,height:768});
  await page.route('**/api/events',r=>r.fulfill({json:{events,generated_at:'2026-11-25T00:00:00Z'}}));
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(11);
  // Let existing section-entry feedback settle before measuring sticky positions.
  await page.locator('.opportunity-group').evaluateAll(elements=>Promise.all(elements.flatMap(el=>el.getAnimations().map(animation=>animation.finished))));
}

test('groups use the card Manila day, stable ties and geography after combined filters',async({page})=>{
  await setup(page);
  const ph=page.locator('.opportunity-group').first();
  await expect(ph.locator('.event-day-heading')).toHaveText(['Wed, Nov 25','Fri, Nov 27']);
  await expect(ph.locator('.event-day-group').first().locator('.notice-select')).toHaveText(['Community workshop one','Community workshop two','Community workshop three']);
  await expect(page.locator('#notice-wed-3').locator('..').locator('../..').locator('.date-day')).toHaveText('25');
  await expect(page.locator('.opportunity-group').nth(1).locator('.event-day-heading')).toHaveText(['Wed, Nov 25']);
  await page.getByRole('searchbox',{name:'Search events'}).fill('workshop');
  await chooseFilter(filterTrigger(page, 'attendance'), 'in_person');
  await chooseFilter(filterTrigger(page, 'interest'), 'cloud');
  await expect(page.locator('.event-day-heading')).toHaveText(['Fri, Nov 27']);
  await expect(page.locator('.event-card')).toHaveCount(2);
  await page.getByRole('searchbox').fill('no matching event');
  await expect(page.locator('.event-day-group')).toHaveCount(0);
  await page.getByRole('button',{name:'Clear filters',exact:true}).first().click();
  await expect(page.locator('.event-card')).toHaveCount(11);
  await page.getByRole('tab',{name:/Needs confirmation/}).click();
  await expect(page.locator('.event-day-heading')).toHaveText(['Wed, Nov 25','Fri, Nov 27','Date to confirm']);
  await expect(page.locator('.event-day-group').last().locator('.notice-select')).toHaveText(['Review with only a registration cutoff','Review with conflicting event dates']);
  await expect(page.locator('.event-day-group').last().locator('.date-unconfirmed')).toHaveCount(2);
  await expect(page.locator('.event-day-heading time').first()).toHaveAttribute('datetime','2026-11-25');
  await expect(page.locator('.event-day-heading time').nth(1)).toHaveAttribute('datetime','2026-11-27');
});

for(const width of [1366,390,320]) {
  test(`native sticky headings pin, push away and preserve selection scroll at ${width}px`,async({page},testInfo)=>{
    await setup(page,width);
    const desktop=width>760;
    const list=page.locator('.board-list');
    const headings=page.locator('.opportunity-group').first().locator('.event-day-heading');
    const first=headings.nth(0),second=headings.nth(1);
    const listBox=(await list.boundingBox())!;
    const top=desktop?listBox.y:0;
    // Native scrolling only; no synthetic positioning or replaced headings.
    const scrollBy=async(amount:number)=>{
      if(desktop) await list.evaluate((el,n)=>el.scrollBy(0,n),amount);
      else await page.evaluate(n=>window.scrollBy(0,n),amount);
    };
    await scrollBy((await first.boundingBox())!.y-top+80);
    await expect.poll(async()=>(await first.boundingBox())!.y).toBeCloseTo(top,0);
    expect((await second.boundingBox())!.y).toBeGreaterThan(top+50);
    await page.screenshot({path:testInfo.outputPath(`pinned-${width}.png`)});
    // Sample the actual push-away interval, not just before/after positions.
    const height=(await first.boundingBox())!.height;
    await scrollBy((await second.boundingBox())!.y-top-height/2);
    await expect.poll(async()=>(await second.boundingBox())!.y).toBeCloseTo(top+height/2,0);
    const pushed=(await first.boundingBox())!;
    expect(pushed.y).toBeLessThan(top);
    expect(pushed.y+pushed.height).toBeLessThanOrEqual((await second.boundingBox())!.y+1);
    await page.screenshot({path:testInfo.outputPath(`handoff-${width}.png`)});
    await scrollBy(height);
    await expect.poll(async()=>(await second.boundingBox())!.y).toBeCloseTo(top,0);
    const before=await list.evaluate(el=>({list:el.scrollTop,page:window.scrollY}));
    // Choose a fully exposed card so Playwright does not first scroll a title
    // that is partially hidden beneath the sticky heading into view.
    await expect(page.locator('#notice-fri-2')).toBeInViewport({ratio:1});
    await page.locator('#notice-fri-2').click();
    await expect(page.locator('#paper-title')).toHaveText('Cloud workshop two');
    if(!desktop) {
      await page.getByRole('button',{name:'Back to the board'}).click();
      await expect(page.locator('#notice-fri-2')).toBeFocused();
    }
    expect(await list.evaluate(el=>({list:el.scrollTop,page:window.scrollY}))).toEqual(before);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await page.screenshot({path:testInfo.outputPath(`next-day-${width}.png`)});
  });
}

for (const width of [1366, 320]) {
  test(`Past shows latest Manila days first with stable ties and unresolved dates last at ${width}px`, async ({page}) => {
    const past = {...base, section:'past', status:'finished'};
    const fixture = [
      {...past,id:'oldest',name:'Previous year',start:day('2025-10-06'),deadline:day('2027-01-01')},
      {...past,id:'november',name:'November event',start:day('2026-11-24')},
      {...past,id:'unknown',name:'Unresolved event',start:null},
      {...past,id:'october',name:'October event',section:'finished',start:day('2026-10-04')},
      {...past,id:'rollover',name:'Latest Manila day',start:{raw:'2026-11-24T18:00:00Z',value:'2026-11-24T18:00:00Z',precision:'datetime',timezone:'UTC'}},
      {...past,id:'tie',name:'Same day second',start:day('2026-11-25')},
      {...past,id:'conflict',name:'Conflicting event',status:'date_conflict',start:day('2026-12-01')},
      {...past,id:'online-old',name:'Online older',geography:'international_online',start:day('2026-10-01')},
      {...past,id:'online-new',name:'Online latest',geography:'international_online',start:day('2026-11-26')},
    ];
    await page.setViewportSize({width,height:768});
    await page.route('**/api/events',r=>r.fulfill({json:{events:fixture}}));
    await page.goto('/');
    await page.getByRole('tab',{name:/Past/}).click();
    const expected = ['Latest Manila day','Same day second','November event','October event','Previous year','Unresolved event','Conflicting event','Online latest','Online older'];
    await expect(page.locator('.notice-select')).toHaveText(expected);
    const ph = page.locator('.opportunity-group').first();
    await expect(ph.locator('.event-day-heading')).toHaveText(['Wed, Nov 25','Tue, Nov 24','Sun, Oct 4','Mon, Oct 6','Date to confirm']);
    await expect(ph.locator('.event-day-heading time').first()).toHaveAttribute('datetime','2026-11-25');
    await expect(ph.locator('.event-day-heading time').nth(3)).toHaveAttribute('datetime','2025-10-06');
    await page.getByRole('searchbox').fill('October');
    await expect(page.locator('.notice-select')).toHaveText(['October event']);
    await page.getByRole('button',{name:'Clear filters',exact:true}).first().click();
    await expect(page.locator('.notice-select')).toHaveText(expected);
    await expect(page.getByRole('tab',{name:/Past/})).toHaveAttribute('aria-selected','true');
  });
}
