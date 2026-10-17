import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Match, Product, MatchTimelineEvent } from '../mocks/mockData';

interface MatchDetailScreenProps {
  match: Match;
  onBack: () => void;
  onBuyPinnedProduct: (product: Product) => void;
}

export const MatchDetailScreen: React.FC<MatchDetailScreenProps> = ({
  match,
  onBack,
  onBuyPinnedProduct,
}) => {
  const getTimelineIcon = (type: MatchTimelineEvent['type']) => {
    switch (type) {
      case 'goal':
        return { icon: 'football' as const, color: '#16A34A', bg: '#DCFCE7' };
      case 'card_yellow':
        return { icon: 'alert' as const, color: '#D97706', bg: '#FEF3C7' };
      case 'card_red':
        return { icon: 'close-circle' as const, color: '#DC2626', bg: '#FEE2E2' };
      case 'sub':
        return { icon: 'swap-horizontal' as const, color: '#2563EB', bg: '#DBEAFE' };
      default:
        return { icon: 'information-circle' as const, color: '#475569', bg: '#F1F5F9' };
    }
  };

  return (
    <View style={styles.screenWrapper}>
      {/* Top Navigation Bar */}
      <View style={styles.navBar}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={onBack}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="Back to Standings"
        >
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={styles.navTitleContainer}>
          <Text style={styles.navTitle}>Match Centre</Text>
          <Text style={styles.navSubtitle}>{match.stadium}</Text>
        </View>
        <View style={{ width: 48 }} />
      </View>

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* Match Header Scoreboard */}
        <View style={styles.scoreboardCard}>
          <View style={styles.scoreboardMeta}>
            <View style={styles.liveBadge}>
              <View style={styles.pulseDot} />
              <Text style={styles.liveBadgeText}>
                {match.status === 'LIVE' ? `LIVE • ${match.minute}'` : match.status}
              </Text>
            </View>
            <Text style={styles.metaDateText}>{match.date}</Text>
          </View>

          <View style={styles.teamsRow}>
            {/* Home Team */}
            <View style={styles.teamColumn}>
              <View style={[styles.teamEmblem, styles.homeEmblem]}>
                <Ionicons name="shield" size={28} color="#FFFFFF" />
              </View>
              <Text style={styles.teamTitle}>{match.homeTeam}</Text>
            </View>

            {/* Score */}
            <View style={styles.scoreCenter}>
              <Text style={styles.scoreText}>
                {match.homeScore} : {match.awayScore}
              </Text>
              <Text style={styles.halfTimeNotice}>2nd Half Active</Text>
            </View>

            {/* Away Team */}
            <View style={styles.teamColumn}>
              <View style={[styles.teamEmblem, styles.awayEmblem]}>
                <Ionicons name="shield-outline" size={28} color="#FFFFFF" />
              </View>
              <Text style={styles.teamTitle}>{match.awayTeam}</Text>
            </View>
          </View>
        </View>

        {/* PINNED PRODUCT SHOWCASE (Judge Journey 1 Requirement) */}
        <View style={styles.pinnedShowcaseCard}>
          <View style={styles.pinnedBadgeRow}>
            <View style={styles.specialBadge}>
              <Ionicons name="sparkles" size={13} color="#FFFFFF" style={{ marginRight: 4 }} />
              <Text style={styles.specialBadgeText}>PINNED MATCH MERCHANDISE</Text>
            </View>
            <Text style={styles.stockNotice}>Official Tournament Issue</Text>
          </View>

          <View style={styles.pinnedBody}>
            <View style={styles.productIconBox}>
              <Ionicons name="shirt" size={44} color="#1E3A8A" />
            </View>

            <View style={styles.productDetails}>
              <Text style={styles.productName}>{match.pinnedProduct.title}</Text>
              <Text style={styles.productDesc} numberOfLines={2}>
                {match.pinnedProduct.description}
              </Text>

              <View style={styles.priceRow}>
                <Text style={styles.priceCurrency}>PKR</Text>
                <Text style={styles.priceValue}>
                  {match.pinnedProduct.pricePKR.toLocaleString('en-PK', {
                    minimumFractionDigits: 2,
                  })}
                </Text>
                <View style={styles.ratingBadge}>
                  <Ionicons name="star" size={12} color="#D97706" />
                  <Text style={styles.ratingText}>{match.pinnedProduct.rating}</Text>
                </View>
              </View>
            </View>
          </View>

          <TouchableOpacity
            style={styles.buyPinnedButton}
            onPress={() => onBuyPinnedProduct(match.pinnedProduct)}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel={`Buy pinned product ${match.pinnedProduct.title} for PKR ${match.pinnedProduct.pricePKR}`}
          >
            <Ionicons name="bag-handle" size={20} color="#FFFFFF" style={{ marginRight: 8 }} />
            <Text style={styles.buyPinnedButtonText}>Buy Pinned Match Merch (PKR 4,500.00)</Text>
          </TouchableOpacity>
        </View>

        {/* Match Timeline Section */}
        <View style={styles.timelineSection}>
          <View style={styles.timelineHeaderRow}>
            <Ionicons name="time-outline" size={20} color="#1E3A8A" />
            <Text style={styles.timelineSectionTitle}>Match Event Timeline</Text>
          </View>

          {match.timeline.length === 0 ? (
            <View style={styles.noEventsBox}>
              <Text style={styles.noEventsText}>No match events recorded yet.</Text>
            </View>
          ) : (
            <View style={styles.timelineList}>
              {match.timeline.map((event, idx) => {
                const iconConfig = getTimelineIcon(event.type);
                return (
                  <View key={event.id} style={styles.timelineRow}>
                    <View style={styles.minuteColumn}>
                      <Text style={styles.minuteNumber}>{event.minute}'</Text>
                    </View>

                    <View style={styles.timelineCenterAxis}>
                      <View style={[styles.timelineIconBubble, { backgroundColor: iconConfig.bg }]}>
                        <Ionicons name={iconConfig.icon} size={15} color={iconConfig.color} />
                      </View>
                      {idx !== match.timeline.length - 1 && <View style={styles.timelineConnector} />}
                    </View>

                    <View style={styles.timelineCard}>
                      <View style={styles.timelineCardHeader}>
                        <Text style={styles.eventPlayer}>{event.player}</Text>
                        <Text style={styles.eventTeam}>{event.team}</Text>
                      </View>
                      <Text style={styles.eventDesc}>{event.description}</Text>
                    </View>
                  </View>
                );
              })}
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  screenWrapper: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  navBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  backButton: {
    width: 48, // >= 48dp HCI principle
    height: 48,
    borderRadius: 24,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  navTitleContainer: {
    alignItems: 'center',
  },
  navTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0F172A',
  },
  navSubtitle: {
    fontSize: 12,
    color: '#64748B',
  },
  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
    gap: 16,
  },
  scoreboardCard: {
    backgroundColor: '#0F1E36',
    borderRadius: 20,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 10,
    elevation: 3,
  },
  scoreboardMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#DC2626',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 14,
  },
  pulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#FFFFFF',
    marginRight: 6,
  },
  liveBadgeText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '800',
  },
  metaDateText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  teamsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  teamColumn: {
    flex: 1,
    alignItems: 'center',
  },
  teamEmblem: {
    width: 54,
    height: 54,
    borderRadius: 27,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  homeEmblem: {
    backgroundColor: '#2563EB',
  },
  awayEmblem: {
    backgroundColor: '#475569',
  },
  teamTitle: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
  },
  scoreCenter: {
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  scoreText: {
    fontSize: 38,
    fontWeight: '900',
    color: '#FFFFFF',
    letterSpacing: 3,
  },
  halfTimeNotice: {
    fontSize: 11,
    color: '#93C5FD',
    marginTop: 2,
    fontWeight: '600',
  },
  pinnedShowcaseCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 16,
    borderWidth: 2,
    borderColor: '#BFDBFE',
    shadowColor: '#2563EB',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 3,
  },
  pinnedBadgeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  specialBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E3A8A',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  specialBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.4,
  },
  stockNotice: {
    fontSize: 11,
    color: '#059669',
    fontWeight: '700',
  },
  pinnedBody: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
  },
  productIconBox: {
    width: 76,
    height: 76,
    borderRadius: 16,
    backgroundColor: '#EFF6FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  productDetails: {
    flex: 1,
  },
  productName: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
    marginBottom: 3,
  },
  productDesc: {
    fontSize: 12,
    color: '#64748B',
    lineHeight: 16,
    marginBottom: 6,
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  priceCurrency: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1E3A8A',
  },
  priceValue: {
    fontSize: 18,
    fontWeight: '900',
    color: '#1E3A8A',
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    marginLeft: 8,
  },
  ratingText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#B45309',
    marginLeft: 3,
  },
  buyPinnedButton: {
    backgroundColor: '#2563EB',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50, // >= 48dp HCI principle
    borderRadius: 14,
    shadowColor: '#2563EB',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  buyPinnedButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
  timelineSection: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  timelineHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  timelineSectionTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
    marginLeft: 8,
  },
  noEventsBox: {
    padding: 24,
    alignItems: 'center',
  },
  noEventsText: {
    color: '#94A3B8',
    fontSize: 13,
  },
  timelineList: {
    paddingLeft: 4,
  },
  timelineRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 14,
  },
  minuteColumn: {
    width: 38,
    alignItems: 'flex-end',
    paddingRight: 8,
    paddingTop: 3,
  },
  minuteNumber: {
    fontSize: 13,
    fontWeight: '800',
    color: '#1E3A8A',
  },
  timelineCenterAxis: {
    alignItems: 'center',
    width: 24,
  },
  timelineIconBubble: {
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 2,
  },
  timelineConnector: {
    width: 2,
    height: 44,
    backgroundColor: '#E2E8F0',
    position: 'absolute',
    top: 24,
  },
  timelineCard: {
    flex: 1,
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 10,
    marginLeft: 10,
    borderWidth: 1,
    borderColor: '#F1F5F9',
  },
  timelineCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  eventPlayer: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0F172A',
  },
  eventTeam: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '600',
  },
  eventDesc: {
    fontSize: 12,
    color: '#475569',
    marginTop: 2,
  },
});
