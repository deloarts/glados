<script setup lang="ts">
/**
 * Text with the standard's symbols set as subscripts: "D_DT" renders as D
 * with a subscript DT, "H_{D,min}" with the subscript "D,min". Used for
 * symbols, formulas and the messages that name them.
 */
import { computed } from 'vue'

import { splitSubscripts } from '../utils/safetyDistance/format'

const props = defineProps<{ text: string }>()

const parts = computed(() => splitSubscripts(props.text))
</script>

<template>
  <span class="sd-text"><template v-for="(part, index) in parts" :key="index"><sub v-if="part.sub">{{ part.text }}</sub><template v-else>{{ part.text }}</template></template></span>
</template>

<style scoped lang="scss">
.sd-text sub {
  font-size: 0.75em;
  line-height: 0;
}
</style>
