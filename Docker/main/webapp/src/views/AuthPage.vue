<template>
  <v-container class="fill-height d-flex align-center justify-center">
    <v-card class="pa-6" max-width="520" variant="flat">
      <div class="text-h6 mb-2">Authentication</div>
      <div class="text-body-2 text-medium-emphasis mb-4">
        This route is reserved for the standalone auth page. The current auth flow is still handled by global dialogs.
      </div>
      <v-btn color="primary" :to="{ path: '/dashboard' }">Back to Dashboard</v-btn>
    </v-card>
  </v-container>
</template>
