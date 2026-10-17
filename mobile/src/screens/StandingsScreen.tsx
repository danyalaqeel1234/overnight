import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CustomHeader } from '../components/CustomHeader';
import { LoadingState } from '../components/LoadingState';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { mockStandings, mockMatches, Match, StandingsEntry } from '../mocks/mockData';

interface StandingsScreenProps {
  onSelectMatch: (match: Match) => void;
  onOpenSettings: () => void;
}

export const StandingsScreen: React.FC<StandingsScreenProps> = ({
  onSelectMatch,
  onOpenSettings,
}) => {
  const [standings, setStandings] = useState<StandingsEntry[]>(mockStandings);
  const [matches, setMatches] = useState<Match[]>(mockMatches);
  const [isLoading, setIsLoading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [activeTab, setActiveTab] = useState<'table' | 'matches'>('table');

  const handleRefresh = async () => {
    setIsLoading(true);
    setIsError(false);
    setTimeout(() => {
      setStandings(mockStandings);
      setMatches(mockMatches);
      setIsLoading(false);
    }, 400);
  };

  if (isLoading && standings.length === 0) {
    return <LoadingState message="Fetching official league table and fixtures..." />;
  }

  if (isError) {
    return (
      <View style={styles.screenWrapper}>
        <CustomHeader
          title="League Standings"
          subtitle="NaSCon '26 Premier Division"
          rightAction={{ icon: 'settings-outline', label: 'Settings', onPress: onOpenSettings }}
        />
        <ErrorState
          title="Could Not Load Standings"
          message="Unable to sync with the tournament scoring service. Tap below to refresh."
          onRetry={handleRefresh}
        />
      </View>
    );
  }

  const liveMatch = matches.find(m => m.status === 'LIVE');

  return (
    <View style={styles.screenWrapper}>
      <CustomHeader
        title="Standings & Matches"
        subtitle="NaSCon '26 Premier Division"
        rightAction={{ icon: 'settings-outline', label: 'Settings', onPress: onOpenSettings }}
      />

      <ScrollView
        style={styles.scrollContent}
        contentContainerStyle={styles.scrollContainer}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={handleRefresh} colors={['#2563EB']} />
        }
      >
        {/* Live Match Hero Banner */}
        {liveMatch && (
          <View style={styles.heroSection}>
            <View style={styles.heroHeader}>
              <View style={styles.liveIndicator}>
                <View style={styles.livePulseDot} />
                <Text style={styles.liveText}>LIVE NOW • {liveMatch.minute}'</Text>
              </View>
              <Text style={styles.venueText}>{liveMatch.stadium}</Text>
            </View>

            <TouchableOpacity
              style={styles.liveMatchCard}
              onPress={() => onSelectMatch(liveMatch)}
              activeOpacity={0.88}
              accessibilityRole="button"
              accessibilityLabel={`View live match between ${liveMatch.homeTeam} and ${liveMatch.awayTeam}`}
            >
              <View style={styles.scoreRow}>
                <View style={styles.teamCol}>
                  <View style={[styles.teamShield, styles.teamHome]}>
                    <Text style={styles.teamInitials}>MUT</Text>
                  </View>
                  <Text style={styles.teamNameText} numberOfLines={1}>
                    {liveMatch.homeTeam}
                  </Text>
                </View>

                <View style={styles.scoreDisplay}>
                  <Text style={styles.scoreNumber}>
                    {liveMatch.homeScore} : {liveMatch.awayScore}
                  </Text>
                  <Text style={styles.matchStatusBadge}>TAP FOR TIMELINE & MERCH</Text>
                </View>

                <View style={styles.teamCol}>
                  <View style={[styles.teamShield, styles.teamAway]}>
                    <Text style={styles.teamInitials}>CYS</Text>
                  </View>
                  <Text style={styles.teamNameText} numberOfLines={1}>
                    {liveMatch.awayTeam}
                  </Text>
                </View>
              </View>

              <View style={styles.cardFooterNotice}>
                <Ionicons name="shirt-outline" size={16} color="#2563EB" />
                <Text style={styles.cardFooterText}>
                  Pinned Apparel: {liveMatch.pinnedProduct.title} (PKR 4500)
                </Text>
                <Ionicons name="chevron-forward" size={16} color="#64748B" />
              </View>
            </TouchableOpacity>
          </View>
        )}

        {/* Segmented Control */}
        <View style={styles.segmentedControl}>
          <TouchableOpacity
            style={[styles.segmentButton, activeTab === 'table' && styles.segmentButtonActive]}
            onPress={() => setActiveTab('table')}
            accessibilityRole="tab"
            accessibilityLabel="Show Table"
          >
            <Ionicons
              name="trophy-outline"
              size={18}
              color={activeTab === 'table' ? '#FFFFFF' : '#475569'}
              style={{ marginRight: 6 }}
            />
            <Text
              style={[styles.segmentButtonText, activeTab === 'table' && styles.segmentButtonTextActive]}
            >
              Standings Table
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.segmentButton, activeTab === 'matches' && styles.segmentButtonActive]}
            onPress={() => setActiveTab('matches')}
            accessibilityRole="tab"
            accessibilityLabel="Show Fixtures"
          >
            <Ionicons
              name="calendar-outline"
              size={18}
              color={activeTab === 'matches' ? '#FFFFFF' : '#475569'}
              style={{ marginRight: 6 }}
            />
            <Text
              style={[styles.segmentButtonText, activeTab === 'matches' && styles.segmentButtonTextActive]}
            >
              All Matches ({matches.length})
            </Text>
          </TouchableOpacity>
        </View>

        {activeTab === 'table' ? (
          /* Table View */
          <View style={styles.tableCard}>
            <View style={styles.tableHeaderRow}>
              <Text style={[styles.tableHeadCol, styles.colRank]}>#</Text>
              <Text style={[styles.tableHeadCol, styles.colTeam]}>Club</Text>
              <Text style={[styles.tableHeadCol, styles.colStat]}>P</Text>
              <Text style={[styles.tableHeadCol, styles.colStat]}>W</Text>
              <Text style={[styles.tableHeadCol, styles.colStat]}>D</Text>
              <Text style={[styles.tableHeadCol, styles.colStat]}>L</Text>
              <Text style={[styles.tableHeadCol, styles.colStat]}>GD</Text>
              <Text style={[styles.tableHeadCol, styles.colPts]}>Pts</Text>
            </View>

            {standings.map(entry => (
              <View
                key={entry.rank}
                style={[
                  styles.tableRow,
                  entry.isCurrentTeam && styles.highlightCurrentTeamRow,
                ]}
              >
                <View style={[styles.tableCell, styles.colRank]}>
                  <View
                    style={[
                      styles.rankCircle,
                      entry.rank <= 3 ? styles.topThreeRank : styles.otherRank,
                      entry.isCurrentTeam && styles.currentTeamRank,
                    ]}
                  >
                    <Text
                      style={[
                        styles.rankText,
                        entry.rank <= 3 && styles.topThreeRankText,
                        entry.isCurrentTeam && styles.currentTeamRankText,
                      ]}
                    >
                      {entry.rank}
                    </Text>
                  </View>
                </View>

                <View style={[styles.tableCell, styles.colTeam]}>
                  <Text
                    style={[
                      styles.teamCellName,
                      entry.isCurrentTeam && styles.currentTeamCellText,
                    ]}
                    numberOfLines={1}
                  >
                    {entry.team}
                  </Text>
                  {entry.isCurrentTeam && (
                    <View style={styles.ourTeamTag}>
                      <Text style={styles.ourTeamTagText}>Our Squad</Text>
                    </View>
                  )}
                </View>

                <Text style={[styles.tableCellText, styles.colStat]}>{entry.played}</Text>
                <Text style={[styles.tableCellText, styles.colStat]}>{entry.won}</Text>
                <Text style={[styles.tableCellText, styles.colStat]}>{entry.drawn}</Text>
                <Text style={[styles.tableCellText, styles.colStat]}>{entry.lost}</Text>
                <Text
                  style={[
                    styles.tableCellText,
                    styles.colStat,
                    entry.gd > 0 ? styles.positiveGd : entry.gd < 0 ? styles.negativeGd : null,
                  ]}
                >
                  {entry.gd > 0 ? `+${entry.gd}` : entry.gd}
                </Text>
                <Text style={[styles.tableCellText, styles.colPts, styles.pointsCell]}>
                  {entry.points}
                </Text>
              </View>
            ))}

            <View style={styles.tableLegend}>
              <View style={styles.legendItem}>
                <View style={[styles.legendBox, { backgroundColor: '#1E3A8A' }]} />
                <Text style={styles.legendText}>Champions League Qualification (Top 3)</Text>
              </View>
            </View>
          </View>
        ) : (
          /* Matches List */
          <View style={styles.matchesListContainer}>
            {matches.map(m => (
              <TouchableOpacity
                key={m.id}
                style={styles.matchItemCard}
                onPress={() => onSelectMatch(m)}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel={`View match ${m.homeTeam} vs ${m.awayTeam}`}
              >
                <View style={styles.matchItemHeader}>
                  <View style={styles.matchStatusRow}>
                    {m.status === 'LIVE' && <View style={styles.liveSmallDot} />}
                    <Text
                      style={[
                        styles.matchItemStatus,
                        m.status === 'LIVE'
                          ? styles.statusLive
                          : m.status === 'UPCOMING'
                          ? styles.statusUpcoming
                          : styles.statusFinished,
                      ]}
                    >
                      {m.status === 'LIVE' ? `LIVE • ${m.minute}'` : m.status}
                    </Text>
                  </View>
                  <Text style={styles.matchItemDate}>{m.date}</Text>
                </View>

                <View style={styles.matchItemTeamsRow}>
                  <View style={styles.teamNameSide}>
                    <Text style={styles.matchItemTeamName}>{m.homeTeam}</Text>
                    <Text style={styles.matchItemScore}>
                      {m.status !== 'UPCOMING' ? m.homeScore : '-'}
                    </Text>
                  </View>

                  <Text style={styles.vsDivider}>VS</Text>

                  <View style={styles.teamNameSide}>
                    <Text style={styles.matchItemScore}>
                      {m.status !== 'UPCOMING' ? m.awayScore : '-'}
                    </Text>
                    <Text style={[styles.matchItemTeamName, { textAlign: 'right' }]}>
                      {m.awayTeam}
                    </Text>
                  </View>
                </View>

                <View style={styles.matchItemBottomBar}>
                  <View style={styles.venueRow}>
                    <Ionicons name="location-outline" size={14} color="#64748B" />
                    <Text style={styles.matchVenueText}>{m.stadium}</Text>
                  </View>
                  <View style={styles.pinnedNotice}>
                    <Ionicons name="pricetag-outline" size={12} color="#2563EB" />
                    <Text style={styles.pinnedNoticeText}>Merch Pinned</Text>
                  </View>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  screenWrapper: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollContent: {
    flex: 1,
  },
  scrollContainer: {
    paddingBottom: 36,
  },
  heroSection: {
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 6,
  },
  heroHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  liveIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#FEE2E2',
  },
  livePulseDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#DC2626',
    marginRight: 6,
  },
  liveText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#DC2626',
    letterSpacing: 0.5,
  },
  venueText: {
    fontSize: 12,
    color: '#64748B',
    fontWeight: '500',
  },
  liveMatchCard: {
    backgroundColor: '#0F1E36',
    borderRadius: 18,
    padding: 18,
    shadowColor: '#0F1E36',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 4,
  },
  scoreRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  teamCol: {
    flex: 1,
    alignItems: 'center',
  },
  teamShield: {
    width: 48,
    height: 48,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 6,
  },
  teamHome: {
    backgroundColor: '#2563EB',
  },
  teamAway: {
    backgroundColor: '#475569',
  },
  teamInitials: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 14,
  },
  teamNameText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
  scoreDisplay: {
    alignItems: 'center',
    paddingHorizontal: 10,
  },
  scoreNumber: {
    fontSize: 32,
    fontWeight: '900',
    color: '#FFFFFF',
    letterSpacing: 2,
  },
  matchStatusBadge: {
    fontSize: 9,
    fontWeight: '800',
    color: '#93C5FD',
    marginTop: 4,
    letterSpacing: 0.8,
  },
  cardFooterNotice: {
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.12)',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cardFooterText: {
    flex: 1,
    marginHorizontal: 8,
    color: '#E2E8F0',
    fontSize: 12,
    fontWeight: '600',
  },
  segmentedControl: {
    flexDirection: 'row',
    backgroundColor: '#E2E8F0',
    borderRadius: 12,
    padding: 4,
    marginHorizontal: 16,
    marginVertical: 14,
  },
  segmentButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48, // >= 48dp HCI principle
    borderRadius: 9,
  },
  segmentButtonActive: {
    backgroundColor: '#1E3A8A',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  segmentButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#475569',
  },
  segmentButtonTextActive: {
    color: '#FFFFFF',
  },
  tableCard: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    overflow: 'hidden',
  },
  tableHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F1F5F9',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  tableHeadCol: {
    fontSize: 11,
    fontWeight: '800',
    color: '#64748B',
    textAlign: 'center',
  },
  colRank: {
    width: 32,
    textAlign: 'center',
  },
  colTeam: {
    flex: 1,
    textAlign: 'left',
    paddingLeft: 6,
  },
  colStat: {
    width: 28,
  },
  colPts: {
    width: 36,
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 13,
    paddingHorizontal: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
    minHeight: 48, // >= 48dp touchable row
  },
  highlightCurrentTeamRow: {
    backgroundColor: '#EFF6FF',
    borderLeftWidth: 4,
    borderLeftColor: '#2563EB',
  },
  tableCell: {
    justifyContent: 'center',
  },
  rankCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  topThreeRank: {
    backgroundColor: '#DBEAFE',
  },
  otherRank: {
    backgroundColor: '#F1F5F9',
  },
  currentTeamRank: {
    backgroundColor: '#2563EB',
  },
  rankText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#475569',
  },
  topThreeRankText: {
    color: '#1D4ED8',
  },
  currentTeamRankText: {
    color: '#FFFFFF',
  },
  teamCellName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0F172A',
  },
  currentTeamCellText: {
    fontWeight: '800',
    color: '#1D4ED8',
  },
  ourTeamTag: {
    alignSelf: 'flex-start',
    backgroundColor: '#BFDBFE',
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 1,
    marginTop: 2,
  },
  ourTeamTagText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#1E40AF',
  },
  tableCellText: {
    fontSize: 13,
    color: '#334155',
    textAlign: 'center',
    fontWeight: '500',
  },
  positiveGd: {
    color: '#059669',
    fontWeight: '700',
  },
  negativeGd: {
    color: '#DC2626',
    fontWeight: '700',
  },
  pointsCell: {
    fontWeight: '800',
    fontSize: 14,
    color: '#0F172A',
  },
  tableLegend: {
    padding: 12,
    backgroundColor: '#F8FAFC',
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  legendBox: {
    width: 10,
    height: 10,
    borderRadius: 2,
    marginRight: 8,
  },
  legendText: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '600',
  },
  matchesListContainer: {
    paddingHorizontal: 16,
    gap: 12,
  },
  matchItemCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    minHeight: 110,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  matchItemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  matchStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  liveSmallDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#DC2626',
    marginRight: 5,
  },
  matchItemStatus: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  statusLive: {
    color: '#DC2626',
  },
  statusUpcoming: {
    color: '#2563EB',
  },
  statusFinished: {
    color: '#64748B',
  },
  matchItemDate: {
    fontSize: 12,
    color: '#64748B',
    fontWeight: '500',
  },
  matchItemTeamsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  teamNameSide: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  matchItemTeamName: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0F172A',
    flex: 1,
  },
  matchItemScore: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0F172A',
    paddingHorizontal: 8,
  },
  vsDivider: {
    fontSize: 11,
    fontWeight: '800',
    color: '#94A3B8',
    paddingHorizontal: 10,
  },
  matchItemBottomBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#F1F5F9',
  },
  venueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  matchVenueText: {
    fontSize: 11,
    color: '#64748B',
    marginLeft: 4,
  },
  pinnedNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EFF6FF',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  pinnedNoticeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#2563EB',
    marginLeft: 4,
  },
});
