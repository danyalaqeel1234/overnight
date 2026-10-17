/**
 * Comprehensive Mock Data for NaSCon '26 Mobile Client
 * Supports all 3 Primary Judge Journeys
 */

export interface StandingsEntry {
  rank: number;
  team: string;
  shortName: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  gf: number;
  ga: number;
  gd: number;
  points: number;
  form: string[];
  isCurrentTeam?: boolean;
}

export interface MatchTimelineEvent {
  id: string;
  minute: number;
  type: 'goal' | 'card_yellow' | 'card_red' | 'sub' | 'var';
  player: string;
  team: string;
  description: string;
}

export interface Product {
  id: string;
  title: string;
  category: 'jerseys' | 'jackets' | 'warmups' | 'accessories';
  pricePKR: number;
  rating: number;
  reviewsCount: number;
  description: string;
  imageIcon: string;
  badge?: string;
  sizes: string[];
  colors: { name: string; hex: string }[];
  isPinnedMatchMerch?: boolean;
}

export interface Match {
  id: string;
  homeTeam: string;
  awayTeam: string;
  homeScore: number;
  awayScore: number;
  status: 'LIVE' | 'UPCOMING' | 'FINISHED';
  minute?: number;
  stadium: string;
  date: string;
  pinnedProduct: Product;
  timeline: MatchTimelineEvent[];
}

export interface Player {
  id: string;
  name: string;
  number: number;
  position: 'FWD' | 'MID' | 'DEF' | 'GK';
  rating: number;
  age: number;
  marketValuePKR: string;
  weeklyWagePKR: string;
  status: 'Active' | 'On Loan' | 'Transferred' | 'Released';
  avatarColor: string;
}

export const mockPinnedProduct: Product = {
  id: 'prod_match_jersey_2026',
  title: 'NaSCon Match Edition Home Kit 2026',
  category: 'jerseys',
  pricePKR: 4500.0,
  rating: 4.9,
  reviewsCount: 142,
  description: 'Official tournament matchday jersey engineered with AeroVent breathable weave, gold woven crest, and commemorative NaSCon insignia.',
  imageIcon: 'shirt',
  badge: 'Matchday Special',
  sizes: ['S', 'M', 'L', 'XL'],
  colors: [
    { name: 'Midnight Navy & Gold', hex: '#0F1E36' },
    { name: 'Emerald Heritage', hex: '#064E3B' },
    { name: 'Pure Platinum White', hex: '#E2E8F0' },
  ],
  isPinnedMatchMerch: true,
};

export const mockProducts: Product[] = [
  mockPinnedProduct,
  {
    id: 'prod_pro_jacket',
    title: 'Mutators Pro Travel Windbreaker',
    category: 'jackets',
    pricePKR: 4500.0,
    rating: 4.8,
    reviewsCount: 89,
    description: 'Weather-resistant technical outerwear featuring fleece thermal lining, storm zips, and tailored athletic fit.',
    imageIcon: 'jacket',
    badge: 'Best Seller',
    sizes: ['M', 'L', 'XL'],
    colors: [
      { name: 'Stealth Matte Black', hex: '#18181B' },
      { name: 'Slate Graphite', hex: '#334155' },
    ],
  },
  {
    id: 'prod_warmup_kit',
    title: 'Pre-Match Performance Warm-Up Top',
    category: 'warmups',
    pricePKR: 4500.0,
    rating: 4.7,
    reviewsCount: 64,
    description: 'Ultra-light sweat-wicking training shirt worn by starting squad during pre-kickoff warmup sessions.',
    imageIcon: 'fitness',
    badge: 'Squad Wear',
    sizes: ['S', 'M', 'L', 'XL'],
    colors: [
      { name: 'Electric Cyan', hex: '#0284C7' },
      { name: 'Obsidian Black', hex: '#09090B' },
    ],
  },
  {
    id: 'prod_club_hoodie',
    title: 'Championship Supporter Heavyweight Hoodie',
    category: 'jackets',
    pricePKR: 4500.0,
    rating: 4.9,
    reviewsCount: 115,
    description: 'Heavy 420gsm brushed French terry cotton hoodie with embroidered chest badge and kangaroo pocket.',
    imageIcon: 'shirt-outline',
    sizes: ['S', 'M', 'L'],
    colors: [
      { name: 'Heather Smoke Grey', hex: '#64748B' },
      { name: 'Deep Royal Navy', hex: '#1E3A8A' },
    ],
  },
];

