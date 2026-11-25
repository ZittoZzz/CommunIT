import {filterTrigger, chooseFilter, expectFilter} from './filter-helpers';
import {test, expect, type Page} from '@playwright/test';

const key = 'communit:board:v1';
const day = {raw:'2035-12-01',value:'2035-12-01',precision:'date',timezone:null};
const base = {id:'one',name:'Workshop 0',organizer:'Community builders',section:'upcoming',status:'scheduled',
  start:day,format:'in_person',region:'NCR',topics:['community'],registration_status:'open',
  announcement_url:'https://organizer.example/event',notices:[],announcements:[],description:'Programme details.\n'.repeat(80)};
const events = Array.from({length:18},(_,i)=>({...base,id:`event-${i}`,name:`Workshop ${i}`}));
const directory = {events,generated_at:'2035-11-24T00:00:00Z',listings_updated_at:'2035-11-23T08:00:00Z'};
const gate = () => { let release!: () => void; const promise = new Promise<void>(resolve=>{release=resolve;}); return {promise,release}; };
const saved = (page:Page) => page.evaluate(key=>JSON.parse(sessionStorage.getItem(key) || 'null'),key);
async function observePaints(page:Page) {
  await page.addInitScript(()=>{
    const state={ticketSeen:false,firstBoardAtPaint:false};
    Object.assign(window,{loadingPaints:state});
    const observer=new MutationObserver(()=>{
      if(document.querySelector('.opening-ticket'))state.ticketSeen=true;
      if(document.querySelector('.board-split'))requestAnimationFrame(()=>{state.firstBoardAtPaint=!!document.querySelector('.event-card, .board .empty');});
    });
    observer.observe(document,{childList:true,subtree:true});
  });
}
async function expectSavedPaint(page:Page) {
  await expect(page.locator('.opening-ticket')).toHaveCount(0);
  await expect.poll(()=>page.evaluate(()=>(window as any).loadingPaints.firstBoardAtPaint)).toBe(true);
  expect(await page.evaluate(()=>(window as any).loadingPaints.ticketSeen)).toBe(false);
  expect(await page.evaluate(()=>(performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming).type)).toBe('reload');
}

test('first visit shows only the pinned ticket until the real response, then saves public data',async({page},info)=>{
  const pending=gate();await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill({json:{...directory,manual_collection:{token:'not-for-storage'}}});});
  await page.goto('/');
  await expect(page.getByRole('link',{name:'CommunIT',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Opening the board'})).toBeVisible();
  await expect(page.locator('.opening-ticket')).toContainText('Loading event listings…');
  await expect(page.locator('.board, .controls, .refresh-slip')).toHaveCount(0);
  expect(await saved(page)).toBeNull();
  await page.screenshot({path:info.outputPath('first-visit.png')});
  await page.getByRole('searchbox').fill('Workshop 1');
  pending.release();
  await expect(page.locator('.opening-ticket')).toHaveCount(0);
  await expect(page.locator('.event-card')).toHaveCount(9);
  await expect(page.getByRole('searchbox')).toHaveValue('Workshop 1');
  expect((await saved(page)).data.events).toHaveLength(18);
  expect((await saved(page)).data.manual_collection).toBeUndefined();
  await expect(page.getByRole('searchbox')).toBeFocused();
});

test('reload before any success still opens with the ticket; failure and Retry recover',async({page})=>{
  let fail=false;const pending=gate();
  await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill(fail?{status:503,body:'unavailable'}:{json:directory});});
  await page.goto('/');await expect(page.locator('.opening-ticket')).toBeVisible();
  await page.reload();await expect(page.locator('.opening-ticket')).toBeVisible();expect(await saved(page)).toBeNull();
  fail=true;pending.release();await expect(page.getByRole('heading',{name:'Couldn’t open the board'})).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Couldn’t load event listings');
  expect(await saved(page)).toBeNull();
  fail=false;await page.getByRole('button',{name:'Retry',exact:true}).click();await expect(page.locator('.event-card')).toHaveCount(18);
});

for(const [name,value] of [
  ['visited flag','true'],['broken JSON','{'],['unsupported version',JSON.stringify({version:0,data:directory})],
  ['invalid event',JSON.stringify({version:1,data:{events:[{...base,notices:{}}]}})],
] as const)test(`unusable saved board (${name}) takes the ticket path`,async({page})=>{
  await page.addInitScript(({key,value})=>sessionStorage.setItem(key,value),{key,value});
  const pending=gate();await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill({json:directory});});
  await page.goto('/');await expect(page.locator('.opening-ticket')).toBeVisible();await expect(page.locator('.board')).toHaveCount(0);
  pending.release();await expect(page.locator('.event-card')).toHaveCount(18);
});

