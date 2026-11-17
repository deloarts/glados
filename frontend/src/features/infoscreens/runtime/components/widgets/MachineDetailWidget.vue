<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { pdfFitUrl } from '@/core/utils/pdfEmbed'
import { useBlobObjectUrl } from '@/shared/composables/useBlobObjectUrl'

import type { InfoscreenMachineOrder, WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import { formatDay, formatQuantity, joinParts, statusLabel } from '../../utils/infoscreenFormat'
import OrderCardText from './OrderCardText.vue'
import RowThumbnail from './RowThumbnail.vue'
import WidgetFrame from './WidgetFrame.vue'

// Everything about the work on one machine: the order on it now, or the next
// one when the machine is free, with the item's large picture, its lot
// number, part number and article name, the drawing, the raw material and
// the lot, and no times. The orders after it follow as small cards.
const props = defineProps<{
  config: WidgetConfigOf<'machine_detail'>
  data: WidgetDataOf<'machine_detail'>
}>()

const { t, te } = useI18n()

// The backend hands out root-relative paths, prefixed for the dev server as
// the thumbnails are (RowThumbnail).
const API_ROOT = import.meta.env.VITE_API_URL ?? ''

function absolute(url: string | null | undefined): string | null {
  if (!url) return null
  return url.startsWith('/') ? `${API_ROOT}${url}` : url
}

const order = computed<InfoscreenMachineOrder | null>(() => props.data.order ?? null)

// The drawing link is signed, so a plain request loads it. It is embedded
// as an object URL, as the file preview does, so the PDF viewer opens it
// fitted to the slot. A new link (every hour) loads it again.
const drawingSource = computed(() => absolute(order.value?.drawing_url))
const { url: drawingBlobUrl } = useBlobObjectUrl(drawingSource, (src) =>
  fetch(src).then((response) => {
    if (!response.ok) throw new Error(`Drawing answered ${response.status}`)
    return response.blob()
  }),
)
const drawingSrc = computed(() => (drawingBlobUrl.value ? pdfFitUrl(drawingBlobUrl.value) : null))

const title = computed(
  () =>
    props.config.title ||
    props.data.machine_name ||
    t('infoscreenRuntime.widgets.machineDetail.title'),
)

const stateLabel = computed(() =>
  props.data.state ? t(`infoscreenRuntime.widgets.machineBoard.states.${props.data.state}`) : null,
)

type Fact = { key: string; label: string; value: string }

const facts = computed<Fact[]>(() => {
  const current = order.value
  if (!current) return []
  const list: Fact[] = []
  const add = (key: string, value: string | null | undefined) => {
    if (value) list.push({ key, label: t(`infoscreenRuntime.widgets.machineDetail.facts.${key}`), value })
  }
  add('revision', current.revision)
  add('material', current.material)
  add(
    'mass',
    current.mass_grams !== null && current.mass_grams !== undefined
      ? formatQuantity(current.mass_grams / 1000, 'kg')
      : null,
  )
  add('baseSize', current.base_size)
  add(
    'quantity',
    `${formatQuantity(current.quantity_completed)} / ${formatQuantity(current.quantity)}`,
  )
  if (current.step_sequence && current.step_count) {
    add(
      'step',
      t('infoscreenRuntime.widgets.machineDetail.stepOf', {
        n: current.step_sequence,
        total: current.step_count,
      }),
    )
  }
  if (current.lot) {
    add('lotStatus', statusLabel(t, te, current.lot.status, ['production.lots.status']))
    add('lotQuantity', formatQuantity(current.lot.quantity))
    add('project', current.lot.project_number)
    add('customer', current.lot.customer_name)
  }
  return list
})

const rawMaterial = computed(() => {
  const raw = order.value?.raw_material
  if (!raw) return null
  return {
    name: joinParts(raw.part_number, raw.name),
    detail: joinParts(raw.material, raw.dimension),
    status: raw.demand_status
      ? statusLabel(t, te, raw.demand_status, [
          'infoscreenRuntime.widgets.machineDetail.demandStatuses',
        ])
      : null,
    expected: raw.expected_delivery
      ? t('infoscreenRuntime.widgets.machineDetail.expected', {
          date: formatDay(raw.expected_delivery),
        })
      : null,
  }
})
</script>

<template>
  <WidgetFrame :title="title">
    <p v-if="!data.machine_name" class="widget-empty" data-testid="machine-detail-missing">
      {{ t('infoscreenRuntime.widgets.machineDetail.missing') }}
    </p>
    <div
      v-else
      class="machine-detail"
      :class="[`machine-detail--${data.state ?? 'idle'}`, { 'machine-detail--drawing': drawingSrc }]"
    >
      <header class="machine-detail-state">
        <span class="machine-detail-state-label" data-testid="machine-detail-state">
          {{ stateLabel }}
        </span>
        <span v-if="data.state === 'down' && data.downtime_reason" class="machine-detail-reason">
          {{ data.downtime_reason }}
        </span>
      </header>

      <p v-if="!order" class="widget-empty">
        {{ t('infoscreenRuntime.widgets.machineBoard.nothingPlanned') }}
      </p>
      <template v-else>
        <section class="machine-detail-item" data-testid="machine-detail-order">
          <span class="machine-detail-label">
            {{
              order.current
                ? t('infoscreenRuntime.widgets.machineBoard.now')
                : t('infoscreenRuntime.widgets.machineBoard.next')
            }}
          </span>
          <div class="machine-detail-card">
            <RowThumbnail :url="order.picture_url" size="7em" />
            <OrderCardText
              :lot-number="order.lot_number"
              :part-number="order.part_number"
              :item-name="order.item_name"
              :fallback="order.production_order_id"
              size="large"
            />
          </div>
          <dl v-if="facts.length > 0" class="machine-detail-facts">
            <div v-for="fact in facts" :key="fact.key" class="machine-detail-fact">
              <dt>{{ fact.label }}</dt>
              <dd>{{ fact.value }}</dd>
            </div>
          </dl>
          <div v-if="rawMaterial" class="machine-detail-raw" data-testid="machine-detail-raw">
            <span class="machine-detail-label">
              {{ t('infoscreenRuntime.widgets.machineDetail.rawMaterial') }}
            </span>
            <span class="machine-detail-raw-name">{{ rawMaterial.name || rawMaterial.detail }}</span>
            <span v-if="rawMaterial.name && rawMaterial.detail" class="machine-detail-muted">
              {{ rawMaterial.detail }}
            </span>
            <span v-if="rawMaterial.status || rawMaterial.expected" class="machine-detail-muted">
              {{ joinParts(rawMaterial.status, rawMaterial.expected) }}
            </span>
          </div>
        </section>

        <section v-if="drawingSrc" class="machine-detail-drawing">
          <iframe
            :src="drawingSrc"
            class="machine-detail-drawing-frame"
            :title="t('infoscreenRuntime.widgets.machineDetail.drawing')"
            data-testid="machine-detail-drawing"
          />
        </section>
      </template>

      <section v-if="data.next.length > 0" class="machine-detail-next">
        <span class="machine-detail-label">
          {{ t('infoscreenRuntime.widgets.machineBoard.next') }}
        </span>
        <ul class="machine-detail-next-list">
          <li
            v-for="card in data.next"
            :key="card.production_order_id"
            class="machine-detail-next-card"
            data-testid="machine-detail-next"
          >
            <RowThumbnail :url="card.thumbnail_url" size="2.4em" />
            <OrderCardText
              :lot-number="card.lot_number"
              :part-number="card.part_number"
              :item-name="card.item_name"
              :fallback="card.production_order_id"
            />
          </li>
        </ul>
      </section>
    </div>
  </WidgetFrame>
</template>

<style scoped lang="scss">
// Without a drawing the item fills the slot; with one, the drawing takes
// the larger right part, since it is what the operator reads from afar.
.machine-detail {
  --machine-accent: var(--p-text-muted-color);
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr) auto;
  grid-template-areas:
    'state'
    'item'
    'next';
  gap: 0.5em;
}