export const mockMatches: Match[] = [
  {
    id: 'match_101',
    homeTeam: 'Mutators FC',
    awayTeam: 'Cyber Strikers',
    homeScore: 2,
    awayScore: 1,
    status: 'LIVE',
    minute: 68,
    stadium: 'FAST National Arena',
    date: 'Today, 11:30 AM',
    pinnedProduct: mockPinnedProduct,
    timeline: [
      {
        id: 't1',
        minute: 14,
        type: 'goal',
        player: 'Hamza Khan (#10)',
        team: 'Mutators FC',
        description: 'Spectacular curling strike into top right corner after solo dribble.',
      },
      {
        id: 't2',
        minute: 31,
        type: 'card_yellow',
        player: 'Bilal Ahmed (#4)',
        team: 'Mutators FC',
        description: 'Tactical foul stopping a dangerous counterattack on the halfway line.',
      },
      {
        id: 't3',
        minute: 44,
        type: 'goal',
        player: 'Rayyan Mirza (#9)',
        team: 'Cyber Strikers',
        description: 'Header from a set-piece corner kick.',
      },
      {
        id: 't4',
        minute: 59,
        type: 'goal',
        player: 'Zayn Malik (#8)',
        team: 'Mutators FC',
        description: 'Pounced on loose rebound inside the six-yard box to restore lead!',
      },
      {
        id: 't5',
        minute: 65,
        type: 'sub',
        player: 'Usman Tariq (#7) IN ⇄ Ayan Raza (#19) OUT',
        team: 'Mutators FC',
        description: 'Fresh legs brought on wing to press defensive lines.',
      },
    ],
  },
  {
    id: 'match_102',
    homeTeam: 'FAST Titans',
    awayTeam: 'Lahore Dynamos',
    homeScore: 0,
    awayScore: 0,
    status: 'UPCOMING',
    stadium: 'Jinnah Sports Complex',
    date: 'Today, 2:00 PM',
    pinnedProduct: mockProducts[1],
    timeline: [],
  },
  {
    id: 'match_103',
    homeTeam: 'Rawalpindi Vipers',
    awayTeam: 'Islamabad United FC',
    homeScore: 3,
    awayScore: 2,
    status: 'FINISHED',
    stadium: 'KRL Stadium',
    date: 'Yesterday',
    pinnedProduct: mockProducts[2],
    timeline: [],
  },
];

export const mockStandings: StandingsEntry[] = [
  {
    rank: 1,
    team: 'Mutators FC',
    shortName: 'MUT',
    played: 14,
    won: 11,
    drawn: 2,
    lost: 1,
    gf: 34,
    ga: 12,
    gd: 22,
    points: 35,
    form: ['W', 'W', 'W', 'D', 'W'],
    isCurrentTeam: true,
  },
  {
    rank: 2,
    team: 'Cyber Strikers',
    shortName: 'CYS',
    played: 14,
    won: 9,
    drawn: 3,
    lost: 2,
    gf: 28,
    ga: 15,
    gd: 13,
    points: 30,
    form: ['W', 'L', 'W', 'W', 'D'],
  },
  {
    rank: 3,
    team: 'FAST Titans',
    shortName: 'FTN',
    played: 14,
    won: 8,
    drawn: 4,
    lost: 2,
    gf: 25,
    ga: 14,
    gd: 11,
    points: 28,
    form: ['D', 'W', 'W', 'D', 'W'],
  },
  {
    rank: 4,
    team: 'Islamabad United FC',
    shortName: 'ISU',
    played: 14,
    won: 7,
    drawn: 2,
    lost: 5,
    gf: 22,
    ga: 19,
    gd: 3,
    points: 23,
    form: ['L', 'W', 'L', 'W', 'W'],
  },
  {
    rank: 5,
    team: 'Lahore Dynamos',
    shortName: 'LHD',
    played: 14,
    won: 5,
    drawn: 4,
    lost: 5,
    gf: 18,
    ga: 20,
    gd: -2,
    points: 19,
    form: ['W', 'D', 'L', 'D', 'L'],
  },
  {
    rank: 6,
    team: 'Rawalpindi Vipers',
    shortName: 'RPV',
    played: 14,
    won: 3,
    drawn: 3,
    lost: 8,
    gf: 14,
    ga: 27,
    gd: -13,
    points: 12,
    form: ['L', 'L', 'W', 'L', 'L'],
  },
];

export const mockRoster: Player[] = [
  {
    id: 'ply_10',
    name: 'Hamza Khan',
    number: 10,
    position: 'FWD',
    rating: 89,
    age: 23,
    marketValuePKR: 'PKR 18.5M',
    weeklyWagePKR: 'PKR 250,000',
    status: 'Active',
    avatarColor: '#2563EB',
  },
  {
    id: 'ply_8',
    name: 'Zayn Malik',
    number: 8,
    position: 'MID',
    rating: 87,
    age: 25,
    marketValuePKR: 'PKR 14.0M',
    weeklyWagePKR: 'PKR 210,000',
    status: 'Active',
    avatarColor: '#7C3AED',
  },
  {
    id: 'ply_4',
    name: 'Bilal Ahmed',
    number: 4,
    position: 'DEF',
    rating: 85,
    age: 26,
    marketValuePKR: 'PKR 10.2M',
    weeklyWagePKR: 'PKR 180,000',
    status: 'Active',
    avatarColor: '#059669',
  },
  {
    id: 'ply_1',
    name: 'Saad Farooq',
    number: 1,
    position: 'GK',
    rating: 86,
    age: 27,
    marketValuePKR: 'PKR 9.5M',
    weeklyWagePKR: 'PKR 175,000',
    status: 'Active',
    avatarColor: '#D97706',
  },
  {
    id: 'ply_7',
    name: 'Usman Tariq',
    number: 7,
    position: 'FWD',
    rating: 82,
    age: 21,
    marketValuePKR: 'PKR 7.8M',
    weeklyWagePKR: 'PKR 120,000',
    status: 'Active',
    avatarColor: '#DC2626',
  },
  {
    id: 'ply_19',
    name: 'Ayan Raza',
    number: 19,
    position: 'MID',
    rating: 76,
    age: 19,
    marketValuePKR: 'PKR 3.4M',
    weeklyWagePKR: 'PKR 65,000',
    status: 'Active',
    avatarColor: '#4F46E5',
  },
];
