<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import {
  createManualPlcTag,
  setSignalTagName,
  updateManualPlcTag,
} from '../api/plcTagsApi'
import type { PlcTag, ProductDeviceSignalType } from '../types/productDevice'
import { SIGNAL_TYPES } from '../types/productDevice'

/**
 * Edits one PLC tag. A tag built from a device signal only takes a name of
 * its own, stored on the signal, or loses it again so the built name
 * applies. A manual tag, or a new one (no `tag`), has its name, signal
 * type, safety flag, address and comment.
 */
const props = defineProps<{ productId: number; tag?: PlcTag }>()

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ saved: [] }>()

const { t } = useI18n()

const name = ref('')
const signalType = ref<ProductDeviceSignalType>('di')
const safety = ref(false)
const address = ref('')
const comment = ref('')
const error = ref<string | null>(null)
const saving = ref(false)

const built = computed(() => props.tag !== undefined && props.tag.manual_id === null)

watch(visible, (open) => {
  if (!open) return
  error.value = null
  const tag = props.tag
  name.value = tag?.name ?? ''
  signalType.value = (tag?.signal_type as ProductDeviceSignalType | undefined) ?? 'di'
  safety.value = tag?.safety ?? false
  address.value = tag?.address ?? ''
  comment.value = tag?.manual_id ? tag.comment : ''
})

const nameValid = computed(() => /^[A-Za-z0-9_]+$/.test(name.value.trim()))
const typeOptions = computed(() => SIGNAL_TYPES.map((value) => ({ value, label: value.toUpperCase() })))

async function run(action: () => Promise<void>): Promise<void> {
  saving.value = true
  error.value = null
  try {
    await action()
    emit('saved')
    visible.value = false
  } catch (e) {
    error.value = extractApiError(e) ?? t('productDevices.tags.saveFailed')
  } finally {
    saving.value = false
  }
}

function save(): void {
  if (!nameValid.value) {
    error.value = t('productDevices.tags.nameInvalid')
    return
  }
  const tag = props.tag
  if (tag && built.value) {
    void run(() => setSignalTagName(tag.device_id, tag.component_id, tag.signal_index, name.value.trim()))
    return
  }
  const body = {
    name: name.value.trim(),
    signal_type: signalType.value,
    safety: signalType.value === 'bus' ? false : safety.value,
    address: address.value.trim() || null,
    comment: comment.value.trim(),
  }
  void run(() => (tag?.manual_id ? updateManualPlcTag(tag.manual_id, body) : createManualPlcTag(props.productId, body)))
}

function resetName(): void {
  const tag = props.tag
  if (tag) void run(() => setSignalTagName(tag.device_id, tag.component_id, tag.signal_index, null))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="tag ? t('productDevices.tags.editTag') : t('productDevices.tags.addTag')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <form class="tag-form" @submit.prevent="save">
      <p v-if="built" class="hint">{{ t('productDevices.tags.builtHint', { device: tag?.device_name }) }}</p>
      <div class="field">
        <label for="plc-tag-name">{{ t('productDevices.tags.columns.name') }}</label>
        <InputText
          id="plc-tag-name"
          v-model="name"
          :maxlength="200"
          :invalid="name.trim() !== '' && !nameValid"
          fluid
          data-testid="plc-tag-name"
        />
      </div>
      <template v-if="!built">
        <div class="row">
          <div class="field">
            <label id="plc-tag-type-label" for="plc-tag-type">{{ t('productDevices.tags.columns.type') }}</label>
            <Select v-model="signalType" input-id="plc-tag-type" aria-labelledby="plc-tag-type-label" :options="typeOptions" option-label="label" option-value="value" />
          </div>
          <div class="field">
            <label for="plc-tag-address">{{ t('productDevices.tags.columns.address') }}</label>
            <InputText id="plc-tag-address" v-model="address" :maxlength="30" />
          </div>
          <label class="check">
            <Checkbox v-model="safety" binary :disabled="signalType === 'bus'" />
            {{ t('productDevices.devices.fields.signalSafety') }}
          </label>
        </div>
        <div class="field">
          <label for="plc-tag-comment">{{ t('productDevices.tags.columns.comment') }}</label>
          <InputText id="plc-tag-comment" v-model="comment" :maxlength="500" fluid />
        </div>
      </template>
      <Message v-if="error" severity="error">{{ error }}</Message>
      <div class="form-footer">
        <Button
          v-if="built && tag?.overridden"
          type="button"
          :label="t('productDevices.tags.resetName')"
          icon="mdi mdi-backup-restore"
          severity="secondary"
          text
          :disabled="saving"
          data-testid="plc-tag-reset"
          @click="resetName"
        />
        <Button type="button" :label="t('common.cancel')" severity="secondary" :disabled="saving" @click="visible = false" />
        <Button type="submit" :label="t('common.save')" :loading="saving" data-testid="plc-tag-save" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.tag-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.row {
  display: flex;
  gap: var(--space-3);
  align-items: flex-end;
}

.check {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding-bottom: var(--space-2);
}

.hint {
  margin: 0;
}
</style>
