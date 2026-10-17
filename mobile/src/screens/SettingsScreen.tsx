import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Switch,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useConfigStore } from '../store/configStore';

interface SettingsScreenProps {
  onBack: () => void;
}

export const SettingsScreen: React.FC<SettingsScreenProps> = ({ onBack }) => {
  const {
    serverUrl,
    useMock,
    isPinging,
    pingResult,
    setServerUrl,
    setUseMock,
    testConnection,
    resetToDefaults,
  } = useConfigStore();

  const [inputUrl, setInputUrl] = useState(serverUrl);
  const [saveBanner, setSaveBanner] = useState<string | null>(null);

  const presets = [
    { label: 'Android Emulator', url: 'http://10.0.2.2:8080' },
    { label: 'Laptop 1 LAN (Hotspot)', url: 'http://192.168.1.100:8000' },
    { label: 'Localhost Fallback', url: 'http://localhost:8000' },
  ];

  const handleApplyUrl = () => {
    setServerUrl(inputUrl);
    setSaveBanner('Server address updated successfully.');
    setTimeout(() => setSaveBanner(null), 3000);
  };

  const handleSelectPreset = (url: string) => {
    setInputUrl(url);
    setServerUrl(url);
    setSaveBanner(`Configured to ${url}`);
    setTimeout(() => setSaveBanner(null), 3000);
  };

  return (
    <View style={styles.screenWrapper}>
      {/* Top Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={onBack}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="Back"
        >
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={styles.headerTitleBox}>
          <Text style={styles.headerTitle}>Network Settings</Text>
          <Text style={styles.headerSubtitle}>Server Connectivity & Diagnostics</Text>
        </View>
        <View style={{ width: 48 }} />
      </View>

      <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
        {/* Notification Toast */}
        {saveBanner && (
          <View style={styles.toastBanner}>
            <Ionicons name="checkmark-circle" size={18} color="#16A34A" />
            <Text style={styles.toastText}>{saveBanner}</Text>
          </View>
        )}

        {/* MOCK MODE TOGGLE CARD */}
        <View style={styles.settingCard}>
          <View style={styles.cardHeaderRow}>
            <View style={styles.iconBadgeBlue}>
              <Ionicons name="hardware-chip-outline" size={22} color="#2563EB" />
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>Data Source Mode</Text>
              <Text style={styles.cardSubtitle}>
                Toggle between offline mock contracts and live Laptop 1 backend
              </Text>
            </View>
            <Switch
              value={useMock}
              onValueChange={val => setUseMock(val)}
              trackColor={{ false: '#CBD5E1', true: '#93C5FD' }}
              thumbColor={useMock ? '#2563EB' : '#F1F5F9'}
            />
          </View>

          <View style={[styles.statusBanner, useMock ? styles.mockStatus : styles.liveStatus]}>
            <Ionicons
              name={useMock ? 'shield-checkmark' : 'globe-outline'}
              size={18}
              color={useMock ? '#1D4ED8' : '#047857'}
            />
            <Text style={[styles.statusBannerText, useMock ? styles.mockText : styles.liveText]}>
              {useMock
                ? 'Mock Mode Enabled — 100% resilient offline data layer'
                : 'Live API Mode Enabled — Queries sent to Server URL below'}
            </Text>
          </View>
        </View>

        {/* SERVER URL CONFIGURATION */}
        <View style={styles.settingCard}>
          <View style={styles.cardHeaderRow}>
            <View style={styles.iconBadgeIndigo}>
              <Ionicons name="server-outline" size={22} color="#4F46E5" />
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>Backend Server URL</Text>
              <Text style={styles.cardSubtitle}>
                Target endpoint for competition API endpoints
              </Text>
            </View>
          </View>

          <View style={styles.inputContainer}>
            <TextInput
              style={styles.urlInput}
              value={inputUrl}
              onChangeText={setInputUrl}
              placeholder="http://10.0.2.2:8080"
              placeholderTextColor="#94A3B8"
              autoCapitalize="none"
              autoCorrect={false}
              accessibilityLabel="Backend Server URL input"
            />
            <TouchableOpacity
              style={styles.applyButton}
              onPress={handleApplyUrl}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel="Apply server URL"
            >
              <Text style={styles.applyButtonText}>Apply</Text>
            </TouchableOpacity>
          </View>

          {/* Quick Presets */}
          <Text style={styles.presetsHeading}>Quick Connect Presets:</Text>
          <View style={styles.presetButtonsList}>
            {presets.map(p => (
              <TouchableOpacity
                key={p.url}
                style={[
                  styles.presetButton,
                  serverUrl === p.url && styles.presetButtonActive,
                ]}
                onPress={() => handleSelectPreset(p.url)}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityLabel={`Connect to ${p.label}`}
              >
                <View style={styles.presetTextCol}>
                  <Text
                    style={[
                      styles.presetLabel,
                      serverUrl === p.url && styles.presetLabelActive,
                    ]}
                  >
                    {p.label}
                  </Text>
                  <Text style={styles.presetUrl}>{p.url}</Text>
                </View>
                {serverUrl === p.url && (
                  <Ionicons name="checkmark-circle" size={18} color="#2563EB" />
                )}
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* CONNECTION DIAGNOSTICS & PING TEST */}
        <View style={styles.settingCard}>
          <View style={styles.cardHeaderRow}>
            <View style={styles.iconBadgeGreen}>
              <Ionicons name="pulse-outline" size={22} color="#059669" />
            </View>
            <View style={styles.cardHeaderText}>
              <Text style={styles.cardTitle}>Network Health Check</Text>
              <Text style={styles.cardSubtitle}>
                Perform round-trip ping latency and HTTP status test
              </Text>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.pingButton, isPinging && styles.pingButtonDisabled]}
            onPress={testConnection}
            disabled={isPinging}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel="Test server connection"
          >
            {isPinging ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <>
                <Ionicons name="wifi" size={18} color="#FFFFFF" style={{ marginRight: 8 }} />
                <Text style={styles.pingButtonText}>Test Connection & Ping</Text>
              </>
            )}
          </TouchableOpacity>

          {/* Ping Diagnostics Result Card */}
          {pingResult.tested && (
            <View
              style={[
                styles.pingResultCard,
                pingResult.ok ? styles.pingSuccessCard : styles.pingFailureCard,
              ]}
            >
              <View style={styles.pingResultHeader}>
                <Ionicons
                  name={pingResult.ok ? 'checkmark-circle' : 'alert-circle'}
                  size={20}
                  color={pingResult.ok ? '#16A34A' : '#DC2626'}
                />
                <Text
                  style={[
                    styles.pingResultTitle,
                    { color: pingResult.ok ? '#166534' : '#991B1B' },
                  ]}
                >
                  {pingResult.ok ? 'Connection Verified' : 'Host Unreachable'}
                </Text>
                <Text style={styles.pingLatency}>
                  {pingResult.latencyMs} ms
                </Text>
              </View>

              <Text style={styles.pingExplanation}>{pingResult.message}</Text>
              {pingResult.timestamp && (
                <Text style={styles.pingTimestamp}>Tested at {pingResult.timestamp}</Text>
              )}
            </View>
          )}
        </View>

        {/* RESTORE DEFAULTS */}
        <TouchableOpacity
          style={styles.restoreDefaultsButton}
          onPress={resetToDefaults}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="Restore default settings"
        >
          <Ionicons name="refresh-outline" size={18} color="#64748B" style={{ marginRight: 6 }} />
          <Text style={styles.restoreDefaultsText}>Restore Competition Defaults</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  screenWrapper: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  header: {
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
  headerTitleBox: {
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0F172A',
  },
  headerSubtitle: {
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
  toastBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#DCFCE7',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#86EFAC',
    gap: 8,
  },
  toastText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#166534',
  },
  settingCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 18,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
  },
  iconBadgeBlue: {
    width: 42,
    height: 42,
    borderRadius: 12,
    backgroundColor: '#EFF6FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconBadgeIndigo: {
    width: 42,
    height: 42,
    borderRadius: 12,
    backgroundColor: '#EEF2FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconBadgeGreen: {
    width: 42,
    height: 42,
    borderRadius: 12,
    backgroundColor: '#ECFDF5',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  cardHeaderText: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
  },
  cardSubtitle: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
    lineHeight: 16,
  },
  statusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 12,
    gap: 8,
  },
  mockStatus: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#BFDBFE',
  },
  liveStatus: {
    backgroundColor: '#ECFDF5',
    borderWidth: 1,
    borderColor: '#A7F3D0',
  },
  statusBannerText: {
    fontSize: 12,
    fontWeight: '600',
    flex: 1,
  },
  mockText: {
    color: '#1D4ED8',
  },
  liveText: {
    color: '#047857',
  },
  inputContainer: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  urlInput: {
    flex: 1,
    height: 48, // >= 48dp HCI principle
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#CBD5E1',
    paddingHorizontal: 14,
    fontSize: 14,
    color: '#0F172A',
    fontFamily: 'monospace',
  },
  applyButton: {
    backgroundColor: '#1E3A8A',
    height: 48, // >= 48dp HCI principle
    paddingHorizontal: 18,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  applyButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  presetsHeading: {
    fontSize: 12,
    fontWeight: '700',
    color: '#64748B',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  presetButtonsList: {
    gap: 8,
  },
  presetButton: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    backgroundColor: '#F8FAFC',
    minHeight: 48, // >= 48dp HCI principle
  },
  presetButtonActive: {
    borderColor: '#2563EB',
    backgroundColor: '#EFF6FF',
  },
  presetTextCol: {
    flex: 1,
  },
  presetLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: '#334155',
  },
  presetLabelActive: {
    color: '#1D4ED8',
  },
  presetUrl: {
    fontSize: 11,
    color: '#64748B',
    fontFamily: 'monospace',
    marginTop: 1,
  },
  pingButton: {
    backgroundColor: '#059669',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48, // >= 48dp HCI principle
    borderRadius: 12,
    shadowColor: '#059669',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 2,
  },
  pingButtonDisabled: {
    opacity: 0.6,
  },
  pingButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
  pingResultCard: {
    marginTop: 14,
    padding: 14,
    borderRadius: 14,
    borderWidth: 1,
  },
  pingSuccessCard: {
    backgroundColor: '#F0FDF4',
    borderColor: '#BBF7D0',
  },
  pingFailureCard: {
    backgroundColor: '#FEF2F2',
    borderColor: '#FECACA',
  },
  pingResultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  pingResultTitle: {
    fontSize: 14,
    fontWeight: '800',
    marginLeft: 6,
    flex: 1,
  },
  pingLatency: {
    fontSize: 12,
    fontWeight: '800',
    color: '#64748B',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  pingExplanation: {
    fontSize: 12,
    color: '#334155',
    lineHeight: 17,
  },
  pingTimestamp: {
    fontSize: 10,
    color: '#94A3B8',
    marginTop: 6,
  },
  restoreDefaultsButton: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: 48, // >= 48dp HCI principle
    marginTop: 8,
  },
  restoreDefaultsText: {
    fontSize: 13,
    color: '#64748B',
    fontWeight: '600',
  },
});
