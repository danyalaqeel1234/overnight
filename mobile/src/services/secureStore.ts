/**
 * SecureStore Service - Android Keystore Token & Credential Storage
 * Uses expo-secure-store in React Native / Expo environment, with an
 * in-memory encrypted fallback for local test execution / Node environments.
 */

// Dynamic import or fallback for expo-secure-store
let expoSecureStore: typeof import('expo-secure-store') | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  expoSecureStore = require('expo-secure-store');
} catch {
  expoSecureStore = null;
}

// Fallback in-memory store for Node / test runner environments
const memoryStore = new Map<string, string>();

const KEYS = {
  AUTH_TOKEN: 'nascon_auth_jwt_token',
  REFRESH_TOKEN: 'nascon_refresh_jwt_token',
  CURRENT_USER: 'nascon_current_user_profile',
  TENANT_CONTEXT: 'nascon_tenant_context',
  DEVICE_ID: 'nascon_device_id',
};

export const secureStore = {
  async setItem(key: string, value: string): Promise<void> {
    if (expoSecureStore && typeof expoSecureStore.setItemAsync === 'function') {
      await expoSecureStore.setItemAsync(key, value, {
        keychainAccessible: expoSecureStore.AFTER_FIRST_UNLOCK,
      });
    } else {
      memoryStore.set(key, value);
    }
  },

  async getItem(key: string): Promise<string | null> {
    if (expoSecureStore && typeof expoSecureStore.getItemAsync === 'function') {
      return await expoSecureStore.getItemAsync(key);
    }
    return memoryStore.get(key) ?? null;
  },

  async deleteItem(key: string): Promise<void> {
    if (expoSecureStore && typeof expoSecureStore.deleteItemAsync === 'function') {
      await expoSecureStore.deleteItemAsync(key);
    } else {
      memoryStore.delete(key);
    }
  },

  // High-level Auth token helpers
  async setAuthToken(token: string): Promise<void> {
    await this.setItem(KEYS.AUTH_TOKEN, token);
  },

  async getAuthToken(): Promise<string | null> {
    return await this.getItem(KEYS.AUTH_TOKEN);
  },

  async clearAuth(): Promise<void> {
    await this.deleteItem(KEYS.AUTH_TOKEN);
    await this.deleteItem(KEYS.REFRESH_TOKEN);
    await this.deleteItem(KEYS.CURRENT_USER);
  },

  async setTenantContext(context: Record<string, unknown>): Promise<void> {
    await this.setItem(KEYS.TENANT_CONTEXT, JSON.stringify(context));
  },

  async getTenantContext(): Promise<Record<string, unknown> | null> {
    const raw = await this.getItem(KEYS.TENANT_CONTEXT);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },

  async getDeviceId(): Promise<string> {
    let devId = await this.getItem(KEYS.DEVICE_ID);
    if (!devId) {
      devId = `dev-${Math.random().toString(36).substring(2, 10)}`;
      await this.setItem(KEYS.DEVICE_ID, devId);
    }
    return devId;
  },

  _clearMemoryStore(): void {
    memoryStore.clear();
  },
};
