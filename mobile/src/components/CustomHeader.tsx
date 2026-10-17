import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useConfigStore } from '../store/configStore';

interface CustomHeaderProps {
  title: string;
  subtitle?: string;
  rightAction?: {
    icon: keyof typeof Ionicons.glyphMap;
    label: string;
    onPress: () => void;
  };
}

export const CustomHeader: React.FC<CustomHeaderProps> = ({
  title,
  subtitle,
  rightAction,
}) => {
  const { useMock, serverUrl } = useConfigStore();

  return (
    <View style={styles.headerContainer}>
      <View style={styles.topRow}>
        <View style={styles.brandRow}>
          <View style={styles.badgeShield}>
            <Ionicons name="shield-checkmark" size={18} color="#FFFFFF" />
          </View>
          <View>
            <Text style={styles.brandText}>MUTATORS FC</Text>
            <Text style={styles.competitionText}>NaSCon '26 Official App</Text>
          </View>
        </View>

        <View style={styles.rightGroup}>
          <View style={[styles.modePill, useMock ? styles.mockPill : styles.livePill]}>
            <View style={[styles.statusDot, useMock ? styles.mockDot : styles.liveDot]} />
            <Text style={[styles.modeText, useMock ? styles.mockText : styles.liveText]}>
              {useMock ? 'MOCK MODE' : 'LIVE API'}
            </Text>
          </View>

          {rightAction && (
            <TouchableOpacity
              style={styles.iconButton}
              onPress={rightAction.onPress}
              accessibilityRole="button"
              accessibilityLabel={rightAction.label}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Ionicons name={rightAction.icon} size={22} color="#0F172A" />
            </TouchableOpacity>
          )}
        </View>
      </View>

      <View style={styles.titleContainer}>
        <Text style={styles.pageTitle}>{title}</Text>
        {subtitle && <Text style={styles.pageSubtitle}>{subtitle}</Text>}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  headerContainer: {
    backgroundColor: '#FFFFFF',
    paddingTop: 16,
    paddingBottom: 14,
    paddingHorizontal: 18,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  badgeShield: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#1E3A8A',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  brandText: {
    fontSize: 13,
    fontWeight: '800',
    color: '#1E3A8A',
    letterSpacing: 0.5,
  },
  competitionText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#64748B',
  },
  rightGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  modePill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  mockPill: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#BFDBFE',
  },
  livePill: {
    backgroundColor: '#ECFDF5',
    borderWidth: 1,
    borderColor: '#A7F3D0',
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 5,
  },
  mockDot: {
    backgroundColor: '#2563EB',
  },
  liveDot: {
    backgroundColor: '#059669',
  },
  modeText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  mockText: {
    color: '#1D4ED8',
  },
  liveText: {
    color: '#047857',
  },
  iconButton: {
    width: 48, // >= 48dp HCI principle
    height: 48,
    borderRadius: 24,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  titleContainer: {
    marginTop: 4,
  },
  pageTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#0F172A',
    letterSpacing: -0.3,
  },
  pageSubtitle: {
    fontSize: 13,
    color: '#64748B',
    marginTop: 2,
  },
});
