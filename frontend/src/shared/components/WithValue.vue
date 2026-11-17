<script setup lang="ts" generic="T">
// Renderless helper that binds one already-computed value to a name for its
// default slot, no wrapping DOM node added. Exists for template spots that
// need to call an expensive or non-idempotent getter (a store lookup keyed
// by a row id, say) exactly once per render instead of once per reference.
// A single-element `v-for` (`v-for="x in [expr]"`) would do the same but
// needs a `vue/valid-v-for` eslint-disable next to it because the rule can't
// verify the array literal is stable, and forces the list keyed by whatever
// the caller invents instead of what it's iterating.
defineProps<{
  value: T
}>()
</script>

<template>
  <slot :value="value" />
</template>