test('successful empty data is saved and paints an empty board on real reload',async({page})=>{
  let pending=gate();pending.release();await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill({json:{...directory,events:[]}});});
  await page.goto('/');await expect(page.getByRole('heading',{name:'No upcoming events recorded yet.'})).toBeVisible();
  expect((await saved(page)).data.events).toEqual([]);
  pending=gate();await observePaints(page);await page.reload();
  await expect(page.locator('.refresh-slip')).toHaveText('Checking listings…');await expectSavedPaint(page);
  await expect(page.getByRole('heading',{name:'No upcoming events recorded yet.'})).toBeVisible();
  pending.release();await expect(page.locator('.refresh-slip')).toContainText('Board up to date');
});

test('real reload paints saved listings first and preserves selection, filters and scroll during refresh',async({page},info)=>{
  await page.setViewportSize({width:1366,height:768});let pending=gate();pending.release();let response=directory;
  await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill({json:response});});
  await page.goto('/');await expect(page.locator('.event-card')).toHaveCount(18);
  pending=gate();await observePaints(page);await page.reload();await expectSavedPaint(page);
  const slip=page.locator('.refresh-slip');await expect(slip).toContainText('Checking listings…');
  const boardBox=await page.locator('.board-split').boundingBox();
  await page.screenshot({path:info.outputPath('refresh-desktop.png')});
  await page.getByRole('tab',{name:/Past/}).click();await expect(page.locator('.board .empty')).toBeVisible();
  await page.getByRole('tab',{name:/Upcoming/}).click();
  await page.getByRole('searchbox').fill('Workshop');
  await chooseFilter(filterTrigger(page, 'interest'), 'community');
  await chooseFilter(filterTrigger(page, 'attendance'), 'in_person');
  const selected=page.locator('#notice-event-12');await selected.click();
  await expect(page.locator('#paper-title')).toHaveText('Workshop 12');
  await page.locator('.paper-scroll').evaluate(el=>{el.scrollTop=120;});
  const position=()=>page.evaluate(()=>({list:document.querySelector('.board-list')!.scrollTop,paper:document.querySelector('.paper-scroll')!.scrollTop,page:scrollY}));
  const before=await position();response={...directory,events:events.map(e=>e.id==='event-12'?{...e,name:'Workshop 12 updated'}:e)};
  pending.release();await expect(slip).toContainText('Board up to date');
  await expect(page.locator('#paper-title')).toHaveText('Workshop 12 updated');
  await expect(selected).toHaveAttribute('aria-pressed','true');await expect(selected).toBeFocused();
  expect(await position()).toEqual(before);
  await expect(page.getByRole('searchbox')).toHaveValue('Workshop');
  await expectFilter(filterTrigger(page, 'interest'), 'community');
  await expectFilter(filterTrigger(page, 'attendance'), 'in_person');
  await expect(slip.locator('.refresh-seal')).toHaveText('✓');await expect(slip).toBeHidden({timeout:4000});
  // Filtering adds Clear filters; compare the panel's top rather than its height.
  expect((await page.locator('.board-split').boundingBox())!.y).toBe(boardBox!.y);
  expect(await position()).toEqual(before);
});

for(const width of [390,320])test(`failed reload keeps saved board; Retry and mobile selection survive refresh at ${width}px`,async({page},info)=>{
  await page.setViewportSize({width,height:768});let fail=false;let pending=gate();pending.release();let response=directory;
  await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill(fail?{status:503,body:'unavailable'}:{json:response});});
  await page.goto('/');await expect(page.locator('.event-card')).toHaveCount(18);const cache=await saved(page);
  fail=true;await page.reload();const slip=page.locator('.refresh-slip');await expect(slip).toContainText('Couldn’t refresh · Showing saved listings');
  await expect(page.locator('.event-card')).toHaveCount(18);expect(await saved(page)).toEqual(cache);
  const controls=(await page.locator('.controls').boundingBox())!,nav=(await page.locator('header').boundingBox())!,status=(await slip.boundingBox())!;
  expect(status.y).toBeGreaterThanOrEqual(nav.y+nav.height);expect(status.y+status.height).toBeLessThanOrEqual(controls.y);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:info.outputPath(`refresh-failure-${width}.png`)});
  fail=false;pending=gate();await slip.getByRole('button',{name:'Retry',exact:true}).click();await expect(slip).toContainText('Checking listings…');
  await page.getByRole('searchbox').fill('Workshop');await chooseFilter(filterTrigger(page, 'interest'), 'community');
  const card=page.locator('#notice-event-7');await card.scrollIntoViewIfNeeded();
  // Pointer actions may scroll again while settling the hover/visibility check.
  // Back must restore the actual selection position, not the earlier scroll command.
  await card.evaluate(el=>el.addEventListener('pointerdown',()=>{(el as HTMLElement).dataset.scrollBeforeSelection=String(scrollY);},{once:true}));
  await card.click();const returnY=Number(await card.getAttribute('data-scroll-before-selection'));expect(returnY).toBeGreaterThan(0);
  response={...directory,events:events.map(e=>e.id==='event-7'?{...e,name:'Workshop 7 updated'}:e)};pending.release();
  await expect(page.locator('#paper-title')).toHaveText('Workshop 7 updated');await expect(page.locator('#paper-title')).toBeFocused();
  await page.getByRole('button',{name:'Back to the board'}).click();await expect(card).toBeFocused();
  expect(await page.evaluate(()=>scrollY)).toBe(returnY);await expect(page.getByRole('searchbox')).toHaveValue('Workshop');
});

