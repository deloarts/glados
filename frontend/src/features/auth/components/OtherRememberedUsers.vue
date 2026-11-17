<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { initials, type RememberedUser } from '../utils/rememberedUsers'

defineProps<{ users: RememberedUser[]; disabled: boolean }>()

const emit = defineEmits<{ select: [user: RememberedUser] }>()

const { t } = useI18n()
</script>

<template>
  <div v-if="users.length > 0" class="other-users">
    <span class="other-users-label">{{ t('login.chooser.otherAccounts') }}</span>
    <button
      v-for="other in users"
      :key="other.username"
      type="button"
      class="other-user"
      :disabled="disabled"
      @click="emit('select', other)"
    >
      <img v-if="other.avatar" :src="other.avatar" alt="" class="other-user-avatar" />
      <span v-else class="other-user-avatar other-user-initials">
        {{ initials(other.fullName || other.username) }}
      </span>
      {{ other.fullName || other.username }}
    </button>
  </div>
</template>

<style scoped lang="scss">
// Part of the login card, which keeps its fixed dark look in every theme.
.other-users {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-top: var(--space-3);
  border-top: 1px solid var(--auth-line);
}

.other-users-label {
  color: var(--auth-text-muted);
  font-size: var(--font-size-xs);
  text-align: center;
}

.other-user {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  background: none;
  border: none;
  border-radius: 9px;
  cursor: pointer;
  color: var(--auth-text);
  font-family: inherit;
  font-size: var(--font-size-sm);
  text-align: left;
  transition: background 0.15s ease;

  &:hover:not(:disabled) {
    background: var(--auth-field);
  }

  &:disabled {
    cursor: default;
  }
}

.other-user-avatar {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  object-fit: cover;
}

.other-user-initials {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--auth-accent-fill);
  color: var(--auth-text-strong);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
</style>
