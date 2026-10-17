/**
 * Local SQLite Cache Service (Section 8.4 Desk Check Step 1 & 2)
 * Caches fixtures, standings, and club profiles locally so the app
 * remains fully readable and interactive while offline / in Airplane Mode.
 */

import { getDatabase } from './database.ts';

export const localCache = {
  // --- Fixtures Cache ---
  async cacheFixtures(matchId: string, data: unknown): Promise<void> {
    const db = await getDatabase();
    const now = new Date().toISOString();
    await db.runAsync(
      `INSERT OR REPLACE INTO fixtures_cache (match_id, data, updated_at) VALUES (?, ?, ?);`,
      [matchId, JSON.stringify(data), now]
    );
  },

  async getCachedFixtures<T = unknown>(matchId: string): Promise<T | null> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<{ match_id: string; data: string; updated_at: string }>(
      `SELECT * FROM fixtures_cache WHERE match_id = ?;`,
      [matchId]
    );
    if (!row) return null;
    try {
      return JSON.parse(row.data) as T;
    } catch {
      return null;
    }
  },

  async getAllCachedFixtures<T = unknown>(): Promise<T[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<{ match_id: string; data: string; updated_at: string }>(
      `SELECT * FROM fixtures_cache ORDER BY updated_at DESC;`
    );
    return rows.map(r => {
      try {
        return JSON.parse(r.data) as T;
      } catch {
        return null as unknown as T;
      }
    }).filter(Boolean);
  },

  // --- Standings Cache ---
  async cacheStandings(leagueId: string, data: unknown): Promise<void> {
    const db = await getDatabase();
    const now = new Date().toISOString();
    await db.runAsync(
      `INSERT OR REPLACE INTO standings_cache (league_id, data, updated_at) VALUES (?, ?, ?);`,
      [leagueId, JSON.stringify(data), now]
    );
  },

  async getCachedStandings<T = unknown>(leagueId: string): Promise<T | null> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<{ league_id: string; data: string; updated_at: string }>(
      `SELECT * FROM standings_cache WHERE league_id = ?;`,
      [leagueId]
    );
    if (!row) return null;
    try {
      return JSON.parse(row.data) as T;
    } catch {
      return null;
    }
  },

  // --- Club Profile Cache ---
  async cacheClubProfile(clubId: string, data: unknown): Promise<void> {
    const db = await getDatabase();
    const now = new Date().toISOString();
    await db.runAsync(
      `INSERT OR REPLACE INTO club_profile_cache (club_id, data, updated_at) VALUES (?, ?, ?);`,
      [clubId, JSON.stringify(data), now]
    );
  },

  async getCachedClubProfile<T = unknown>(clubId: string): Promise<T | null> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<{ club_id: string; data: string; updated_at: string }>(
      `SELECT * FROM club_profile_cache WHERE club_id = ?;`,
      [clubId]
    );
    if (!row) return null;
    try {
      return JSON.parse(row.data) as T;
    } catch {
      return null;
    }
  },
};

export const getCachedStandings = localCache.getCachedStandings.bind(localCache);
export const cacheStandings = localCache.cacheStandings.bind(localCache);
