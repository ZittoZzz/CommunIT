import {test, expect, type Page} from '@playwright/test';
import {chooseFilter, expectFilter, filterTrigger} from './filter-helpers';

const base = {organizer:'Community builders',region:'NCR',status:'scheduled',section:'upcoming',start:{value:'2035-12-01',precision:'date'},end:null,deadline:null,registration_status:'open',notices:[],announcements:[]};
const events = [
  {...base,id:'software',name:'Software workshop',topics:['software_development'],format:'in_person'},
  {...base,id:'cloud',name:'Cloud stream',topics:['cloud'],format:'online'},
  {...base,id:'unknown',name:'Unconfirmed format meetup',topics:['community'],format:'unknown'},
];
async function setup(page: Page, width: number) {
  await page.setViewportSize({width,height:800});
  await page.route('**/api/events',route=>route.fulfill({json:{events,generated_at:'2035-11-01T00:00:00Z'}}));
  await page.goto('/');await expect(page.locator('.event-card')).toHaveCount(3);
  await page.locator('.event-card').first().screenshot(); // Wait for the existing list entrance animation.
}

for(const width of [1366,360])test(`paper panels overlay the board, combine and reset independently at ${width}px`,async({page},info)=>{
  await setup(page,width);
  const interest=filterTrigger(page,'interest'),attend=filterTrigger(page,'attendance');
  const geometry=()=>page.locator('.tabs, .event-card').evaluateAll(elements=>elements.map(el=>({y:el.getBoundingClientRect().y,height:el.getBoundingClientRect().height})));
  const before=await geometry();await interest.click();
  const panel=page.getByRole('group',{name:'Browse by interest',exact:true});
  await expect(interest).toHaveAttribute('aria-expanded','true');
  await expect(panel.getByRole('button').first()).toHaveAccessibleName('All interests');
  await expect(panel.getByRole('button',{pressed:true})).toHaveCount(1);
  await expect(panel.getByRole('button',{name:'All interests',exact:true})).toBeFocused();
  await expect(panel).toHaveCSS('animation-duration','0.15s');
  await panel.screenshot({path:info.outputPath(`interest-${width}.png`)});
  expect(await geometry()).toEqual(before);
  const panelBox=(await panel.boundingBox())!,barBox=(await page.locator('.filters').boundingBox())!;
  expect(panelBox.y).toBeGreaterThanOrEqual(barBox.y+barBox.height);
  if(width<=760)expect(panelBox.width).toBe(barBox.width);
  for(const chip of await panel.getByRole('button').all()) {
    const box=(await chip.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(panelBox.x);expect(box.x+box.width).toBeLessThanOrEqual(panelBox.x+panelBox.width);
    expect(await chip.evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));})).toBeTruthy();
  }
  // Switch directly while the first panel is open.
  await attend.click();await expect(panel).toHaveCount(0);
  const attendance=page.getByRole('group',{name:'How to attend',exact:true});
  await expect(attendance.getByRole('button').first()).toHaveAccessibleName('All attendance options');
  await expect(attendance.getByRole('button',{name:'Format unconfirmed',exact:true})).toBeVisible();
  await chooseFilter(attend,'online');await chooseFilter(interest,'software_development');
  await expectFilter(interest,'software_development');await expectFilter(attend,'online');
  await expect(interest).toHaveAccessibleName('Browse by interest: Interest · Software Development');
  await expect(page.getByRole('heading',{name:'No matches for these filters.'})).toBeVisible();
  await expect(page.locator('.event-day-group')).toHaveCount(0);
  await chooseFilter(interest,'');await expectFilter(attend,'online');await expect(page.locator('.event-card h3')).toHaveText(['Cloud stream']);
  await chooseFilter(interest,'cloud');await chooseFilter(attend,'');await expectFilter(interest,'cloud');
  await expect(page.locator('.event-card h3')).toHaveText(['Cloud stream']);
  await interest.click();await expect(panel.getByRole('button',{name:'Cloud',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(panel.getByRole('button',{pressed:true})).toHaveCount(1);
  await expect(panel.getByRole('button',{name:'Cloud',exact:true})).toContainText('✓');
  await page.keyboard.press('Escape');await expect(interest).toBeFocused();await expectFilter(interest,'cloud');
  await page.getByRole('button',{name:'Clear filters',exact:true}).first().click();
  await expect(page.locator('.event-card')).toHaveCount(3);await expectFilter(interest,'');await expectFilter(attend,'');
  await page.getByRole('searchbox').fill('Software');await chooseFilter(interest,'software_development');
  await page.locator('.notice-select').click();await expect(page.locator('#paper-title')).toHaveText('Software workshop');
  if(width<=760){await page.getByRole('button',{name:'Back to the board'}).click();await expect(page.locator('.notice-select')).toBeFocused();}
  await expect(page.getByRole('searchbox')).toHaveValue('Software');await expectFilter(interest,'software_development');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('keyboard chips, Escape, focus return and outside dismissal preserve filter state',async({page})=>{
  await setup(page,1366);const interest=filterTrigger(page,'interest'),attend=filterTrigger(page,'attendance');
  await interest.focus();await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('button',{name:'All interests',exact:true})).toBeFocused();
  await page.keyboard.press('Shift+Tab');await page.keyboard.press('Shift+Tab');await expect(interest).toBeFocused();
  await page.keyboard.press('ArrowDown');await expect(page.getByRole('button',{name:'All interests',exact:true})).toBeFocused();
  await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowRight');
  const cloud=page.getByRole('button',{name:'Cloud',exact:true});await expect(cloud).toBeFocused();
  expect(await cloud.evaluate(el=>parseFloat(getComputedStyle(el).outlineWidth))).toBeGreaterThanOrEqual(2);
  await page.keyboard.press('Enter');await expect(interest).toBeFocused();await expectFilter(interest,'cloud');
  await page.keyboard.press('Space');await expect(cloud).toBeFocused();
  await page.keyboard.press('End');await expect(page.getByRole('button',{name:'General IT',exact:true})).toBeFocused();
  await page.keyboard.press('Home');await page.keyboard.press('Space');await expectFilter(interest,'');await expect(interest).toBeFocused();
  await attend.click();await page.keyboard.press('Escape');await expect(attend).toBeFocused();await expect(attend).toHaveAttribute('aria-expanded','false');
  await interest.click();await page.getByRole('searchbox').click();await expect(interest).toHaveAttribute('aria-expanded','false');await expect(page.getByRole('searchbox')).toBeFocused();
  await interest.click();await page.keyboard.press('End');await page.keyboard.press('Tab');await expect(interest).toHaveAttribute('aria-expanded','false');
  await chooseFilter(attend,'unknown');await expect(page.locator('.event-card h3')).toHaveText(['Unconfirmed format meetup']);
  await expect(page.locator('.filters [role=status]')).toHaveText('All interests. Attendance: Format unconfirmed.');
});

test('reduced motion keeps panels static and forced colors retains a selected indicator',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce',forcedColors:'active'});await setup(page,360);
  await filterTrigger(page,'interest').click();const panel=page.locator('.filter-panel');
  await expect(panel).toHaveCSS('animation-name','none');
  const all=panel.getByRole('button',{name:'All interests',exact:true});await expect(all).toHaveAttribute('aria-pressed','true');await expect(all).toContainText('✓');await expect(all).toHaveCSS('border-top-width','2px');
});
