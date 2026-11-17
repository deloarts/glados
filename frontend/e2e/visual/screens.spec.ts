/**
 * Screenshots of the screens that carry the Glados look: the login page, the
 * app shell with a catalogue table in both themes, and a form dialog. Each
 * test fails if the screen asked the API for anything the fixtures do not
 * answer, so a new request shows up as a clear failure, not as a toast in the
 * picture.
 */
import { expect, test, type Page } from '@playwright/test'

import { NOW, articleGroups, baseHandlers, madeItems, page as pageOf, user } from './fixtures'
import { mockApi, type MockHandler, type MockedApi } from './mockApi'

const catalogueHandlers: MockHandler[] = [
  { path: '/web/made-items/', body: pageOf(madeItems) },
  { path: '/web/article-groups/', body: pageOf(articleGroups) },
  { path: '/web/pdm/preview', body: { enabled: false, kind: 'made', newer: [], unlinked: [] } },
  { path: '/web/made-items-pictures/', body: [] },
  // The app asks without the trailing slash and follows the redirect.
  { path: /^\/web\/made-items-files\/?$/, body: [] },
  // Pickers in the create dialog: empty lists are enough for the empty form.
  { path: /^\/web\/(customers|source-items|fabrication-methods|inspection-methods)\/?$/, body: pageOf([]) },
]

// Dates on screen, such as a format example or a relative time, follow the
// fixtures rather than the day the test runs.
test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date(NOW))
})

async function settle(page: Page, api: MockedApi): Promise<void> {
  // Web fonts and lazily loaded icons must be in before the picture is taken.
  await page.evaluate(() => document.fonts.ready)
  expect(api.unmatched(), 'requests without a fixture').toEqual([])
}

test('login page', async ({ page }) => {
  const api = await mockApi(page, baseHandlers(null))
  await page.goto('/login')
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
  await settle(page, api)
  await expect(page).toHaveScreenshot('login.png')
})

for (const dark of [false, true]) {
  test(`made items catalogue, ${dark ? 'dark' : 'light'}`, async ({ page }) => {
    const api = await mockApi(page, [...baseHandlers(user({ theme_dark_mode: dark })), ...catalogueHandlers])
    await page.goto('/catalogue/made-items')
    await expect(page.getByText('Gearbox housing')).toBeVisible()
    await settle(page, api)
    await expect(page).toHaveScreenshot(`catalogue-made-items-${dark ? 'dark' : 'light'}.png`)
  })
}

test('made item create dialog', async ({ page }) => {
  const api = await mockApi(page, [...baseHandlers(user()), ...catalogueHandlers])
  await page.goto('/catalogue/made-items')
  await expect(page.getByText('Gearbox housing')).toBeVisible()
  await page.getByRole('button', { name: 'New', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await settle(page, api)
  await expect(dialog).toHaveScreenshot('made-item-create-dialog.png')
})

test('account page', async ({ page }) => {
  const api = await mockApi(page, baseHandlers(user()))
  await page.goto('/account')
  // The form's labels are not tied to their inputs, so the field is found by
  // its value rather than its label.
  await expect
    .poll(() => page.locator('input').evaluateAll((inputs) => inputs.some((input) => (input as HTMLInputElement).value === 'Avery Example')))
    .toBe(true)
  await settle(page, api)
  await expect(page).toHaveScreenshot('account.png')
})
