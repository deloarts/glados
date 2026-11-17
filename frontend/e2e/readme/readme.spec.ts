/**
 * Captures the README pictures from the mocked API in ./handlers: the
 * dashboard in both themes and the frames of a short walkthrough. It is not a
 * test and is run on demand through `npm run readme:media`, which hands the
 * frames to ./assemble.py to build the files in docs/assets.
 *
 * A headless browser draws no mouse pointer, so the walkthrough injects one
 * and moves it together with the real mouse, which keeps hover states and
 * tooltips in the picture.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { expect, test, type Locator, type Page } from '@playwright/test'

import { NOW } from '../visual/fixtures'
import { mockApi, type MockedApi } from '../visual/mockApi'
import { readmeHandlers } from './handlers'

const OUT = process.env.README_OUT ?? 'test-results/readme'

// The real clock keeps running from the fixed day, so chart animations play
// instead of freezing on their first frame.
test.beforeEach(async ({ page }) => {
  await page.clock.setSystemTime(new Date(NOW))
})

async function settle(page: Page, api: MockedApi): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
  // Long enough for the dashboard's chart and rings to finish animating.
  await page.waitForTimeout(3000)
  expect(api.unmatched(), 'requests without a fixture').toEqual([])
}

for (const dark of [false, true]) {
  test(`dashboard, ${dark ? 'dark' : 'light'}`, async ({ page }) => {
    const api = await mockApi(page, readmeHandlers(dark))
    await page.goto('/dashboard')
    await expect(page.getByText('Pieces scrapped')).toBeVisible()
    await settle(page, api)
    mkdirSync(OUT, { recursive: true })
    await page.screenshot({ path: join(OUT, `dashboard-${dark ? 'dark' : 'light'}.png`) })
  })
}

const CURSOR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="28" viewBox="0 0 22 28">
  <path d="M2 2 L2 22 L7.5 17 L11 25.5 L14.5 24 L11 15.5 L18.5 15.5 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/>
</svg>`

/** Writes numbered frames and a manifest of how long each one shows. */
class Recorder {
  private readonly frames: { file: string; ms: number }[] = []
  private x = 720
  private y = 450

  constructor(private readonly page: Page, private readonly dir: string) {
    mkdirSync(dir, { recursive: true })
  }

  async installCursor(): Promise<void> {
    await this.page.evaluate(
      ([svg, x, y]) => {
        const cursor = document.createElement('div')
        cursor.id = 'readme-cursor'
        cursor.innerHTML = `<span class="ring"></span>${svg}`
        const style = document.createElement('style')
        style.textContent = `
          #readme-cursor { position: fixed; left: 0; top: 0; z-index: 2147483647; pointer-events: none; }
          #readme-cursor svg { position: absolute; left: -2px; top: -2px; filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.35)); }
          #readme-cursor .ring { position: absolute; left: -14px; top: -14px; width: 28px; height: 28px; border-radius: 50%;
            background: rgb(37 99 235 / 0.35); transform: scale(0); }
          #readme-cursor.down .ring { transform: scale(1); }`
        document.head.append(style)
        document.body.append(cursor)
        cursor.style.transform = `translate(${x}px, ${y}px)`
      },
      [CURSOR_SVG, this.x, this.y] as const,
    )
  }

  async frame(ms: number): Promise<void> {
    const file = `${String(this.frames.length).padStart(4, '0')}.png`
    await this.page.screenshot({ path: join(this.dir, file) })
    this.frames.push({ file, ms })
  }

  private async place(x: number, y: number): Promise<void> {
    this.x = x
    this.y = y
    await this.page.mouse.move(x, y)
    await this.page.evaluate(
      ([px, py]) => {
        document.getElementById('readme-cursor')!.style.transform = `translate(${px}px, ${py}px)`
      },
      [x, y] as const,
    )
  }

  /** Glides the pointer to the middle of `target` in eased steps. */
  async moveTo(target: Locator, steps = 14): Promise<void> {
    const box = (await target.boundingBox())!
    const [fromX, fromY] = [this.x, this.y]
    const [toX, toY] = [box.x + box.width / 2, box.y + box.height / 2]
    for (let step = 1; step <= steps; step++) {
      const t = step / steps
      const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
      await this.place(fromX + (toX - fromX) * eased, fromY + (toY - fromY) * eased)
      await this.frame(40)
    }
  }

  async click(target: Locator): Promise<void> {
    await this.moveTo(target)
    await this.frame(250)
    await this.page.evaluate(() => document.getElementById('readme-cursor')!.classList.add('down'))
    await this.frame(140)
    await this.page.mouse.down()
    await this.page.mouse.up()
    await this.page.evaluate(() => document.getElementById('readme-cursor')!.classList.remove('down'))
  }

  save(): void {
    writeFileSync(join(this.dir, 'manifest.json'), JSON.stringify(this.frames, null, 2))
  }
}

test('walkthrough', async ({ page }) => {
  test.setTimeout(180_000)
  const api = await mockApi(page, readmeHandlers(false))
  const rec = new Recorder(page, join(OUT, 'walkthrough'))

  await page.goto('/dashboard')
  await expect(page.getByText('Pieces scrapped')).toBeVisible()
  await settle(page, api)
  await rec.installCursor()
  await rec.frame(2600)

  await rec.click(page.getByRole('link', { name: 'Catalogue', exact: true }).first())
  await expect(page.getByText('Linear guide rail 20 mm')).toBeVisible()
  await page.waitForTimeout(500)
  await rec.frame(2200)

  await rec.click(page.getByRole('link', { name: 'Production', exact: true }).first())
  await expect(page.getByText('L26-0412').first()).toBeVisible()
  await page.waitForTimeout(500)
  await rec.frame(2600)

  await rec.click(page.getByRole('tab', { name: 'Planning' }))
  await expect(page.getByText('MILL-01 (Milling)').first()).toBeVisible()
  await page.waitForTimeout(500)
  await rec.frame(2600)

  await rec.click(page.getByRole('tab', { name: 'Capacity' }))
  await expect(page.getByText('MILL-02').first()).toBeVisible()
  await page.waitForTimeout(500)
  await rec.frame(2600)

  expect(api.unmatched(), 'requests without a fixture').toEqual([])
  rec.save()
})
