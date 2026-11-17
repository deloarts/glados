<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type {
  MachineBoardMachine,
  MachineBoardPool,
  WidgetConfigOf,
  WidgetDataOf,
} from '../../types/infoscreenFeed'
import OrderCardText from './OrderCardText.vue'
import RowThumbnail from './RowThumbnail.vue'
import WidgetFrame from './WidgetFrame.vue'

// One tile per machine: its state, what runs on it now and what comes next.
// Below the tiles, one row per pool with orders that wait for a machine;
// a pool with nothing waiting shows no row. Every order shows its lot
// number, part number and article name beside its picture and no times.
const props = defineProps<{
  config: WidgetConfigOf<'machine_board'>
  data: WidgetDataOf<'machine_board'>
}>()

const { t } = useI18n()

const waitingPools = computed<MachineBoardPool[]>(() =>
  (props.data.pools ?? []).filter((pool) => pool.waiting_total > 0),
)

function hiddenCount(pool: MachineBoardPool): number {
  return Math.max(0, pool.waiting_total - pool.waiting.length)
}

function stateLabel(machine: MachineBoardMachine): string {
  return t(`infoscreenRuntime.widgets.machineBoard.states.${machine.state}`)
}
</script>

<template>
  <WidgetFrame :title="config.title || t('infoscreenRuntime.widgets.machineBoard.title')">
    <div v-if="data.machines.length > 0 || waitingPools.length > 0" class="machine-board">
      <div v-if="data.machines.length > 0" class="machine-board-tiles">
        <section
          v-for="machine in data.machines"
          :key="machine.machine_id"
          class="machine-tile"
          :class="`machine-tile--${machine.state}`"
          data-testid="machine-tile"
        >
          <header class="machine-tile-header">
            <h3 class="machine-tile-name">{{ machine.machine_name }}</h3>
            <span class="machine-tile-state">{{ stateLabel(machine) }}</span>
          </header>
          <p v-if="machine.state === 'down' && machine.downtime_reason" class="machine-tile-reason">
            {{ machine.downtime_reason }}
          </p>
          <div v-if="machine.current" class="machine-tile-current" data-testid="machine-current">
            <span class="machine-tile-label">{{ t('infoscreenRuntime.widgets.machineBoard.now') }}</span>
            <div class="machine-tile-card">
              <RowThumbnail :url="machine.current.thumbnail_url" size="3.4em" />
              <OrderCardText
                :lot-number="machine.current.lot_number"
                :part-number="machine.current.part_number"
                :item-name="machine.current.item_name"
                :fallback="machine.current.production_order_id"
                size="large"
              />
            </div>
          </div>
          <p v-else class="machine-tile-idle">
            {{ t('infoscreenRuntime.widgets.machineBoard.nothingPlanned') }}
          </p>
          <div v-if="machine.next.length > 0" class="machine-tile-next">
            <span class="machine-tile-label">{{ t('infoscreenRuntime.widgets.machineBoard.next') }}</span>
            <ul class="machine-tile-next-list">
              <li
                v-for="card in machine.next"
                :key="card.production_order_id"
                data-testid="machine-next"
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
          </div>
        </section>
      </div>
      <section
        v-for="pool in waitingPools"
        :key="pool.pool_id"
        class="machine-pool"
        data-testid="machine-pool"
      >
        <span class="machine-pool-label">
          {{ t('infoscreenRuntime.widgets.machineBoard.waitingInPool', { name: pool.pool_name }) }}
          · {{ pool.waiting_total }}
        </span>
        <ul class="machine-pool-cards">
          <li
            v-for="card in pool.waiting"
            :key="card.production_order_id"
            class="machine-pool-card"
            data-testid="machine-pool-card"
          >
            <RowThumbnail :url="card.thumbnail_url" size="2.4em" />
            <OrderCardText
              :lot-number="card.lot_number"
              :part-number="card.part_number"
              :item-name="card.item_name"
              :fallback="card.production_order_id"
            />
          </li>
          <li v-if="hiddenCount(pool) > 0" class="machine-pool-more" data-testid="machine-pool-more">
            {{ t('infoscreenRuntime.widgets.machineBoard.more', { n: hiddenCount(pool) }) }}
          </li>
        </ul>
      </section>
    </div>
    <p v-else class="widget-empty">{{ t('infoscreenRuntime.widgets.machineBoard.empty') }}</p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.machine-board {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}

.machine-board-tiles {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 14em), 1fr));
  grid-auto-rows: minmax(0, 1fr);
  gap: 0.5em;
}

.machine-pool {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.25em;
  min-width: 0;
  padding: 0.4em 0.7em;
  border: 1px dashed var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
}

.machine-pool-label {
  font-size: 0.85em;
  font-weight: 700;
  color: var(--p-text-muted-color);
}

// The waiting orders run left to right and clip at the edge rather than
// wrapping into a second line.
.machine-pool-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: 1em;
  min-width: 0;
  overflow: hidden;
}

.machine-pool-card {
  flex: 0 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 0.4em;
}

.machine-pool-more {
  flex: 0 0 auto;
  align-self: center;
  font-weight: 700;
  color: var(--p-text-muted-color);
}

.machine-tile {
  --machine-accent: var(--p-text-muted-color);
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 0.3em;
  padding: 0.5em 0.7em;
  border: 1px solid var(--p-content-border-color);
  border-top: 0.3em solid var(--machine-accent);
  border-radius: var(--p-border-radius-sm);
}

.machine-tile--running {
  --machine-accent: var(--p-green-500);
}

.machine-tile--down {
  --machine-accent: var(--p-red-500);
}

.machine-tile--closed {
  opacity: 0.6;
}

.machine-tile-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5em;
}

.machine-tile-name {
  margin: 0;
  font-size: 1.15em;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.machine-tile-state {
  flex: 0 0 auto;
  font-weight: 700;
  color: var(--machine-accent);
}

.machine-tile-reason {
  margin: 0;
  font-weight: 600;
  color: var(--p-red-500);
}

.machine-tile-current,
.machine-tile-next {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.machine-tile-label {
  font-size: 0.7em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--p-text-muted-color);
}

.machine-tile-idle {
  margin: 0;
  color: var(--p-text-muted-color);
}

.machine-tile-next-list {
  list-style: none;
  margin: 0;
  padding: 0;

  li {
    display: flex;
    align-items: center;
    gap: 0.5em;
    padding: 0.1em 0;
  }
}

.machine-tile-card {
  display: flex;
  align-items: center;
  gap: 0.5em;
  min-width: 0;
}

.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
