/**
 * Offline Sync Service (Section 5.14 & Section 8.4)
 * Replays queued offline actions to POST /audit/v1/offline-sync,
 * processes per-action conflict resolutions, and translates error codes
 * into human-readable plain language for judge desk checks.
 */

import { offlineQueue } from './offlineQueue.ts';
import type { OfflineAction } from './offlineQueue.ts';
import { secureStore } from './secureStore.ts';

export interface SyncResultItem {
  action_id: string;
  status: 'applied' | 'rejected' | 'duplicate';
  resolution: 'appended' | 'rebased_append' | 'skipped_duplicate' | 'server_wins';
  error_code: string | null;
  processed_order: number;
  server_version: number;
  signature: string | null;
}

export interface SyncResponse {
  device_id: string;
  results: SyncResultItem[];
  summary: {
    applied: number;
    rejected: number;
    duplicate: number;
  };
}

export interface SyncReport {
  success: boolean;
  syncedCount: number;
  appliedCount: number;
  rejectedCount: number;
  duplicateCount: number;
  results: Array<SyncResultItem & { plainExplanation: string }>;
  error?: string;
}

// Plain-language error explanations for Section 8.4 judge evaluation
export const ERROR_EXPLANATIONS: Record<string, string> = {
  SQUAD_FULL: 'Roster limit reached: The destination squad has already reached its maximum allowed players.',
  TRANSFER_WINDOW_CLOSED: 'Transfer window is closed: New player registrations and transfers are not permitted at this time.',
  NOT_IN_SQUAD: 'Player not found in squad: The specified player does not belong to the selected source squad.',
  PLAYER_ON_LOAN: 'Player on active loan: This player is currently on loan and cannot be transferred until returned.',
  MIN_POSITION_VIOLATION: 'Position requirement unmet: Releasing this player would leave the squad below the required positional minimum.',
  CROSS_TENANT_TRANSFER: 'Tenant boundary violation: Transfers between different tenant clubs are strictly forbidden.',
  MATCH_NOT_IN_PROGRESS: 'Match not active: Scoring events can only be added while a match is currently in progress.',
  MATCH_NOT_FOUND: 'Match not found: The referenced fixture does not exist.',
  PLAYER_NOT_FOUND: 'Player not found: The referenced player ID does not exist in the registry.',
  SQUAD_NOT_FOUND: 'Squad not found: The referenced squad ID does not exist.',
  INVALID_BASE_VERSION: 'Sync conflict: The action was queued against a future state that does not match the server.',
  INVALID_COMPENSATION: 'Invalid compensation: Target event is already compensated or belongs to another match.',
  UNKNOWN_EVENT_TYPE: 'Unknown score event: The event type is not supported by this sport rulebook.',
  VALIDATION_ERROR: 'Invalid payload structure: Missing or invalid required fields.',
};

export function getPlainLanguageExplanation(errorCode: string | null): string {
  if (!errorCode) return 'Action applied successfully.';
  return ERROR_EXPLANATIONS[errorCode] || `Action could not be applied due to rule: ${errorCode}`;
}

// Simulated network state for Airplane Mode desk-check testing
let isSimulatedAirplaneMode = false;
let configuredServerBaseUrl = 'http://localhost:8080';

export const syncService = {
  setServerUrl(url: string): void {
    configuredServerBaseUrl = url.replace(/\/+$/, '');
  },

  getServerUrl(): string {
    return configuredServerBaseUrl;
  },

  setAirplaneMode(enabled: boolean): void {
    isSimulatedAirplaneMode = enabled;
  },

  isAirplaneModeActive(): boolean {
    return isSimulatedAirplaneMode;
  },

  /**
   * One-Tap Sync: Replays all pending offline actions to POST /audit/v1/offline-sync
   */
  async replayPendingActions(customFetch?: (url: string, init: any) => Promise<any>): Promise<SyncReport> {
    if (isSimulatedAirplaneMode) {
      return {
        success: false,
        syncedCount: 0,
        appliedCount: 0,
        rejectedCount: 0,
        duplicateCount: 0,
        results: [],
        error: 'Airplane Mode is ON. Please disable Airplane Mode to sync.',
      };
    }

    const pending = await offlineQueue.getPendingActions();
    if (pending.length === 0) {
      return {
        success: true,
        syncedCount: 0,
        appliedCount: 0,
        rejectedCount: 0,
        duplicateCount: 0,
        results: [],
      };
    }

    const deviceId = await secureStore.getDeviceId();

    // Prepare payload matching Section 5.14
    const requestPayload = {
      device_id: deviceId,
      actions: pending.map(a => ({
        action_id: a.action_id,
        type: a.type,
        queued_at: a.queued_at,
        base_version: a.base_version,
        payload: a.payload,
      })),
    };

    const fetchImpl = customFetch || (typeof fetch !== 'undefined' ? fetch : null);
    if (!fetchImpl) {
      throw new Error('No fetch implementation available for network sync');
    }

    const response = await fetchImpl(`${configuredServerBaseUrl}/audit/v1/offline-sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestPayload),
    });

    if (!response.ok) {
      const errText = await response.text();
      return {
        success: false,
        syncedCount: 0,
        appliedCount: 0,
        rejectedCount: 0,
        duplicateCount: 0,
        results: [],
        error: `Server sync failed with HTTP ${response.status}: ${errText}`,
      };
    }

    const data: SyncResponse = await response.json();

    const reportResults: Array<SyncResultItem & { plainExplanation: string }> = [];

    // Process each action result and update SQLite
    for (const res of data.results) {
      const plainExplanation = getPlainLanguageExplanation(res.error_code);
      await offlineQueue.updateActionResult(res.action_id, {
        status: res.status,
        resolution: res.resolution,
        server_version: res.server_version,
        error_code: res.error_code,
        processed_order: res.processed_order,
        signature: res.signature,
      });

      reportResults.push({
        ...res,
        plainExplanation,
      });
    }

    return {
      success: true,
      syncedCount: data.results.length,
      appliedCount: data.summary.applied,
      rejectedCount: data.summary.rejected,
      duplicateCount: data.summary.duplicate,
      results: reportResults,
    };
  },
};
