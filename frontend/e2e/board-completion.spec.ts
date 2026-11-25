import {filterTrigger, chooseFilter, expectFilter} from './filter-helpers';
import {test,expect,type Page} from '@playwright/test';

const url='https://organizer.example/workshop';
const date={raw:'2035-12-01',value:'2035-12-01',precision:'date',timezone:null};
const base={id:'free',name:'Community workshop',organizer:'Community builders',section:'upcoming',status:'scheduled',
  start:date,end:null,deadline:null,format:'in_person',region:'NCR',geography:'PH',topics:['community'],
  registration_status:'open',registration_url:null,announcement_url:url,price:{kind:'free'},
  notices:[],description:'Long programme details.\n'.repeat(100),
  field_evidence:{description:{url,quote:'Build useful tools together at our community workshop.'}},
  announcements:[{url,access:'full',kind:'event',first_seen:'2035-11-23T16:30:00Z'}],
};
const fixtures=[base,{...base,id:'zero',name:'Zero fee workshop',price:{kind:'paid',amount:0}},
  {...base,id:'paid',name:'Paid workshop',price:{kind:'paid',amount:500,currency:'PHP'},format:'online',topics:['cloud']},
  {...base,id:'unknown',name:'Unconfirmed workshop',start:null,status:'date_conflict',section:'unconfirmed',format:'unknown',registration_status:'unknown',price:{kind:'unknown'},
    field_evidence:{description:{url,quote:'Search-only text must not be represented as a fetched excerpt.'}},announcements:[{url,access:'search_only',kind:'lead'}]},
  ...Array.from({length:20},(_,i)=>({...base,id:`next-${i}`,name:`Next workshop ${i}`,price:{kind:'unknown'}})),
];
async function setup(page:Page,width=1366){
  await page.setViewportSize({width,height:768});
  await page.route('**/api/events',r=>r.fulfill({json:{events:fixtures,generated_at:'2035-11-24T00:00:00Z'}}));
  await page.goto('/');await expect(page.locator('.event-card')).toHaveCount(23);
}
test('yellow note contains the supported facts without a description; missing fields remain honest',async({page})=>{
  await setup(page);
  const note=page.getByRole('region',{name:'What we found'});
  await expect(note.locator('.attendance-detail')).toHaveText('How to attendIn person');
  await expect(note.locator('.interests-detail')).toHaveText('InterestsCommunity');
  await expect(note.locator('.signup-detail')).toHaveText('SignupRegistration open');
  await expect(note.locator('.price-detail')).toHaveText('PriceFree');
  await expect(page.locator('.collected-grid')).toHaveCount(1);
  await expect(note.locator('blockquote')).toHaveCount(0);
  await expect(note).not.toContainText(base.field_evidence.description.quote);
  await expect(note).not.toContainText('Long programme details.');
  await expect(page.locator('.event-description')).toContainText('Long programme details.');
  await expect(note.locator('.missing-fields')).toContainText('Missing: time, exact venue');
  await expect(note.locator('.missing-fields')).not.toContainText('cost');
  await expect(note).toHaveCSS('background-color','rgb(250, 227, 139)');
  await page.getByRole('tab',{name:/Needs confirmation/}).click();
  await expect(note.locator('blockquote')).toHaveCount(0);
  await expect(note.locator('.attendance-detail, .signup-detail, .price-detail')).toHaveCount(0);
  await expect(note.locator('.missing-fields')).toContainText('confirmed event date, time, attendance format, cost, signup status');
  await expect(note).not.toContainText('First saved');
  // An unrelated source's description also stays out of the fact note.
  await page.route('**/api/events',r=>r.fulfill({json:{events:[{...fixtures[3],announcements:[{url:'https://organizer.example/another-event',access:'full',kind:'event'}]}]}}));
  await page.reload();await page.getByRole('tab',{name:/Needs confirmation/}).click();
  await expect(note.locator('blockquote')).toHaveCount(0);
  // A city alone is not an exact venue; adding a retained Place name resolves it.
  for(const name of [null,'Community Hall']) {
    const place={'@type':'Place',name,address:{addressLocality:'Quezon City'}};
    await page.route('**/api/events',r=>r.fulfill({json:{events:[{...base,field_evidence:{...base.field_evidence,format:{url,quote:`Schema.org eventAttendanceMode=OfflineEventAttendanceMode; location=${JSON.stringify(place)}`}}}]}}));
    await page.reload();
    if(name) await expect(note.locator('.missing-fields')).not.toContainText('exact venue');
    else await expect(note.locator('.missing-fields')).toContainText('exact venue');
  }
});
for(const width of [1366,390,320])test(`compact dropdowns combine and clear without overflow at ${width}px`,async({page},info)=>{
  await setup(page,width);
  const interest=filterTrigger(page, 'interest');
  const attendance=filterTrigger(page, 'attendance');
  await expect(page.locator('.filter-trigger')).toHaveCount(2);
  await expect(page.locator('.filter-chip')).toHaveCount(0);
  await chooseFilter(interest, 'community');
  await chooseFilter(attendance, 'in_person');
  await page.getByRole('searchbox').fill('Zero');
  await expect(page.locator('.event-card')).toHaveCount(1);
  await chooseFilter(interest, '');
  await expectFilter(interest, '');
  await expect(page.getByRole('searchbox')).toHaveValue('Zero');
  await chooseFilter(attendance, 'online');
  await expect(page.locator('.event-day-group')).toHaveCount(0);
  await page.getByRole('button',{name:'Clear filters',exact:true}).first().click();
  await expectFilter(interest, '');
  await expectFilter(attendance, '');
  await expect(page.locator('.event-card')).toHaveCount(23);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath(`dropdowns-${width}.png`)});
  if(width<=760) await page.locator('.notice-select').first().click();
  await expect(page.locator('.found-note .collected-grid')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.locator('.found-note').screenshot({path:info.outputPath(`facts-${width}.png`)});
});
test('list and notice share idle/reveal scrollbars and wheel boundaries never move the notice',async({page})=>{
  await setup(page);
  const list=page.getByRole('region',{name:'Event listings'}), paper=page.getByRole('region',{name:'Selected event notice'});
  const geometry=()=>paper.evaluate(el=>({x:el.getBoundingClientRect().x,y:el.getBoundingClientRect().y,width:el.clientWidth,page:scrollY}));
  const before=await geometry();
  for(const panel of [list,paper]) {
    await expect(panel).toHaveAttribute('data-scrolling','false');
    await expect(panel).toHaveCSS('scrollbar-gutter','stable');
    await expect(panel).toHaveCSS('overscroll-behavior-y','contain');
    const appearance=()=>panel.evaluate(el=>({thumb:getComputedStyle(el,'::-webkit-scrollbar-thumb').backgroundColor,track:getComputedStyle(el,'::-webkit-scrollbar-track').backgroundColor}));
    const idle=await appearance();
    await panel.hover();
    await expect(panel).toHaveAttribute('data-scrolling','true');
    expect(await appearance()).not.toEqual(idle);
    expect(await geometry()).toEqual(before);
    for(const [edge,delta] of [[0,-600],[100000,600]]) {
      await panel.evaluate((el,y)=>{el.scrollTop=y;},edge);
      await page.mouse.wheel(0,delta);
      // Two frames plus idle expiry allow scroll chaining and layout changes to surface.
      await expect(panel).toHaveAttribute('data-scrolling','false',{timeout:2500});
      expect(await geometry()).toEqual(before);
      expect(await appearance()).toEqual(idle);
    }
  }
  await page.emulateMedia({forcedColors:'active'});
  for(const panel of [list,paper]) {
    await expect(panel).toHaveCSS('scrollbar-color','auto');
    expect(await panel.evaluate(el=>getComputedStyle(el,'::-webkit-scrollbar-thumb').backgroundColor)).not.toBe('rgba(0, 0, 0, 0)');
  }
});

test('short notices also consume wheel movement without shifting the panel',async({page})=>{
  await page.setViewportSize({width:1366,height:900});
  await page.route('**/api/events',r=>r.fulfill({json:{events:[{...base,name:'Short notice',description:null,field_evidence:{},topics:[],region:null,format:'unknown',registration_status:'unknown',price:{kind:'unknown'}}]}}));
  await page.goto('/');
  const paper=page.getByRole('region',{name:'Selected event notice'});
  await expect(paper).toBeVisible();
  expect(await paper.evaluate(el=>el.scrollHeight<=el.clientHeight)).toBeTruthy();
  const before=await paper.boundingBox();
  await paper.hover();await page.mouse.wheel(0,700);
  await expect(paper).toHaveAttribute('data-scrolling','false',{timeout:2500});
  expect(await paper.boundingBox()).toEqual(before);
  expect(await page.evaluate(()=>scrollY)).toBe(0);
});
