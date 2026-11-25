import {expect, type Locator, type Page} from '@playwright/test';

const labels: Record<string,string> = {cybersecurity:'Cybersecurity',ai_data:'AI & Data',cloud:'Cloud',devops:'DevOps',software_development:'Software Development',networking_systems:'Networking & Systems',community:'Community',general_it:'General IT',online:'Online',in_person:'In person',hybrid:'Hybrid',unknown:'Format unconfirmed'};
export function filterTrigger(page: Page, group: 'interest' | 'attendance') {
  return page.getByRole('button', {name: group === 'interest' ? /^Browse by interest(?:$|:)/ : /^How to attend(?:$|:)/});
}
export async function chooseFilter(trigger: Locator, value: string) {
  const id = await trigger.getAttribute('aria-controls');
  if (await trigger.getAttribute('aria-expanded') !== 'true') await trigger.click();
  await trigger.page().locator(`#${id}`).getByRole('button', {name: value ? labels[value] : id?.includes('interest') ? 'All interests' : 'All attendance options', exact:true}).click();
  await expect(trigger).toHaveAttribute('aria-expanded','false');
  await expect(trigger).toBeFocused();
}
export async function expectFilter(trigger: Locator, value: string) {
  const interest = (await trigger.getAttribute('aria-controls'))?.includes('interest');
  await expect(trigger).toHaveText(value ? `${interest ? 'Interest' : 'Attend'} · ${labels[value]}` : interest ? 'Browse by interest' : 'How to attend');
}