test('a removed selection uses the existing fallback; an invalid response cannot replace saved data',async({page})=>{
  let response:unknown=directory;await page.route('**/api/events',route=>route.fulfill({json:response}));
  await page.goto('/');await page.locator('#notice-event-1').click();
  response={...directory,events:events.filter(e=>e.id!=='event-1')};await page.getByRole('button',{name:'Refresh saved listings'}).click();
  await expect(page.locator('#paper-title')).toHaveText('Workshop 0');const cache=await saved(page);
  response={events:[null]};await page.getByRole('button',{name:'Refresh saved listings'}).click();
  await expect(page.locator('.refresh-slip')).toContainText('Couldn’t refresh');await expect(page.locator('.event-card')).toHaveCount(17);expect(await saved(page)).toEqual(cache);
});

test('blocked browser storage does not prevent loading or Retry',async({page})=>{
  await page.addInitScript(()=>{Object.defineProperty(window,'sessionStorage',{get(){throw new DOMException('Blocked','SecurityError');}});});
  let fail=false;await page.route('**/api/events',route=>route.fulfill(fail?{status:503}:{json:directory}));
  await page.goto('/');await expect(page.locator('.event-card')).toHaveCount(18);
  fail=true;await page.reload();await expect(page.locator('.opening-ticket')).toBeVisible();await expect(page.getByRole('button',{name:'Retry'})).toBeVisible();
  fail=false;await page.getByRole('button',{name:'Retry'}).click();await expect(page.locator('.event-card')).toHaveCount(18);
});

test('reduced motion uses static ticket and refresh indicators with an accessible success announcement',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});let pending=gate();await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill({json:directory});});
  await page.goto('/');await expect(page.locator('.opening-stamp')).toHaveCSS('animation-name','none');pending.release();await expect(page.locator('.event-card')).toHaveCount(18);
  pending=gate();await page.reload();await expect(page.locator('.refresh-slip')).toHaveCSS('animation-name','none');
  for(const card of await page.locator('.refresh-stack i').all())await expect(card).toHaveCSS('animation-name','none');
  await page.getByRole('searchbox').focus();pending.release();await expect(page.locator('.refresh-seal')).toHaveText('✓');
  await expect(page.locator('.refresh-seal')).toHaveCSS('animation-name','none');await expect(page.locator('.refresh-slip')).toHaveCSS('transition-duration','0s');
  await expect(page.getByRole('status').filter({hasText:'Board up to date'})).toBeVisible();await expect(page.getByRole('searchbox')).toBeFocused();
});

test('keyboard Retry retains focus through refresh and success stays until focus leaves',async({page})=>{
  let fail=false;let pending=gate();pending.release();await page.route('**/api/events',async route=>{await pending.promise;await route.fulfill(fail?{status:503}:{json:directory});});
  await page.goto('/');await expect(page.locator('.event-card')).toHaveCount(18);fail=true;await page.reload();
  const retry=page.locator('.refresh-slip button');await expect(retry).toHaveText('Retry');await retry.focus();
  fail=false;pending=gate();await page.keyboard.press('Enter');await expect(retry).toBeFocused();await expect(retry).toHaveAttribute('aria-disabled','true');
  pending.release();await expect(retry).toHaveText('Dismiss');await expect(retry).toBeFocused();
  await page.getByRole('searchbox').focus();await expect(page.locator('.refresh-slip')).toHaveAttribute('data-leaving','true',{timeout:3000});
  await expect(page.locator('.refresh-slip')).toBeHidden();await expect(page.getByRole('searchbox')).toBeFocused();
});
