import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * The Sequences tab of a product and the product page's controls bar meet
 * here: the bar's buttons count their presses, the tab opens the matching
 * dialog on each change.
 */
export const useSequencesViewStore = defineStore('sequencesView', () => {
  const createRequests = ref(0)
  const variantsRequests = ref(0)

  function requestCreate(): void {
    createRequests.value++
  }

  function requestVariants(): void {
    variantsRequests.value++
  }

  return { createRequests, variantsRequests, requestCreate, requestVariants }
})
