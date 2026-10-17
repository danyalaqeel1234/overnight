/**
 * API Client with Mock-First Architecture and Live Fallback
 * Complies with LAPTOP2_MOBILE_BRIEF and CONVENTIONS.md
 */

import { mockStandings, mockMatches, mockProducts, mockRoster, Match, Product, Player, StandingsEntry } from '../mocks/mockData';

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

export class ApiClient {
  private baseUrl: string;
  private useMock: boolean;

  constructor(baseUrl: string = 'http://10.0.2.2:8080', useMock: boolean = true) {
    this.baseUrl = baseUrl;
    this.useMock = useMock;
  }

  setBaseUrl(url: string) {
    this.baseUrl = url;
  }

  setUseMock(mock: boolean) {
    this.useMock = mock;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  isMockMode(): boolean {
    return this.useMock;
  }

  // Simulated latency for smooth loading state demo
  private async delay(ms: number = 400): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Ping Server / Health check
  async ping(): Promise<{ ok: boolean; status: number; latencyMs: number; message: string }> {
    const startTime = Date.now();
    if (this.useMock) {
      await this.delay(200);
      return {
        ok: true,
        status: 200,
        latencyMs: Date.now() - startTime,
        message: 'Mock Mode Active — Instant simulated responses',
      };
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3500);
      const res = await fetch(`${this.baseUrl}/api/v1/health`, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const latencyMs = Date.now() - startTime;
      return {
        ok: res.ok,
        status: res.status,
        latencyMs,
        message: res.ok
          ? `Connected to backend (${latencyMs}ms)`
          : `Server returned status ${res.status}`,
      };
    } catch (err: any) {
      const latencyMs = Date.now() - startTime;
      return {
        ok: false,
        status: 0,
        latencyMs,
        message: err.name === 'AbortError'
          ? 'Connection timed out (3.5s). Verify Laptop 1 IP & port.'
          : 'Unable to reach backend. Check network hotspot connection.',
      };
    }
  }

  // Journey 1: Standings & Matches
  async getStandings(): Promise<StandingsEntry[]> {
    if (this.useMock) {
      await this.delay(350);
      return [...mockStandings];
    }
    const res = await fetch(`${this.baseUrl}/api/v1/standings`);
    if (!res.ok) throw new Error('Could not load league standings. Please check server.');
    return res.json();
  }

  async getMatches(): Promise<Match[]> {
    if (this.useMock) {
      await this.delay(300);
      return [...mockMatches];
    }
    const res = await fetch(`${this.baseUrl}/api/v1/matches`);
    if (!res.ok) throw new Error('Could not load matches.');
    return res.json();
  }

  async getMatchDetail(id: string): Promise<Match | undefined> {
    if (this.useMock) {
      await this.delay(250);
      return mockMatches.find(m => m.id === id);
    }
    const res = await fetch(`${this.baseUrl}/api/v1/matches/${id}`);
    if (!res.ok) throw new Error('Match details not found.');
    return res.json();
  }

  // Journey 2: Apparel Catalogue & Checkout
  async getProducts(): Promise<Product[]> {
    if (this.useMock) {
      await this.delay(300);
      return [...mockProducts];
    }
    const res = await fetch(`${this.baseUrl}/api/v1/store/products`);
    if (!res.ok) throw new Error('Could not load apparel catalogue.');
    return res.json();
  }

  async checkoutOrder(payload: {
    productId: string;
    variantSize: string;
    variantColor: string;
    quantity: number;
    paymentToken: string;
  }): Promise<{ orderId: string; totalPKR: number; status: string; message: string }> {
    if (this.useMock) {
      await this.delay(600);
      if (payload.paymentToken !== 'tok_success') {
        throw new Error('Payment declined: invalid token. Use tok_success for mock checkout.');
      }
      return {
        orderId: `ORD-${Math.floor(100000 + Math.random() * 900000)}`,
        totalPKR: 4500.00,
        status: 'PAID',
        message: 'Order placed successfully with mock token tok_success!',
      };
    }

    const res = await fetch(`${this.baseUrl}/api/v1/store/checkout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Payment processing error' }));
      throw new Error(err.detail || 'Payment could not be processed.');
    }
    return res.json();
  }

  // Journey 3: Roster Management
  async getRoster(): Promise<Player[]> {
    if (this.useMock) {
      await this.delay(300);
      return [...mockRoster];
    }
    const res = await fetch(`${this.baseUrl}/api/v1/roster`);
    if (!res.ok) throw new Error('Could not fetch club roster.');
    return res.json();
  }
}

export const apiClient = new ApiClient();
