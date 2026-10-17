/**
 * Judge Desk-Check Sequence Verifier (Section 8.4)
 * Proves the exact 5-step judge sequence:
 * 1. Airplane Mode ON.
 * 2. Perform score event & roster action -> appears 'pending'.
 * 3. Force-close app & reopen (action MUST still be in SQLite).
 * 4. Airplane Mode OFF.
 * 5. One-tap sync replays to POST /audit/v1/offline-sync -> updates SQLite.
 */

import { offlineQueue } from './offlineQueue.ts';
import type { OfflineAction } from './offlineQueue.ts';
import { syncService } from './sync.ts';
import type { SyncReport } from './sync.ts';
import { simulateForceCloseAndReopen } from './database.ts';
import { localCache } from './cache.ts';

export interface DeskCheckStepResult {
  step: number;
  name: string;
  success: boolean;
  details: string;
  data?: unknown;
}

export async function runDeskCheckVerification(
  mockSyncServerHandler?: (req: any) => Promise<any>
): Promise<{
  allPassed: boolean;
  steps: DeskCheckStepResult[];
}> {
  const steps: DeskCheckStepResult[] = [];

  try {
    // Step 0: Ensure baseline cache works online
    await localCache.cacheStandings('lg-alpha-1', {
      league_id: 'lg-alpha-1',
      teams: [{ team_id: 't1', points: 6 }, { team_id: 't2', points: 3 }],
    });
    await localCache.cacheClubProfile('club-alpha-1', {
      club_id: 'club-alpha-1',
      name: 'Alpha FC',
      squad_count: 18,
    });

    // STEP 1: Turn Airplane Mode ON
    syncService.setAirplaneMode(true);
    const cachedStandings = await localCache.getCachedStandings('lg-alpha-1');
    const isAirplane = syncService.isAirplaneModeActive();

    steps.push({
      step: 1,
      name: 'Airplane Mode ON & Offline Cache Verification',
      success: isAirplane && cachedStandings !== null,
      details: 'Airplane mode activated. Offline cached standings retrieved successfully from SQLite.',
      data: { isAirplane, cachedStandings },
    });

    // STEP 2: Perform actions while offline (Score Event + Roster Transfer)
    const scoreAction = await offlineQueue.enqueueAction({
      action_id: 'desk-check-act-1',
      type: 'score_event',
      base_version: 2,
      payload: {
        event_id: 'evt-desk-1',
        match_id: 'm1',
        type: 'score',
        payload: { team_id: 't1', event_type: 'goal' },
      },
    });

    const rosterAction = await offlineQueue.enqueueAction({
      action_id: 'desk-check-act-2',
      type: 'roster_transfer',
      base_version: 1,
      payload: {
        request_id: 'req-desk-1',
        league_id: 'league-alpha-1',
        player_id: 'player-alpha-1',
        from_squad_id: 'squad-alpha-1',
        to_squad_id: 'squad-alpha-2',
        type: 'transfer',
        effective_date: '2026-10-17',
      },
    });

    const pendingAfterCreate = await offlineQueue.getPendingActions();
    const step2Passed =
      pendingAfterCreate.length >= 2 &&
      pendingAfterCreate.every(a => a.status === 'pending');

    steps.push({
      step: 2,
      name: 'Perform Offline Actions (Status: Pending)',
      success: step2Passed,
      details: `Enqueued ${pendingAfterCreate.length} actions in SQLite with status 'pending'.`,
      data: pendingAfterCreate,
    });

    // STEP 3: Force-Close & Reopen (Persistence Verification)
    // Kill in-memory handle and reconnect to SQLite on disk
    await simulateForceCloseAndReopen();

    const pendingAfterRestart = await offlineQueue.getPendingActions();
    const step3Passed =
      pendingAfterRestart.length >= 2 &&
      pendingAfterRestart.some(a => a.action_id === 'desk-check-act-1' && a.status === 'pending') &&
      pendingAfterRestart.some(a => a.action_id === 'desk-check-act-2' && a.status === 'pending');

    steps.push({
      step: 3,
      name: 'Force-Close App & Reopen (SQLite Persistence Check)',
      success: step3Passed,
      details: 'App force-closed and memory destroyed. Pending actions survived and reloaded from SQLite.',
      data: pendingAfterRestart,
    });

    // STEP 4: Airplane Mode OFF
    syncService.setAirplaneMode(false);
    const airplaneOff = !syncService.isAirplaneModeActive();

    steps.push({
      step: 4,
      name: 'Airplane Mode OFF',
      success: airplaneOff,
      details: 'Network connectivity restored. Airplane mode disabled.',
    });

    // STEP 5: One-Tap Sync Replays to POST /audit/v1/offline-sync
    // Provide mock fetch if testing without live server
    const mockFetch = async (url: string, init: any) => {
      if (mockSyncServerHandler) {
        const body = JSON.parse(init.body);
        const res = await mockSyncServerHandler(body);
        return {
          ok: true,
          status: 200,
          json: async () => res,
        };
      }
      // Standard mock replay response matching Section 5.14
      return {
        ok: true,
        status: 200,
        json: async () => ({
          device_id: 'dev-1',
          results: [
            {
              action_id: 'desk-check-act-1',
              status: 'applied',
              resolution: 'rebased_append',
              error_code: null,
              processed_order: 1,
              server_version: 3,
              signature: '972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501',
            },
            {
              action_id: 'desk-check-act-2',
              status: 'applied',
              resolution: 'appended',
              error_code: null,
              processed_order: 2,
              server_version: 2,
              signature: null,
            },
          ],
          summary: { applied: 2, rejected: 0, duplicate: 0 },
        }),
      };
    };

    const syncReport = await syncService.replayPendingActions(mockFetch);
    const step5Passed = syncReport.success && syncReport.appliedCount === 2;

    const allInDb = await offlineQueue.getAllActions();
    steps.push({
      step: 5,
      name: 'One-Tap Sync Replay to POST /audit/v1/offline-sync',
      success: step5Passed,
      details: `Replayed ${syncReport.syncedCount} actions. Results: ${syncReport.appliedCount} applied, ${syncReport.rejectedCount} rejected.`,
      data: { syncReport, storedActions: allInDb },
    });

    const allPassed = steps.every(s => s.success);
    return { allPassed, steps };
  } catch (err: any) {
    steps.push({
      step: steps.length + 1,
      name: 'Desk Check Execution Error',
      success: false,
      details: err.message || String(err),
    });
    return { allPassed: false, steps };
  }
}
