import { create } from 'zustand';
import { Player, mockRoster } from '../mocks/mockData';

interface RosterState {
  players: Player[];
  selectedPlayer: Player | null;
  lastActionMessage: string | null;
  setSelectedPlayer: (player: Player | null) => void;
  transferPlayer: (playerId: string, destinationClub?: string) => { success: boolean; message: string };
  loanPlayer: (playerId: string, durationMonths?: number) => { success: boolean; message: string };
  releasePlayer: (playerId: string) => { success: boolean; message: string };
  resetRoster: () => void;
  clearActionMessage: () => void;
}

export const useRosterStore = create<RosterState>((set, get) => ({
  players: [...mockRoster],
  selectedPlayer: null,
  lastActionMessage: null,

  setSelectedPlayer: (player: Player | null) => {
    set({ selectedPlayer: player });
  },

  transferPlayer: (playerId: string, destinationClub: string = 'Al-Sharjah FC') => {
    const player = get().players.find(p => p.id === playerId);
    if (!player) return { success: false, message: 'Player not found' };

    set(state => ({
      players: state.players.map(p =>
        p.id === playerId ? { ...p, status: 'Transferred' as const } : p
      ),
      lastActionMessage: `Transfer agreement finalized: ${player.name} transferred to ${destinationClub} for ${player.marketValuePKR}.`,
    }));
    return {
      success: true,
      message: `Successfully transferred ${player.name} to ${destinationClub}.`,
    };
  },

  loanPlayer: (playerId: string, durationMonths: number = 6) => {
    const player = get().players.find(p => p.id === playerId);
    if (!player) return { success: false, message: 'Player not found' };

    set(state => ({
      players: state.players.map(p =>
        p.id === playerId ? { ...p, status: 'On Loan' as const } : p
      ),
      lastActionMessage: `Loan deal confirmed: ${player.name} dispatched on a ${durationMonths}-month development loan.`,
    }));
    return {
      success: true,
      message: `${player.name} sent on loan for ${durationMonths} months.`,
    };
  },

  releasePlayer: (playerId: string) => {
    const player = get().players.find(p => p.id === playerId);
    if (!player) return { success: false, message: 'Player not found' };

    set(state => ({
      players: state.players.map(p =>
        p.id === playerId ? { ...p, status: 'Released' as const } : p
      ),
      lastActionMessage: `Contract terminated by mutual consent: ${player.name} is now a Free Agent.`,
    }));
    return {
      success: true,
      message: `Released ${player.name} from club roster.`,
    };
  },

  resetRoster: () => {
    set({
      players: [...mockRoster],
      lastActionMessage: 'Club roster restored to original competition roster.',
    });
  },

  clearActionMessage: () => {
    set({ lastActionMessage: null });
  },
}));
