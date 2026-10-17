/**
 * Persistent SQLite Offline Action Queue (Section 5.14 & Section 8.4)
 * Stores offline score events and roster actions in SQLite with status 'pending'.
 * Survives force-close and app restart.
 */

import { getDatabase } from './database.ts';

export interface OfflineAction<T = unknown> {
  action_id: string;
  type: 'score_event' | 'roster_transfer';
  queued_at: string;
  base_version: number;
  payload: T;
  status: 'pending' | 'syncing' | 'applied' | 'rejected' | 'duplicate';
  resolution?: 'appended' | 'rebased_append' | 'skipped_duplicate' | 'server_wins' | null;
  server_version?: number | null;
  error_code?: string | null;
  processed_order?: number | null;
  signature?: string | null;
  plain_explanation?: string | null;
}

export const offlineQueue = {
  /**
   * Enqueues an offline action into the SQLite table.
   * Status is set to 'pending'.
   */
  async enqueueAction<T = unknown>(params: {
    action_id?: string;
    type: 'score_event' | 'roster_transfer';
    base_version: number;
    payload: T;
    queued_at?: string;
  }): Promise<OfflineAction<T>> {
    const db = await getDatabase();
    const action_id = params.action_id || `act-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const queued_at = params.queued_at || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    const status = 'pending';
    const payloadStr = JSON.stringify(params.payload);

    await db.runAsync(
      `INSERT INTO offline_action_queue 
       (action_id, type, queued_at, base_version, payload, status) 
       VALUES (?, ?, ?, ?, ?, ?);`,
      [action_id, params.type, queued_at, params.base_version, payloadStr, status]
    );

    return {
      action_id,
      type: params.type,
      queued_at,
      base_version: params.base_version,
      payload: params.payload,
      status,
    };
  },

  /**
   * Returns all pending actions sorted chronologically (queued_at ASC).
   */
  async getPendingActions(): Promise<OfflineAction[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<{
      action_id: string;
      type: 'score_event' | 'roster_transfer';
      queued_at: string;
      base_version: number;
      payload: string;
      status: 'pending' | 'syncing' | 'applied' | 'rejected' | 'duplicate';
      resolution: string | null;
      server_version: number | null;
      error_code: string | null;
      processed_order: number | null;
      signature: string | null;
    }>(`SELECT * FROM offline_action_queue WHERE status = 'pending' ORDER BY queued_at ASC;`);

    return rows.map(r => ({
      action_id: r.action_id,
      type: r.type,
      queued_at: r.queued_at,
      base_version: r.base_version,
      payload: JSON.parse(r.payload),
      status: r.status,
      resolution: (r.resolution as any) || null,
      server_version: r.server_version,
      error_code: r.error_code,
      processed_order: r.processed_order,
      signature: r.signature,
    }));
  },

  /**
   * Returns all actions in the queue regardless of status.
   */
  async getAllActions(): Promise<OfflineAction[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<any>(
      `SELECT * FROM offline_action_queue ORDER BY queued_at ASC;`
    );

    return rows.map(r => ({
      action_id: r.action_id,
      type: r.type,
      queued_at: r.queued_at,
      base_version: r.base_version,
      payload: JSON.parse(r.payload),
      status: r.status,
      resolution: r.resolution || null,
      server_version: r.server_version,
      error_code: r.error_code,
      processed_order: r.processed_order,
      signature: r.signature,
    }));
  },

  /**
   * Updates an action's execution status following sync.
   */
  async updateActionResult(
    actionId: string,
    result: {
      status: 'applied' | 'rejected' | 'duplicate';
      resolution: 'appended' | 'rebased_append' | 'skipped_duplicate' | 'server_wins';
      server_version?: number | null;
      error_code?: string | null;
      processed_order?: number | null;
      signature?: string | null;
    }
  ): Promise<void> {
    const db = await getDatabase();
    await db.runAsync(
      `UPDATE offline_action_queue 
       SET status = ?, resolution = ?, server_version = ?, error_code = ?, processed_order = ?, signature = ? 
       WHERE action_id = ?;`,
      [
        result.status,
        result.resolution,
        result.server_version ?? null,
        result.error_code ?? null,
        result.processed_order ?? null,
        result.signature ?? null,
        actionId,
      ]
    );
  },

  /**
   * Deletes successfully applied and duplicate actions.
   */
  async clearSyncedActions(): Promise<void> {
    const db = await getDatabase();
    await db.runAsync(`DELETE FROM offline_action_queue WHERE status IN ('applied', 'duplicate');`);
  },

  /**
   * Wipes entire queue.
   */
  async clearAll(): Promise<void> {
    const db = await getDatabase();
    await db.runAsync(`DELETE FROM offline_action_queue;`);
  },

  /**
   * Returns count summary for UI indicators.
   */
  async getQueueSummary(): Promise<{
    pending: number;
    applied: number;
    rejected: number;
    duplicate: number;
    total: number;
  }> {
    const all = await this.getAllActions();
    return {
      pending: all.filter(a => a.status === 'pending').length,
      applied: all.filter(a => a.status === 'applied').length,
      rejected: all.filter(a => a.status === 'rejected').length,
      duplicate: all.filter(a => a.status === 'duplicate').length,
      total: all.length,
    };
  },
};

export const enqueueOfflineAction = offlineQueue.enqueueAction.bind(offlineQueue);
