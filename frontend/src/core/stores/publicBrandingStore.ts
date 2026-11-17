import axios from 'axios'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { i18n } from '@/core/i18n'
import type { Schemas } from '@/core/api/generated'
import { useCurrentUserStore } from './currentUserStore'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''

/**
 * What the pre-auth screens need from the host: branding, the footer's
 * company and "Contact & Legal" links from the general settings, the
 * tenant-wide default language (the login screen has no user to read it
 * from), the maintenance banner and the address QR codes on PDF reports
 * point to. Read from the public surface, outside the web API client.
 * domain and has_company_logo stay optional, since the store reads a
 * missing one as absent.
 */
type PublicBranding = Omit<Schemas['PublicBrandingResponse'], 'domain' | 'has_company_logo'> &
  Partial<Pick<Schemas['PublicBrandingResponse'], 'domain' | 'has_company_logo'>>

export type FooterLinkKey = 'contact' | 'support' | 'imprint' | 'privacy'

export interface FooterLink {
  key: FooterLinkKey
  href: string
}

function trimmed(value: string | null | undefined): string | null {
  return value?.trim() || null
}

export const usePublicBrandingStore = defineStore('publicBranding', () => {
  const branding = ref<PublicBranding | null>(null)

  const appName = computed(() => branding.value?.app_name ?? 'Glados')
  // Null rather than '' when unset (or whitespace-only via the API), so the
  // header can drop the whole tagline row instead of rendering an empty one.
  const appDescription = computed(() => branding.value?.app_description?.trim() || null)
  // Null when unset, so the footer can leave its left slot empty rather than
  // falling back to the app name and repeating what is already centred.
  const companyName = computed(() => branding.value?.company_name ?? null)
  const footerText = computed(
    () => branding.value?.footer_text ?? branding.value?.app_name ?? 'Glados',
  )
  // Only the configured ones, in the footer's fixed display order. The
  // contact email becomes a mailto: link so the footer can treat all four
  // uniformly as anchors; labels are the footer's business (i18n).
  const footerLinks = computed<FooterLink[]>(() => {
    const b = branding.value
    if (!b) return []
    const email = trimmed(b.contact_email)
    const candidates: Array<[FooterLinkKey, string | null]> = [
      ['contact', email ? `mailto:${email}` : null],
      ['support', trimmed(b.support_url)],
      ['imprint', trimmed(b.imprint_url)],
      ['privacy', trimmed(b.privacy_url)],
    ]
    return candidates.flatMap(([key, href]) => (href ? [{ key, href }] : []))
  })
  const logoUrl = computed(() =>
    branding.value?.has_logo ? `${API_ROOT}/api/v1/public/branding/logo` : null,
  )
  const companyLogoUrl = computed(() =>
    branding.value?.has_company_logo ? `${API_ROOT}/api/v1/public/company/logo` : null,
  )
  const faviconUrl = computed(() =>
    branding.value?.has_favicon ? `${API_ROOT}/api/v1/public/branding/favicon` : null,
  )
  // Null until branding has loaded, and reports then link to the address
  // the browser has open.
  const domain = computed(() => trimmed(branding.value?.domain))
  const maintenanceEnabled = computed(() => branding.value?.maintenance_enabled ?? false)
  const maintenanceMessage = computed(() => branding.value?.maintenance_message ?? null)

  async function fetch() {
    try {
      const response = await axios.get<PublicBranding>(`${API_ROOT}/api/v1/public/branding`)
      branding.value = response.data
      // Race guard against currentUserStore.refresh(), which sets the
      // signed-in user's own language once /users/me answers: whichever of
      // the two lands second must not clobber a real user's choice, so this
      // only ever writes the locale while nobody is signed in. Both
      // orderings are then safe: if refresh() already landed, `user` is set
      // and this is a no-op; if this lands first, refresh() still
      // unconditionally overwrites the locale with the signed-in user's own
      // preference when it completes.
      if (!useCurrentUserStore().user) {
        i18n.global.locale.value = response.data.default_language
      }
      applyToDocument()
    } catch {
      // Non-fatal, default branding stays in place
    }
  }

  function applyToDocument() {
    if (!branding.value) return

    document.title = branding.value.app_name

    if (branding.value.has_favicon) {
      let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
      if (!link) {
        link = document.createElement('link')
        link.rel = 'icon'
        document.head.appendChild(link)
      }
      link.href = `${API_ROOT}/api/v1/public/branding/favicon?t=${Date.now()}`
    }
  }

  return {
    branding,
    appName,
    appDescription,
    companyName,
    footerText,
    footerLinks,
    logoUrl,
    companyLogoUrl,
    domain,
    faviconUrl,
    maintenanceEnabled,
    maintenanceMessage,
    fetch,
  }
})
