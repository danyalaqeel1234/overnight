import * as SQLite from 'expo-sqlite';
import * as SecureStore from 'expo-secure-store';

export type User = {email: string; sub: string; name: string; role: string; tenant_id: string; club_id: string; league_id: string};
export type Session = {token: string; user: User};
export type Action = {action_id: string; type: 'score_event'|'roster_transfer'; queued_at: string; base_version: number; payload: any};
export type QueueRow = {id: string; server: string; owner: string; action: string; status: string; result: string|null};
let dbPromise: Promise<SQLite.SQLiteDatabase> | undefined;
export async function database() {
  if (!dbPromise) dbPromise = (async () => {
    const db = await SQLite.openDatabaseAsync('league_operations_v2.db');
    await db.execAsync(`PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS action_queue (id TEXT PRIMARY KEY, server TEXT NOT NULL, owner TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', result TEXT);
      CREATE INDEX IF NOT EXISTS queue_scope ON action_queue(server,owner,status);`);
    return db;
  })();
  return dbPromise;
}
export async function save(key: string, value: any) {
  await (await database()).runAsync('INSERT OR REPLACE INTO cache(key,data) VALUES (?,?)', key, JSON.stringify(value));
}
export async function load<T>(key: string): Promise<T|null> {
  const row = await (await database()).getFirstAsync<{data:string}>('SELECT data FROM cache WHERE key=?', key);
  return row ? JSON.parse(row.data) : null;
}
export function scoped(server: string, user: User) { return `${server}|${user.email}`; }
export function unique(prefix = 'id') { return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2,10)}`; }
export async function deviceId() {
  let id = await SecureStore.getItemAsync('device-id');
  if (!id) {id = unique('device'); await SecureStore.setItemAsync('device-id', id);}
  return id;
}
export async function sessions(): Promise<Record<string,Session>> {
  return JSON.parse(await SecureStore.getItemAsync('sessions') || '{}');
}
export async function remember(server: string, session: Session) {
  const all = await sessions(); all[scoped(server,session.user)] = session;
  await SecureStore.setItemAsync('sessions', JSON.stringify(all));
  await save('active-session', scoped(server,session.user));
}
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {super(message);}
}
export async function request(server: string, path: string, session?: Session|null, data?: any): Promise<any> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4500);
  try {
    const response = await fetch(server + path, {method: data === undefined ? 'GET' : 'POST', signal:controller.signal,
      headers: {'Content-Type':'application/json', ...(session ? {Authorization:`Bearer ${session.token}`} : {})},
      ...(data === undefined ? {} : {body:JSON.stringify(data)})});
    const result = await response.json();
    if (!response.ok) throw new ApiError(response.status, result.error?.code || 'REQUEST_FAILED', result.error?.message || 'The request could not be completed.');
    return result;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0,'OFFLINE','Cannot reach your server. Check Wi-Fi and the laptop address.');
  } finally {clearTimeout(timeout);}
}
export const explanations: Record<string,string> = {
  SQUAD_FULL:'The destination squad is full. The player stayed in their original squad.',
  NOT_IN_SQUAD:'The player has already moved. Refresh the roster before trying again.',
  TRANSFER_WINDOW_CLOSED:'The transfer window is closed. No player was moved.',
  PLAYER_ON_LOAN:'This player is on loan and cannot be moved again yet.',
  MIN_POSITION_VIOLATION:'The move would leave the squad without a required position.',
  CROSS_TENANT_TRANSFER:'Players cannot be transferred to another tenant.',
  MATCH_NOT_IN_PROGRESS:'The match is not live. Your score was not added.',
  ILLEGAL_TRANSITION:'The match status has changed. This action was not applied.',
  INVALID_BASE_VERSION:'The server data changed. Refresh before entering this action again.',
  INVALID_COMPENSATION:'That event cannot be reversed, or has already been reversed.',
  MATCH_NOT_FOUND:'The match no longer exists on this server.',
  PLAYER_NOT_FOUND:'The player no longer exists on this server.',
  SQUAD_NOT_FOUND:'The squad no longer exists on this server.',
  DUPLICATE_EVENT_ID:'This event ID was already used for different data.',
  FORBIDDEN:'This account does not have permission for the action.',
  UNAUTHENTICATED:'Sign in to this account again to send its pending actions.',
  PAYMENT_DECLINED:'Payment declined. No stock was deducted. You can try again.',
  PAYMENT_CAPTURE_FAILED:'Payment capture failed. Authorization was voided and stock released.',
  OUT_OF_STOCK:'This variant is out of stock. Choose another size or reduce the quantity.',
};
export function explain(code?:string|null) {return code ? explanations[code] || 'The server could not accept this action. Refresh the relevant screen and review your entry.' : 'Saved successfully.';}
export async function queue(server: string, session: Session, action: Action) {
  await (await database()).runAsync('INSERT INTO action_queue(id,server,owner,action,status) VALUES (?,?,?,?,?)',action.action_id,server,session.user.email,JSON.stringify(action),'pending');
}
export async function queued(server: string):Promise<QueueRow[]> {
  return (await database()).getAllAsync<QueueRow>('SELECT * FROM action_queue WHERE server=? ORDER BY rowid',server);
}
let syncing = false;
export async function sync(server: string) {
  if (syncing) return;
  syncing = true;
  try {
    const all = await sessions();
    const pending = (await queued(server)).filter(q=>q.status==='pending');
    const owners = [...new Set(pending.map(q=>q.owner))];
    for (const owner of owners) {
      const session = all[`${server}|${owner}`];
      if (!session) continue;
      const rows = pending.filter(q=>q.owner===owner);
      for (let offset=0; offset<rows.length; offset+=100) {
        const batch = rows.slice(offset,offset+100);
        let response;
        try {response = await request(server,'/api/v1/mobile/offline-sync',session,{device_id:await deviceId(),actions:batch.map(q=>JSON.parse(q.action))});}
        catch(error) {
          // Keep pending actions intact on transport/auth failures; retry after reconnect/login.
          if (error instanceof ApiError && error.status===401) continue;
          throw error;
        }
        for (const result of response.results) {
          await (await database()).runAsync('UPDATE action_queue SET status=?,result=? WHERE id=?',result.status,JSON.stringify(result),result.action_id);
        }
      }
    }
  } finally {syncing=false;}
}
