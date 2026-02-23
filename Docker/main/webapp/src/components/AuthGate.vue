<template>
  <v-dialog :model-value="visible" persistent fullscreen :transition="false">
    <v-card class="auth-gate-wrap d-flex align-center justify-center">
      <v-sheet v-if="!app.authReady" class="auth-gate-card pa-8 text-center" rounded="xl" elevation="8">
        <div class="d-flex justify-center mb-4">
          <img v-if="logo" :src="logo" alt="AutoEhHunter" class="auth-logo" />
        </div>
        <v-progress-circular indeterminate color="primary" size="34" class="mb-3" />
        <div class="text-body-2 text-medium-emphasis">{{ t('auth.checking') }}</div>
      </v-sheet>
      <v-sheet v-else class="auth-gate-card pa-6" rounded="xl" elevation="8">
        <div class="d-flex justify-center mb-3">
          <img v-if="logo" :src="logo" alt="AutoEhHunter" class="auth-logo" />
        </div>
        <div class="text-body-2 text-medium-emphasis text-center mb-4">{{ t('auth.welcome') }}</div>
        <div class="text-h6 font-weight-bold mb-1">{{ app.authConfigured === false ? t('auth.register.title') : t('auth.login.title') }}</div>
        <div class="text-body-2 text-medium-emphasis mb-5">{{ app.authConfigured === false ? t('auth.register.hint') : t('auth.login.hint') }}</div>

        <v-alert v-if="app.authError" type="warning" variant="tonal" class="mb-4">{{ app.authError }}</v-alert>

        <v-text-field v-model="username" :label="t('auth.username')" autocomplete="username" class="mb-2" />
        <v-text-field v-model="password" :label="t('auth.password')" type="password" autocomplete="current-password" class="mb-2" @keyup.enter="submit" />
        <v-text-field v-if="app.authConfigured === false" v-model="password2" :label="t('auth.password_confirm')" type="password" autocomplete="new-password" class="mb-4" @keyup.enter="submit" />

        <v-btn block color="primary" :loading="app.authSubmitting" @click="submit">{{ app.authConfigured === false ? t('auth.register.submit') : t('auth.login.submit') }}</v-btn>
      </v-sheet>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed, ref } from "vue";
import { useAppStore } from "../stores/appStore";

const props = defineProps({
  logo: { type: String, default: "" },
  t: { type: Function, required: true },
});
const app = useAppStore();
const visible = computed(() => !app.authReady || app.showAuthGate);

const username = ref("");
const password = ref("");
const password2 = ref("");

function submit() {
  const user = String(username.value || "").trim();
  const pass = String(password.value || "");
  if (!user || !pass) return;
  if (app.authConfigured === false) {
    if (pass !== String(password2.value || "")) return;
    app.registerNow({ username: user, password: pass }).catch(() => null);
    return;
  }
  app.loginNow({ username: user, password: pass }).catch(() => null);
}
</script>
