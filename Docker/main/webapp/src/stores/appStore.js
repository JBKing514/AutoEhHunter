import { ref } from "vue";
import { defineStore } from "pinia";
import {
  changePassword,
  deleteAccount,
  getAuthBootstrap,
  getCsrfToken,
  getMe,
  getSetupStatus,
  login,
  logout,
  registerAdmin,
  setCsrfToken,
  updateProfile,
} from "../api";
import { useToastStore } from "./useToastStore";

export const useAppStore = defineStore("app", () => {
  const toast = useToastStore();

  const showAuthGate = ref(false);
  const showSetupWizard = ref(false);
  const authConfigured = ref(true);
  const authSubmitting = ref(false);
  const authError = ref("");
  const authReady = ref(false);
  const authUser = ref({ uid: "", username: "", role: "" });
  const accountForm = ref({ username: "", oldPassword: "", newPassword: "", newPassword2: "" });

  let _t = (k) => k;
  let _afterAuthOk = null;
  let _afterLogout = null;

  function init(deps = {}) {
    if (typeof deps.t === "function") _t = deps.t;
    if (typeof deps.afterAuthOk === "function") _afterAuthOk = deps.afterAuthOk;
    if (typeof deps.afterLogout === "function") _afterLogout = deps.afterLogout;
  }

  async function bootstrap() {
    authError.value = "";
    authReady.value = false;
    showAuthGate.value = false;
    try {
      const b = await getAuthBootstrap();
      authConfigured.value = !!b.configured;
      if (b.configured) {
        const me = await getMe();
        authUser.value = me.user || {};
        accountForm.value.username = String(authUser.value.username || "");
        const csrf = await getCsrfToken();
        setCsrfToken(csrf.csrf_token || "");
        const st = await getSetupStatus();
        showSetupWizard.value = !st.initialized;
        showAuthGate.value = false;
      } else {
        showAuthGate.value = true;
      }
    } catch (e) {
      authConfigured.value = true;
      showAuthGate.value = true;
      authError.value = String(e?.response?.data?.detail || e);
    } finally {
      authReady.value = true;
    }
  }

  function onAuthRequiredEvent() {
    showAuthGate.value = true;
    authError.value = _t("auth.required");
    setCsrfToken("");
  }

  async function registerNow(payload) {
    authSubmitting.value = true;
    authError.value = "";
    try {
      const res = await registerAdmin(payload?.username, payload?.password);
      authUser.value = res.user || {};
      accountForm.value.username = String(authUser.value.username || "");
      setCsrfToken(res?.session?.csrf_token || "");
      authConfigured.value = true;
      showAuthGate.value = false;
      showSetupWizard.value = true;
      if (_afterAuthOk) await _afterAuthOk();
    } catch (e) {
      authError.value = String(e?.response?.data?.detail || e);
    } finally {
      authSubmitting.value = false;
    }
  }

  async function loginNow(payload) {
    authSubmitting.value = true;
    authError.value = "";
    try {
      const res = await login(payload?.username, payload?.password);
      setCsrfToken(res?.session?.csrf_token || "");
      const me = await getMe();
      authUser.value = me.user || {};
      accountForm.value.username = String(authUser.value.username || "");
      const st = await getSetupStatus();
      showSetupWizard.value = !st.initialized;
      showAuthGate.value = false;
      if (_afterAuthOk) await _afterAuthOk();
    } catch (e) {
      authError.value = String(e?.response?.data?.detail || e);
    } finally {
      authSubmitting.value = false;
    }
  }

  async function logoutNow() {
    try {
      await logout();
    } catch {
      // ignore
    }
    setCsrfToken("");
    showAuthGate.value = true;
    if (_afterLogout) _afterLogout();
  }

  async function updateAccountUsername() {
    try {
      const res = await updateProfile(accountForm.value.username);
      authUser.value = res.user || authUser.value;
      accountForm.value.username = String(authUser.value.username || "");
      toast.success(_t("auth.profile.updated"));
    } catch (e) {
      toast.warning(String(e?.response?.data?.detail || e));
    }
  }

  async function updateAccountPassword() {
    if (String(accountForm.value.newPassword || "") !== String(accountForm.value.newPassword2 || "")) {
      toast.warning(_t("auth.profile.password_mismatch"));
      return;
    }
    try {
      await changePassword(accountForm.value.oldPassword, accountForm.value.newPassword);
      toast.success(_t("auth.profile.password_changed"));
      accountForm.value.oldPassword = "";
      accountForm.value.newPassword = "";
      accountForm.value.newPassword2 = "";
      await logoutNow();
    } catch (e) {
      toast.warning(String(e?.response?.data?.detail || e));
    }
  }

  async function deleteAccountNow(password) {
    const pwd = String(password || prompt(_t("auth.profile.delete_confirm")) || "").trim();
    if (!pwd) return;
    try {
      await deleteAccount(pwd);
      toast.success(_t("auth.profile.deleted"));
      await logoutNow();
    } catch (e) {
      toast.warning(String(e?.response?.data?.detail || e));
    }
  }

  function openSetupWizardManual() {
    showSetupWizard.value = true;
  }

  function closeSetupWizard() {
    showSetupWizard.value = false;
  }

  return {
    showAuthGate,
    showSetupWizard,
    authConfigured,
    authSubmitting,
    authError,
    authReady,
    authUser,
    accountForm,
    init,
    bootstrap,
    onAuthRequiredEvent,
    registerNow,
    loginNow,
    logoutNow,
    updateAccountUsername,
    updateAccountPassword,
    deleteAccountNow,
    openSetupWizardManual,
    closeSetupWizard,
  };
});
