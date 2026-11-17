<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import CakeEasterEgg from './CakeEasterEgg.vue'
import { APERTURE_FOOTER, useEasterEggs } from '@/core/composables/useEasterEggs'
import { useConnectionStore } from '@/core/stores/connectionStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { useLiveStore } from '@/core/realtime/liveStore'
import { safeHref } from '@/shared/utils/isSafeHttpUrl'

const { t } = useI18n()
const publicBrandingStore = usePublicBrandingStore()
const connectionStore = useConnectionStore()
const liveStore = useLiveStore()
const { apertureMode } = useEasterEggs()

const footerText = computed(() =>
  apertureMode.value ? APERTURE_FOOTER : publicBrandingStore.footerText,
)

// Hidden in aperture mode: that easter egg replaces the footer wholesale, and
// a real company name sitting next to it would break the joke.
const companyName = computed(() => (apertureMode.value ? null : publicBrandingStore.companyName))

// Same rule as the company name: a customer's imprint next to the Aperture
// footer would break the joke.
const footerLinks = computed(() => (apertureMode.value ? [] : publicBrandingStore.footerLinks))

// mailto: hands off to the mail client; a blank tab for it would just be an
// empty window left behind.
function linkTarget(href: string) {
  return href.startsWith('mailto:') ? undefined : '_blank'
}

// These come from admin-configured branding fields, not from anything the
// current user typed, so a stale or tampered value could in theory still
// hold something other than an absolute http(s) URL or a mailto: link. An
// unsafe link is skipped entirely rather than rendered as dead or unsafe
// markup.
function footerLinkHref(href: string): string | undefined {
  return safeHref(href, { allowMailto: true })
}

// Unsafe links are dropped rather than rendered without an href, since there
// is no useful fallback text for a bare link label like "Support".
const safeFooterLinks = computed(() =>
  footerLinks.value.flatMap((link) => {
    const href = footerLinkHref(link.href)
    return href ? [{ key: link.key, href }] : []
  }),
)

const liveIcon = computed(() =>
  liveStore.status === 'open' ? 'mdi-broadcast' : 'mdi-broadcast-off',
)
const liveTooltip = computed(() => t(`common.live.${liveStore.status}`))
</script>

<template>
  <div class="footer" :class="{ 'is-offline': connectionStore.isOffline }">
    <span v-if="companyName || safeFooterLinks.length" class="footer-left">
      <span v-if="companyName" class="company-name">{{ companyName }}</span>
      <nav
        v-if="safeFooterLinks.length"
        class="footer-links"
        :aria-label="t('main.footer.linksLabel')"
      >
        <a
          v-for="link in safeFooterLinks"
          :key="link.key"
          :href="link.href"
          :target="linkTarget(link.href)"
          rel="noopener noreferrer"
          class="footer-link"
          >{{ t(`main.footer.${link.key}`) }}</a
        >
      </nav>
    </span>

    <!-- Takes over the footer's centre rather than opening a dialog: the bar
         is already on screen at all times, so this is unmissable without
         blocking the page behind it. Losing the connection does not make
         what is already rendered unusable, and it clears itself the moment
         anything reaches the server again. -->
    <span v-if="connectionStore.isOffline" class="offline-status" role="alert">
      <i class="mdi mdi-lan-disconnect" aria-hidden="true" />
      <span>{{ t('common.connection.offline') }}</span>
      <button
        type="button"
        class="offline-retry"
        :disabled="connectionStore.isProbing"
        @click="connectionStore.retryNow()"
      >
        {{
          connectionStore.isProbing ? t('common.connection.retrying') : t('common.connection.retry')
        }}
      </button>
    </span>
    <span v-else>{{ footerText }}</span>

    <i
      class="mdi live-status-icon"
      :class="[liveIcon, { 'is-open': liveStore.status === 'open' }]"
      aria-hidden="true"
      v-tooltip.top="liveTooltip"
    />
    <CakeEasterEgg />
  </div>
</template>

<style scoped lang="scss">
.footer {
  display: flex;
  user-select: none;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 100%;
  height: var(--footer-height);
  background: var(--p-primary-500);
  color: var(--on-accent);
  font-size: var(--font-size-sm);
  cursor: default;
  transition: background-color 0.2s ease;

  &.is-offline {
    background: var(--p-red-600);
  }
}

.offline-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;

  > span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

/* A bare button, not a OpenVue one: the footer is 1.5rem tall and any real
   button component overflows it. */
.offline-retry {
  flex: none;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-decoration: underline;
  cursor: pointer;

  &:disabled {
    text-decoration: none;
    opacity: 0.7;
    cursor: default;
  }
}

/* Absolutely positioned, like the live icon on the right, so the footer text
   stays centred on the viewport rather than being pushed off-centre by
   whatever length the company name and link row happen to be. */
.footer-left {
  position: absolute;
  top: 50%;
  left: 0.75rem;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  max-width: 45%;
  min-width: 0;
  opacity: 0.85;
}

/* The name is the part that gives way: the links are short fixed words and
   stay readable, a long legal name just gets its ellipsis. */
.company-name {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.footer-links {
  flex: none;
  white-space: nowrap;
}

.footer-link {
  color: inherit;
  text-decoration: none;

  &:hover,
  &:focus-visible {
    text-decoration: underline;
  }

}

/* One divider between every neighbour in the row, the company name included,
   but only *between*: with no company name the row must not open on a bare
   bar, and the links themselves are never empty, so no trailing one either. */
.footer-link + .footer-link::before,
.company-name + .footer-links > .footer-link:first-child::before {
  content: '|';
  margin: 0 var(--space-2);
  opacity: 0.6;
}

.live-status-icon {
  position: absolute;
  top: 50%;
  right: 0.75rem;
  transform: translateY(-50%);
  font-size: var(--font-size-md);
  padding-top: var(--space-2);
  opacity: 0.55;
  cursor: default;

  &.is-open {
    opacity: 1;
  }
}
</style>