.machine-detail--drawing {
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  grid-template-areas:
    'state state'
    'item drawing'
    'next next';
}

.machine-detail--running {
  --machine-accent: var(--p-green-500);
}

.machine-detail--down {
  --machine-accent: var(--p-red-500);
}

.machine-detail-state {
  grid-area: state;
  display: flex;
  align-items: baseline;
  gap: 0.6em;
  padding-bottom: 0.2em;
  border-bottom: 0.25em solid var(--machine-accent);
}

.machine-detail-state-label {
  font-weight: 700;
  color: var(--machine-accent);
}

.machine-detail-reason {
  font-weight: 600;
  color: var(--p-red-500);
}

.machine-detail-item {
  grid-area: item;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}

.machine-detail-card {
  display: flex;
  align-items: center;
  gap: 0.8em;
  min-width: 0;
  font-size: 1.15em;
}

.machine-detail-label {
  font-size: 0.7em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--p-text-muted-color);
}

.machine-detail-facts {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(8em, 1fr));
  gap: 0.3em 0.8em;
}

.machine-detail-fact {
  min-width: 0;

  dt {
    font-size: 0.7em;
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-variant-numeric: tabular-nums;
  }
}

.machine-detail-raw {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 0.3em 0.6em;
  border-left: 0.2em solid var(--p-content-border-color);
}

.machine-detail-raw-name {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.machine-detail-muted {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
}

.machine-detail-drawing {
  grid-area: drawing;
  min-height: 0;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  overflow: hidden;
}

.machine-detail-drawing-frame {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
}

.machine-detail-next {
  grid-area: next;
  display: flex;
  flex-direction: column;
  gap: 0.2em;
  min-width: 0;
}

// The next orders run left to right and clip at the edge.
.machine-detail-next-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: 1em;
  min-width: 0;
  overflow: hidden;
}

.machine-detail-next-card {
  flex: 0 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.4em;
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
