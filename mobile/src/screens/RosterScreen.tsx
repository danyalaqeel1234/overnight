import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CustomHeader } from '../components/CustomHeader';
import { useRosterStore } from '../store/rosterStore';
import { Player } from '../mocks/mockData';
import { EmptyState } from '../components/EmptyState';

interface RosterScreenProps {
  onOpenSettings: () => void;
}

export const RosterScreen: React.FC<RosterScreenProps> = ({ onOpenSettings }) => {
  const {
    players,
    transferPlayer,
    loanPlayer,
    releasePlayer,
    resetRoster,
    lastActionMessage,
    clearActionMessage,
  } = useRosterStore();

  const [filter, setFilter] = useState<'All' | 'Active' | 'On Loan' | 'Transferred'>('All');
  const [selectedPlayerForAction, setSelectedPlayerForAction] = useState<Player | null>(null);
  const [actionType, setActionType] = useState<'transfer' | 'loan' | 'release' | null>(null);
  const [selectedDestination, setSelectedDestination] = useState('Al-Sharjah FC');
  const [loanMonths, setLoanMonths] = useState(6);

  const filteredPlayers = players.filter(p => {
    if (filter === 'All') return true;
    return p.status === filter;
  });

  const getPositionBadgeStyle = (pos: Player['position']) => {
    switch (pos) {
      case 'FWD':
        return { bg: '#FEE2E2', text: '#DC2626' };
      case 'MID':
        return { bg: '#EDE9FE', text: '#7C3AED' };
      case 'DEF':
        return { bg: '#DCFCE7', text: '#16A34A' };
      case 'GK':
        return { bg: '#FEF3C7', text: '#D97706' };
    }
  };

  const getStatusBadgeStyle = (status: Player['status']) => {
    switch (status) {
      case 'Active':
        return { bg: '#DCFCE7', text: '#166534' };
      case 'On Loan':
        return { bg: '#DBEAFE', text: '#1E40AF' };
      case 'Transferred':
        return { bg: '#FEF3C7', text: '#92400E' };
      case 'Released':
        return { bg: '#FEE2E2', text: '#991B1B' };
    }
  };

  const handleOpenAction = (player: Player, type: 'transfer' | 'loan' | 'release') => {
    setSelectedPlayerForAction(player);
    setActionType(type);
  };

  const handleConfirmAction = () => {
    if (!selectedPlayerForAction || !actionType) return;

    if (actionType === 'transfer') {
      transferPlayer(selectedPlayerForAction.id, selectedDestination);
    } else if (actionType === 'loan') {
      loanPlayer(selectedPlayerForAction.id, loanMonths);
    } else if (actionType === 'release') {
      releasePlayer(selectedPlayerForAction.id);
    }

    setSelectedPlayerForAction(null);
    setActionType(null);
  };

  const activeCount = players.filter(p => p.status === 'Active').length;
  const loanCount = players.filter(p => p.status === 'On Loan').length;

  return (
    <View style={styles.screenWrapper}>
      <CustomHeader
        title="Club Roster"
        subtitle="Tactical Squad & Contract Management"
        rightAction={{ icon: 'settings-outline', label: 'Settings', onPress: onOpenSettings }}
      />

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* Squad Metrics Dashboard */}
        <View style={styles.metricsCard}>
          <View style={styles.metricsHeader}>
            <View>
              <Text style={styles.metricsHeading}>Mutators FC Squad</Text>
              <Text style={styles.metricsSubheading}>2025/26 Season Roster</Text>
            </View>
            <TouchableOpacity
              style={styles.resetSquadButton}
              onPress={resetRoster}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel="Reset squad to original roster"
            >
              <Ionicons name="reload" size={14} color="#2563EB" style={{ marginRight: 4 }} />
              <Text style={styles.resetSquadText}>Reset Demo</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.metricsRow}>
            <View style={styles.metricItem}>
              <Text style={styles.metricNumber}>{players.length}</Text>
              <Text style={styles.metricLabel}>Total Squad</Text>
            </View>
            <View style={styles.metricDivider} />
            <View style={styles.metricItem}>
              <Text style={[styles.metricNumber, { color: '#16A34A' }]}>{activeCount}</Text>
              <Text style={styles.metricLabel}>Active</Text>
            </View>
            <View style={styles.metricDivider} />
            <View style={styles.metricItem}>
              <Text style={[styles.metricNumber, { color: '#2563EB' }]}>{loanCount}</Text>
              <Text style={styles.metricLabel}>On Loan</Text>
            </View>
          </View>
        </View>

        {/* Action Notice Alert */}
        {lastActionMessage && (
          <View style={styles.actionNoticeCard}>
            <Ionicons name="checkmark-circle" size={20} color="#16A34A" />
            <Text style={styles.actionNoticeText}>{lastActionMessage}</Text>
            <TouchableOpacity
              onPress={clearActionMessage}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons name="close" size={16} color="#64748B" />
            </TouchableOpacity>
          </View>
        )}

        {/* Filter Pills */}
        <View style={styles.filterBar}>
          {(['All', 'Active', 'On Loan', 'Transferred'] as const).map(f => (
            <TouchableOpacity
              key={f}
              style={[styles.filterPill, filter === f && styles.filterPillActive]}
              onPress={() => setFilter(f)}
              activeOpacity={0.8}
              accessibilityRole="tab"
              accessibilityLabel={`Filter ${f}`}
            >
              <Text style={[styles.filterPillText, filter === f && styles.filterPillTextActive]}>
                {f}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Players List */}
        {filteredPlayers.length === 0 ? (
          <EmptyState
            icon="people-outline"
            title={`No ${filter} Players`}
            description="All players in this category have either been transferred or changed status."
            actionLabel="View All Players"
            onAction={() => setFilter('All')}
          />
        ) : (
          filteredPlayers.map(player => {
            const posStyle = getPositionBadgeStyle(player.position);
            const statusStyle = getStatusBadgeStyle(player.status);
            const isManageable = player.status === 'Active';

            return (
              <View key={player.id} style={styles.playerCard}>
                {/* Player Header Row */}
                <View style={styles.playerTopRow}>
                  <View style={[styles.avatarBox, { backgroundColor: player.avatarColor }]}>
                    <Text style={styles.avatarNumber}>#{player.number}</Text>
                  </View>

                  <View style={styles.playerMainInfo}>
                    <View style={styles.nameAndRatingRow}>
                      <Text style={styles.playerName}>{player.name}</Text>
                      <View style={styles.ratingBadge}>
                        <Text style={styles.ratingNumber}>{player.rating}</Text>
                        <Text style={styles.ratingOvr}>OVR</Text>
                      </View>
                    </View>

                    <View style={styles.badgesRow}>
                      <View style={[styles.badgePill, { backgroundColor: posStyle.bg }]}>
                        <Text style={[styles.badgePillText, { color: posStyle.text }]}>
                          {player.position}
                        </Text>
                      </View>
                      <View style={[styles.badgePill, { backgroundColor: statusStyle.bg }]}>
                        <Text style={[styles.badgePillText, { color: statusStyle.text }]}>
                          {player.status}
                        </Text>
                      </View>
                      <Text style={styles.ageText}>{player.age} yrs</Text>
                    </View>
                  </View>
                </View>

                {/* Market & Contract Details */}
                <View style={styles.contractRow}>
                  <View style={styles.contractCol}>
                    <Text style={styles.contractLabel}>Market Valuation</Text>
                    <Text style={styles.contractValue}>{player.marketValuePKR}</Text>
                  </View>
                  <View style={styles.contractCol}>
                    <Text style={styles.contractLabel}>Wage</Text>
                    <Text style={styles.contractValue}>{player.weeklyWagePKR}/wk</Text>
                  </View>
                </View>

                {/* 3 PRIMARY ACTION BUTTONS (Journey 3 Requirement) */}
                <View style={styles.actionsRow}>
                  {/* TRANSFER BUTTON (>= 48dp touch target) */}
                  <TouchableOpacity
                    style={[
                      styles.actionButton,
                      styles.transferButton,
                      !isManageable && styles.actionButtonDisabled,
                    ]}
                    onPress={() => handleOpenAction(player, 'transfer')}
                    disabled={!isManageable}
                    activeOpacity={0.8}
                    accessibilityRole="button"
                    accessibilityLabel={`Transfer ${player.name}`}
                  >
                    <Ionicons name="swap-horizontal" size={16} color="#FFFFFF" style={{ marginRight: 4 }} />
                    <Text style={styles.actionButtonText}>Transfer</Text>
                  </TouchableOpacity>

                  {/* LOAN BUTTON (>= 48dp touch target) */}
                  <TouchableOpacity
                    style={[
                      styles.actionButton,
                      styles.loanButton,
                      !isManageable && styles.actionButtonDisabled,
                    ]}
                    onPress={() => handleOpenAction(player, 'loan')}
                    disabled={!isManageable}
                    activeOpacity={0.8}
                    accessibilityRole="button"
                    accessibilityLabel={`Loan ${player.name}`}
                  >
                    <Ionicons name="time" size={16} color="#FFFFFF" style={{ marginRight: 4 }} />
                    <Text style={styles.actionButtonText}>Loan</Text>
                  </TouchableOpacity>

                  {/* RELEASE BUTTON (>= 48dp touch target) */}
                  <TouchableOpacity
                    style={[
                      styles.actionButton,
                      styles.releaseButton,
                      player.status === 'Released' && styles.actionButtonDisabled,
                    ]}
                    onPress={() => handleOpenAction(player, 'release')}
                    disabled={player.status === 'Released'}
                    activeOpacity={0.8}
                    accessibilityRole="button"
                    accessibilityLabel={`Release ${player.name}`}
                  >
                    <Ionicons name="trash-outline" size={16} color="#FFFFFF" style={{ marginRight: 4 }} />
                    <Text style={styles.actionButtonText}>Release</Text>
                  </TouchableOpacity>
                </View>
              </View>
            );
          })
        )}
      </ScrollView>

      {/* Interactive Action Confirmation Modal */}
      {selectedPlayerForAction && actionType && (
        <Modal transparent animationType="fade" visible={true}>
          <View style={styles.modalBackdrop}>
            <View style={styles.modalDialogCard}>
              <View style={styles.dialogHeader}>
                <View
                  style={[
                    styles.dialogIconCircle,
                    actionType === 'transfer'
                      ? styles.transferIconBg
                      : actionType === 'loan'
                      ? styles.loanIconBg
                      : styles.releaseIconBg,
                  ]}
                >
                  <Ionicons
                    name={
                      actionType === 'transfer'
                        ? 'swap-horizontal'
                        : actionType === 'loan'
                        ? 'time'
                        : 'alert-circle'
                    }
                    size={26}
                    color="#FFFFFF"
                  />
                </View>
                <Text style={styles.dialogTitle}>
                  {actionType === 'transfer'
                    ? `Transfer ${selectedPlayerForAction.name}`
                    : actionType === 'loan'
                    ? `Loan Out ${selectedPlayerForAction.name}`
                    : `Release ${selectedPlayerForAction.name}?`}
                </Text>
                <Text style={styles.dialogSubtitle}>
                  {actionType === 'transfer'
                    ? `Finalize professional transfer agreement for ${selectedPlayerForAction.marketValuePKR}.`
                    : actionType === 'loan'
                    ? `Dispatch on temporary loan for tournament experience.`
                    : `Terminate contract by mutual agreement. Player becomes a free agent.`}
                </Text>
              </View>

              {/* Transfer Destination Selection */}
              {actionType === 'transfer' && (
                <View style={styles.dialogOptionsBlock}>
                  <Text style={styles.optionsLabel}>Select Destination Club:</Text>
                  {['Al-Sharjah FC', 'Doha Stars', 'Karachi United'].map(club => (
                    <TouchableOpacity
                      key={club}
                      style={[
                        styles.destinationOption,
                        selectedDestination === club && styles.destinationOptionActive,
                      ]}
                      onPress={() => setSelectedDestination(club)}
                    >
                      <Text
                        style={[
                          styles.destinationOptionText,
                          selectedDestination === club && styles.destinationOptionTextActive,
                        ]}
                      >
                        {club}
                      </Text>
                      {selectedDestination === club && (
                        <Ionicons name="checkmark" size={18} color="#2563EB" />
                      )}
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              {/* Loan Duration Selection */}
              {actionType === 'loan' && (
                <View style={styles.dialogOptionsBlock}>
                  <Text style={styles.optionsLabel}>Select Loan Period:</Text>
                  <View style={styles.loanMonthsRow}>
                    {[3, 6, 12].map(m => (
                      <TouchableOpacity
                        key={m}
                        style={[
                          styles.monthOptionButton,
                          loanMonths === m && styles.monthOptionButtonActive,
                        ]}
                        onPress={() => setLoanMonths(m)}
                      >
                        <Text
                          style={[
                            styles.monthOptionText,
                            loanMonths === m && styles.monthOptionTextActive,
                          ]}
                        >
                          {m} Months
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              )}

              {/* Dialog Buttons (>= 48dp touch targets) */}
              <View style={styles.dialogActions}>
                <TouchableOpacity
                  style={styles.cancelDialogButton}
                  onPress={() => {
                    setSelectedPlayerForAction(null);
                    setActionType(null);
                  }}
                  activeOpacity={0.8}
                  accessibilityRole="button"
                  accessibilityLabel="Cancel action"
                >
                  <Text style={styles.cancelDialogButtonText}>Cancel</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.confirmDialogButton,
                    actionType === 'transfer'
                      ? styles.transferConfirmBg
                      : actionType === 'loan'
                      ? styles.loanConfirmBg
                      : styles.releaseConfirmBg,
                  ]}
                  onPress={handleConfirmAction}
                  activeOpacity={0.85}
                  accessibilityRole="button"
                  accessibilityLabel="Confirm action"
                >
                  <Text style={styles.confirmDialogButtonText}>
                    {actionType === 'transfer'
                      ? 'Confirm Transfer'
                      : actionType === 'loan'
                      ? 'Confirm Loan'
                      : 'Confirm Release'}
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  screenWrapper: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
    gap: 14,
  },
  metricsCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  metricsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  metricsHeading: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
  },
  metricsSubheading: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 1,
  },
  resetSquadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EFF6FF',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#BFDBFE',
  },
  resetSquadText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#2563EB',
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#F1F5F9',
  },
  metricItem: {
    alignItems: 'center',
  },
  metricNumber: {
    fontSize: 22,
    fontWeight: '900',
    color: '#0F172A',
  },
  metricLabel: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '600',
    marginTop: 2,
  },
  metricDivider: {
    width: 1,
    height: 30,
    backgroundColor: '#E2E8F0',
  },
  actionNoticeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F0FDF4',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#BBF7D0',
    gap: 8,
  },
  actionNoticeText: {
    flex: 1,
    fontSize: 12,
    fontWeight: '600',
    color: '#166534',
  },
  filterBar: {
    flexDirection: 'row',
    gap: 8,
  },
  filterPill: {
    flex: 1,
    minHeight: 48, // >= 48dp HCI principle
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F1F5F9',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  filterPillActive: {
    backgroundColor: '#1E3A8A',
    borderColor: '#1E3A8A',
  },
  filterPillText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#64748B',
  },
  filterPillTextActive: {
    color: '#FFFFFF',
  },
  playerCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  playerTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  avatarBox: {
    width: 50,
    height: 50,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  avatarNumber: {
    color: '#FFFFFF',
    fontWeight: '900',
    fontSize: 16,
  },
  playerMainInfo: {
    flex: 1,
  },
  nameAndRatingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  playerName: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'baseline',
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  ratingNumber: {
    fontSize: 14,
    fontWeight: '900',
    color: '#92400E',
  },
  ratingOvr: {
    fontSize: 9,
    fontWeight: '800',
    color: '#B45309',
    marginLeft: 3,
  },
  badgesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  badgePill: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  badgePillText: {
    fontSize: 10,
    fontWeight: '800',
  },
  ageText: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '500',
    marginLeft: 2,
  },
  contractRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#F8FAFC',
    padding: 10,
    borderRadius: 10,
    marginBottom: 14,
  },
  contractCol: {
    flex: 1,
  },
  contractLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: '#64748B',
    textTransform: 'uppercase',
  },
  contractValue: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1E293B',
    marginTop: 1,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    minHeight: 48, // >= 48dp HCI principle
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 12,
  },
  transferButton: {
    backgroundColor: '#2563EB',
  },
  loanButton: {
    backgroundColor: '#059669',
  },
  releaseButton: {
    backgroundColor: '#DC2626',
  },
  actionButtonDisabled: {
    opacity: 0.35,
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 12,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalDialogCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 22,
    width: '100%',
    maxWidth: 380,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 8,
  },
  dialogHeader: {
    alignItems: 'center',
    marginBottom: 18,
  },
  dialogIconCircle: {
    width: 58,
    height: 58,
    borderRadius: 29,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  transferIconBg: {
    backgroundColor: '#2563EB',
  },
  loanIconBg: {
    backgroundColor: '#059669',
  },
  releaseIconBg: {
    backgroundColor: '#DC2626',
  },
  dialogTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0F172A',
    textAlign: 'center',
  },
  dialogSubtitle: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    marginTop: 4,
    lineHeight: 18,
  },
  dialogOptionsBlock: {
    marginBottom: 18,
  },
  optionsLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0F172A',
    marginBottom: 8,
  },
  destinationOption: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 6,
  },
  destinationOptionActive: {
    borderColor: '#2563EB',
    backgroundColor: '#EFF6FF',
  },
  destinationOptionText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#334155',
  },
  destinationOptionTextActive: {
    color: '#1E40AF',
    fontWeight: '700',
  },
  loanMonthsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  monthOptionButton: {
    flex: 1,
    minHeight: 48,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  monthOptionButtonActive: {
    borderColor: '#059669',
    backgroundColor: '#ECFDF5',
  },
  monthOptionText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#475569',
  },
  monthOptionTextActive: {
    color: '#047857',
    fontWeight: '700',
  },
  dialogActions: {
    flexDirection: 'row',
    gap: 10,
  },
  cancelDialogButton: {
    flex: 1,
    minHeight: 48, // >= 48dp HCI principle
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 12,
    backgroundColor: '#F1F5F9',
  },
  cancelDialogButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#475569',
  },
  confirmDialogButton: {
    flex: 1.3,
    minHeight: 48, // >= 48dp HCI principle
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 12,
  },
  transferConfirmBg: {
    backgroundColor: '#2563EB',
  },
  loanConfirmBg: {
    backgroundColor: '#059669',
  },
  releaseConfirmBg: {
    backgroundColor: '#DC2626',
  },
  confirmDialogButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
