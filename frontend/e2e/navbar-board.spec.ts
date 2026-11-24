import { test, expect, type Page } from '@playwright/test';

// Browser-only API fixtures; they never enter runtime discovery or saved data.
const day = (value: string) => ({raw:value,value,precision:'date',timezone:null});
const base = {
  id:'upcoming',name:'Community technology workshop',organizer:'Campus community builders',
  region:'Quezon City',geography:'PH',format:'in_person',topics:['community'],
  section:'upcoming',status:'scheduled',start:day('2035-12-01'),end:null,deadline:null,
  registration_opens:null,registration_status:'unknown',registration_url:null,
  announcement_url:'https://organizer.example/workshop',eligibility:null,price:{kind:'unknown'},
  summary:null,description:'A public workshop with a detailed programme.\n'.repeat(90),
  posted_at:null,first_seen:null,last_checked:null,notices:[],announcements:[],stage:'main',edition:'2035',
};
const events = [base,
  {...base,id:'next',name:'Another community technology workshop',start:day('2035-12-02')},
  {...base,id:'online',name:'Community technology stream',format:'online'},
  {...base,id:'past',name:'Community technology workshop last month',section:'finished',status:'finished',start:day('2035-10-01')},
  {...base,id:'unknown',name:'Community technology workshop awaiting dates',section:'unconfirmed',status:'schedule_tba',start:null},
  {...base,id:'archive',name:'Community technology lead archived',section:'archived',status:'undated_lead',start:null},
];
async function setup(page: Page, width=1366, fixture=events) {
  await page.setViewportSize({width,height:768});
  await page.route('**/api/events',route=>route.fulfill({json:{events:fixture,generated_at:'2035-11-01T00:00:00Z',listings_updated_at:'2035-11-01T00:00:00Z'}}));
  await page.goto('/');
  await expect(page.locator('.event-card')).toHaveCount(fixture.filter(event=>event.section==='upcoming').length);
}

test('1366×768 arrival shows navbar search, both filters, first card and selected notice', async ({page},testInfo) => {
  await setup(page);
  const search = page.locator('.topbar').getByRole('searchbox',{name:'Search events'});
  for(const control of [search,page.getByRole('combobox',{name:'Browse by interest'}),page.getByRole('combobox',{name:'How to attend'}),page.locator('.event-card').first(),page.locator('#paper-title')]) {
    await expect(control).toBeInViewport({ratio:1});
  }
  const browse = await page.locator('.browse-column').boundingBox();
  const notice = await page.locator('.pinned-detail').boundingBox();
  expect(browse!.width).toBeGreaterThan(notice!.width);
  expect(Math.abs(browse!.y-notice!.y)).toBeLessThanOrEqual(2);
  expect(browse!.x+browse!.width).toBeLessThan(notice!.x);
  expect(await page.evaluate(()=>window.scrollY)).toBe(0);
  await expect(page.locator('.hero, .explore-interests, .interest-chip')).toHaveCount(0);
  await expect(page.locator('.board-doodles')).not.toBeVisible();
  await expect(page.locator('.directory-updated')).toContainText('Nov 1, 2035, 8:00 AM PHT');
  await page.screenshot({path:testInfo.outputPath('first-screen-1366.png'),fullPage:false});
});

