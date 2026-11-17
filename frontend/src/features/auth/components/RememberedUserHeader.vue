<script setup lang="ts">
import { initials, type RememberedUser } from '../utils/rememberedUsers'

defineProps<{ user: RememberedUser }>()
</script>

<template>
  <div class="remembered-user" data-testid="login-remembered-user">
    <img v-if="user.avatar" :src="user.avatar" alt="" class="remembered-avatar" />
    <span v-else class="remembered-avatar remembered-initials">
      {{ initials(user.fullName || user.username) }}
    </span>
    <span class="remembered-name">{{ user.fullName || user.username }}</span>
    <span class="remembered-username">{{ user.username }}</span>
  </div>
</template>

<style scoped lang="scss">
// Part of the login card, which keeps its fixed dark look in every theme.
.remembered-user {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
}

.remembered-avatar {
  width: 4.5rem;
  height: 4.5rem;
  border-radius: 50%;
  object-fit: cover;
  margin-bottom: var(--space-2);
  box-shadow: var(--auth-avatar-ring);
}

.remembered-initials {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--auth-accent-fill);
  color: var(--auth-text-strong);
  font-family: 'Play', sans-serif;
  font-size: var(--font-size-lg);
  font-weight: 700;
}

.remembered-name {
  color: var(--auth-text-strong);
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.remembered-username {
  color: var(--auth-text-muted);
  font-size: var(--font-size-sm);
}
</style>
