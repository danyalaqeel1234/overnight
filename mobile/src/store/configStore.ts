import { create } from 'zustand';
import { apiClient } from '../api/client';

interface ConfigState {
  serverUrl: string;
  useMock: boolean;
  isPinging: boolean;
  pingResult: {
    tested: boolean;
    ok: boolean;
    status: number;
    latencyMs: number;
    message: string;
    timestamp?: string;
  };
  setServerUrl: (url: string) => void;
  setUseMock: (useMock: boolean) => void;
  testConnection: () => Promise<void>;
  resetToDefaults: () => void;
}

export const useConfigStore = create<ConfigState>((set, get) => ({
  serverUrl: process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:8080',
  useMock: process.env.EXPO_PUBLIC_USE_MOCK !== 'false',
  isPinging: false,
  pingResult: {
    tested: false,
    ok: true,
    status: 200,
    latencyMs: 12,
    message: 'Mock Mode Active (Local high-performance)',
  },

  setServerUrl: (url: string) => {
    const cleanUrl = url.trim();
    apiClient.setBaseUrl(cleanUrl);
    set({ serverUrl: cleanUrl });
  },

  setUseMock: (useMock: boolean) => {
    apiClient.setUseMock(useMock);
    set({
      useMock,
      pingResult: {
        tested: true,
        ok: true,
        status: 200,
        latencyMs: useMock ? 5 : 0,
        message: useMock
          ? 'Switched to Mock Mode (offline resilient)'
          : 'Switched to Live Mode — Remember to test connection',
      },
    });
  },

  testConnection: async () => {
    set({ isPinging: true });
    try {
      const res = await apiClient.ping();
      set({
        isPinging: false,
        pingResult: {
          tested: true,
          ok: res.ok,
          status: res.status,
          latencyMs: res.latencyMs,
          message: res.message,
          timestamp: new Date().toLocaleTimeString(),
        },
      });
    } catch (err: any) {
      set({
        isPinging: false,
        pingResult: {
          tested: true,
          ok: false,
          status: 500,
          latencyMs: 0,
          message: err?.message || 'Connection failed',
          timestamp: new Date().toLocaleTimeString(),
        },
      });
    }
  },

  resetToDefaults: () => {
    const defaultUrl = 'http://10.0.2.2:8080';
    apiClient.setBaseUrl(defaultUrl);
    apiClient.setUseMock(true);
    set({
      serverUrl: defaultUrl,
      useMock: true,
      pingResult: {
        tested: false,
        ok: true,
        status: 200,
        latencyMs: 10,
        message: 'Mock Mode Active',
      },
    });
  },
}));