for(const width of [390,320]) {
  test(`phone controls follow navbar search, filters, tabs and cards without overflow at ${width}px`, async ({page},testInfo) => {
    await setup(page,width);
    const search = page.getByRole('searchbox',{name:'Search events'});
    const brand = await page.getByRole('link',{name:'CommunIT',exact:true}).boundingBox();
    const searchBox = await search.boundingBox();
    expect(searchBox!.y).toBeGreaterThanOrEqual(brand!.y+brand!.height);
    const controls = await page.getByRole('region',{name:'Find events'}).boundingBox();
    const tabs = await page.getByRole('tablist').boundingBox();
    const card = await page.locator('.event-card').first().boundingBox();
    expect(controls!.y).toBeGreaterThanOrEqual(searchBox!.y+searchBox!.height);
    expect(tabs!.y).toBeGreaterThanOrEqual(controls!.y+controls!.height);
    expect(card!.y).toBeGreaterThanOrEqual(tabs!.y+tabs!.height);
    for(const control of await page.locator('.filter select, [role=tab]').all()) {
      await expect(control).toBeVisible();
      const box = await control.boundingBox();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x+box!.width).toBeLessThanOrEqual(width);
      expect(await control.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBeTruthy();
      expect(await control.evaluate(el=>parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(11);
    }
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await expect(page.locator('.paper')).not.toBeVisible();
    await expect(page.locator('.board-doodles')).not.toBeVisible();
    await page.screenshot({path:testInfo.outputPath(`board-${width}.png`),fullPage:false});
    await page.locator('#notice-upcoming').click();
    await expect(page.locator('#paper-title')).toHaveText(base.name);
    await expect(page.locator('#paper-title')).toBeFocused();
    const notice = await page.locator('.paper').boundingBox();
    expect(notice!.x).toBeGreaterThanOrEqual(0);
    expect(notice!.x+notice!.width).toBeLessThanOrEqual(width);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
    await page.screenshot({path:testInfo.outputPath(`notice-${width}.png`),fullPage:false});
    await page.getByRole('button',{name:'Back to the board'}).click();
    await expect(page.locator('#notice-upcoming')).toBeFocused();
  });
}

test('all four tab labels and multi-digit counts fit within their paper at 320px',async({page})=>{
  const fixture = [
    ...Array.from({length:30},(_,index)=>({...base,id:`upcoming-${index}`})),
    ...Array.from({length:12},(_,index)=>({...events[3],id:`past-${index}`})),
    ...Array.from({length:12},(_,index)=>({...events[4],id:`confirmation-${index}`})),
    ...Array.from({length:12},(_,index)=>({...events[5],id:`archive-${index}`})),
  ];
  await setup(page,320,fixture);
  await expect(page.getByRole('tab').locator('span')).toHaveText(['30','12','12','12']);
  for(const tab of await page.getByRole('tab').all()) {
    expect(await tab.evaluate(el=>{
      const box=el.getBoundingClientRect();
      const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
      let text: Node | null;
      const rects: DOMRect[]=[];
      while((text=walker.nextNode())) {
        if(!text.textContent?.trim()) continue;
        const range=document.createRange(); range.selectNodeContents(text);
        rects.push(...Array.from(range.getClientRects()));
      }
      return el.scrollWidth<=el.clientWidth+1 && rects.every(rect=>rect.left>=box.left && rect.right<=box.right && rect.top>=box.top && rect.bottom<=box.bottom);
    })).toBeTruthy();
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('navbar search combines with interest, attendance and every section, and empty results clear together', async ({page}) => {
  await setup(page);
  const search = page.getByRole('searchbox',{name:'Search events'});
  const topic = page.getByRole('combobox',{name:'Browse by interest'});
  const attendance = page.getByRole('combobox',{name:'How to attend'});
  await search.fill('Community technology');
  await topic.selectOption('community');
  await attendance.selectOption('in_person');
  await expect(page.locator('.event-card')).toHaveCount(2);
  await expect(page.locator('#tab-upcoming span')).toHaveText('2');
  for(const [section,id] of [['finished','past'],['confirmation','unknown'],['archived','archive']]) {
    await page.locator(`#tab-${section}`).click();
    await expect(page.locator('.notice-select')).toHaveAttribute('id',`notice-${id}`);
    await expect(search).toHaveValue('Community technology');
    await expect(topic).toHaveValue('community');
    await expect(attendance).toHaveValue('in_person');
  }
  await search.fill('no matching event');
  await expect(page.getByRole('heading',{name:'No matches for these filters.'})).toBeVisible();
  await expect(page.locator('.paper')).toHaveCount(0);
  await page.getByRole('button',{name:'Clear filters',exact:true}).first().click();
  for(const control of [search,topic,attendance]) await expect(control).toHaveValue('');
  await expect(page.locator('#tab-archived')).toHaveAttribute('aria-selected','true');
  await expect(page.locator('#notice-archive')).toBeVisible();
  await page.locator('#tab-upcoming').click();
  await expect(page.locator('.event-card')).toHaveCount(3);
});

test('desktop paper scrolls natively without moving the page and reserves its scrollbar space', async ({page}) => {
  await setup(page);
  const paper = page.getByRole('region',{name:'Selected event notice'});
  await expect(paper).toHaveAttribute('tabindex','0');
  await expect(paper).toHaveCSS('overflow-y','auto');
  await expect(paper).toHaveCSS('scrollbar-gutter','stable');
  expect(await paper.evaluate(el=>el.scrollHeight>el.clientHeight)).toBeTruthy();
  await expect(paper).toHaveAttribute('data-scrolling','false');
  const dimensions = () => paper.evaluate(el=>({width:el.clientWidth,titleWidth:document.getElementById('paper-title')!.getBoundingClientRect().width,pageY:scrollY}));
  const before = await dimensions();
  const appearance = () => paper.evaluate(el=>({standard:getComputedStyle(el).scrollbarColor,thumb:getComputedStyle(el,'::-webkit-scrollbar-thumb').backgroundColor}));
  const idleAppearance = await appearance();
  const box = await paper.boundingBox();
  await page.mouse.move(box!.x+box!.width/2,box!.y+100);
  await expect(paper).toHaveAttribute('data-scrolling','true');
  expect(await appearance()).not.toEqual(idleAppearance);
  expect(await dimensions()).toEqual(before);
  await page.mouse.wheel(0,280);
  await expect.poll(()=>paper.evaluate(el=>el.scrollTop)).toBeGreaterThan(0);
  expect(await page.evaluate(()=>window.scrollY)).toBe(before.pageY);
  expect(await dimensions()).toEqual(before);
  await expect(paper).toHaveAttribute('data-scrolling','false',{timeout:2500});
  expect(await appearance()).toEqual(idleAppearance);
  expect(await dimensions()).toEqual(before);
  // The native scroll event also reveals the thumb, including assistive scrolling.
  await paper.evaluate(el=>{el.scrollTop+=50;});
  await expect(paper).toHaveAttribute('data-scrolling','true');
  await expect(paper).toHaveAttribute('data-scrolling','false',{timeout:2500});
  await paper.focus();
  const previousTop = await paper.evaluate(el=>el.scrollTop);
  await page.keyboard.press('ArrowDown');
  await expect(paper).toBeFocused();
  await expect(paper).toHaveAttribute('data-scrolling','true');
  await expect(paper).toHaveCSS('outline-style','solid');
  expect(await paper.evaluate(el=>parseFloat(getComputedStyle(el).outlineWidth))).toBeGreaterThanOrEqual(2);
  await expect.poll(()=>paper.evaluate(el=>el.scrollTop)).toBeGreaterThan(previousTop);
  expect(await page.evaluate(()=>window.scrollY)).toBe(before.pageY);
  await expect(paper).toHaveAttribute('data-scrolling','false',{timeout:2500});
});

test('forced colors keeps a native visible scrollbar and keyboard focus through idle', async ({page}) => {
  await page.emulateMedia({forcedColors:'active',reducedMotion:'reduce'});
  await setup(page);
  const paper = page.getByRole('region',{name:'Selected event notice'});
  await expect(paper).toHaveCSS('scrollbar-gutter','stable');
  await expect(paper).toHaveCSS('scrollbar-color','auto');
  const thumbColor = await paper.evaluate(el=>getComputedStyle(el,'::-webkit-scrollbar-thumb').backgroundColor);
  expect(thumbColor).not.toBe('rgba(0, 0, 0, 0)');
  await paper.focus();
  await page.keyboard.press('ArrowDown');
  await expect(paper).toBeFocused();
  await expect(paper).toHaveCSS('outline-style','solid');
  await expect.poll(()=>paper.evaluate(el=>el.scrollTop)).toBeGreaterThan(0);
  await expect(paper).toHaveAttribute('data-scrolling','false',{timeout:2500});
  await expect(paper).toHaveCSS('scrollbar-color','auto');
  expect(await paper.evaluate(el=>getComputedStyle(el,'::-webkit-scrollbar-thumb').backgroundColor)).toBe(thumbColor);
  await expect(page.locator('.notice-lead .event-date')).toHaveCSS('animation-name','none');
});

test.describe('touch scrollbar interaction',()=>{
  test.use({hasTouch:true});
  test('touching the desktop notice reveals its scrollbar then settles at idle',async({page})=>{
    await setup(page);
    const paper=page.getByRole('region',{name:'Selected event notice'});
    await expect(paper).toHaveAttribute('data-scrolling','false');
    await paper.tap({position:{x:100,y:150}});
    await expect(paper).toHaveAttribute('data-scrolling','true');
    await expect(paper).toHaveAttribute('data-scrolling','false',{timeout:2500});
  });
});

test('decorative notes reveal after scrolling and never enter keyboard or pointer interaction',async({page})=>{
  await setup(page);
  const doodles=page.locator('.board-doodles');
  await expect(doodles).not.toBeVisible();
  await page.locator('.paper-scroll').evaluate(el=>{el.scrollTop=100;});
  await expect(doodles).toBeVisible();
  await expect(doodles).toHaveAttribute('aria-hidden','true');
  await expect(doodles).toHaveCSS('pointer-events','none');
  await expect(doodles.locator('button,a,input,select,[tabindex]')).toHaveCount(0);
  const board=await page.locator('.board-split').boundingBox();
  const notes=await doodles.boundingBox();
  expect(notes!.y).toBeGreaterThanOrEqual(board!.y+board!.height);
});
