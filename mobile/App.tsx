import React, { useState } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';

import { StandingsScreen } from './src/screens/StandingsScreen';
import { MatchDetailScreen } from './src/screens/MatchDetailScreen';
import { StoreScreen } from './src/screens/StoreScreen';
import { ProductDetailModal } from './src/screens/ProductDetailModal';
import { ReceiptModal } from './src/screens/ReceiptModal';
import { RosterScreen } from './src/screens/RosterScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';

import { Match, Product } from './src/mocks/mockData';
import { useCartStore } from './src/store/cartStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

type TabType = 'standings' | 'store' | 'roster' | 'settings';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('standings');
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [selectedProductForModal, setSelectedProductForModal] = useState<Product | null>(null);

  const { lastReceipt, clearReceipt, selectProduct } = useCartStore();

  const handleOpenMatch = (match: Match) => {
    setSelectedMatch(match);
  };

  const handleBackFromMatch = () => {
    setSelectedMatch(null);
  };

  const handleBuyPinnedMerch = (product: Product) => {
    setSelectedMatch(null);
    setActiveTab('store');
    selectProduct(product);
    setSelectedProductForModal(product);
  };

  const handleSelectProduct = (product: Product) => {
    selectProduct(product);
    setSelectedProductForModal(product);
  };

  const handleCloseProductModal = () => {
    setSelectedProductForModal(null);
  };

  const handleCheckoutSuccess = () => {
    setSelectedProductForModal(null);
  };

  const handleDoneReceipt = () => {
    clearReceipt();
  };

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaView style={styles.safeArea}>
        <StatusBar style="dark" />

        <View style={styles.container}>
          {/* Main Content Area based on Tab and Sub-routes */}
          <View style={styles.contentArea}>
            {activeTab === 'standings' && (
              selectedMatch ? (
                <MatchDetailScreen
                  match={selectedMatch}
                  onBack={handleBackFromMatch}
                  onBuyPinnedProduct={handleBuyPinnedMerch}
                />
              ) : (
                <StandingsScreen
                  onSelectMatch={handleOpenMatch}
                  onOpenSettings={() => setActiveTab('settings')}
                />
              )
            )}

            {activeTab === 'store' && (
              <StoreScreen
                onSelectProduct={handleSelectProduct}
                onOpenSettings={() => setActiveTab('settings')}
              />
            )}

            {activeTab === 'roster' && (
              <RosterScreen onOpenSettings={() => setActiveTab('settings')} />
            )}

            {activeTab === 'settings' && (
              <SettingsScreen onBack={() => setActiveTab('standings')} />
            )}
          </View>

          {/* Product Variant Picker Modal (Journey 2) */}
          {selectedProductForModal && (
            <ProductDetailModal
              product={selectedProductForModal}
              onClose={handleCloseProductModal}
              onSuccessCheckout={handleCheckoutSuccess}
            />
          )}

          {/* Official Order Receipt Modal (Journey 2: PKR 4500.00) */}
          {lastReceipt && (
            <ReceiptModal
              receipt={lastReceipt}
              onDone={handleDoneReceipt}
            />
          )}

          {/* Primary Bottom Navigation Bar (HCI Principle: >=48dp touch targets, clear labels & icons) */}
          <View style={styles.tabBar}>
            <TouchableOpacity
              style={[styles.tabItem, activeTab === 'standings' && styles.tabItemActive]}
              onPress={() => {
                setSelectedMatch(null);
                setActiveTab('standings');
              }}
              activeOpacity={0.75}
              accessibilityRole="tab"
              accessibilityState={{ selected: activeTab === 'standings' }}
              accessibilityLabel="Standings and Match Centre"
            >
              <Ionicons
                name={activeTab === 'standings' ? 'trophy' : 'trophy-outline'}
                size={22}
                color={activeTab === 'standings' ? '#1E3A8A' : '#64748B'}
              />
              <Text
                style={[
                  styles.tabLabel,
                  activeTab === 'standings' && styles.tabLabelActive,
                ]}
              >
                Standings
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.tabItem, activeTab === 'store' && styles.tabItemActive]}
              onPress={() => setActiveTab('store')}
              activeOpacity={0.75}
              accessibilityRole="tab"
              accessibilityState={{ selected: activeTab === 'store' }}
              accessibilityLabel="Official Merchandise Store"
            >
              <Ionicons
                name={activeTab === 'store' ? 'bag-handle' : 'bag-handle-outline'}
                size={22}
                color={activeTab === 'store' ? '#1E3A8A' : '#64748B'}
              />
              <Text
                style={[
                  styles.tabLabel,
                  activeTab === 'store' && styles.tabLabelActive,
                ]}
              >
                Store
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.tabItem, activeTab === 'roster' && styles.tabItemActive]}
              onPress={() => setActiveTab('roster')}
              activeOpacity={0.75}
              accessibilityRole="tab"
              accessibilityState={{ selected: activeTab === 'roster' }}
              accessibilityLabel="Club Roster Management"
            >
              <Ionicons
                name={activeTab === 'roster' ? 'people' : 'people-outline'}
                size={22}
                color={activeTab === 'roster' ? '#1E3A8A' : '#64748B'}
              />
              <Text
                style={[
                  styles.tabLabel,
                  activeTab === 'roster' && styles.tabLabelActive,
                ]}
              >
                Roster
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.tabItem, activeTab === 'settings' && styles.tabItemActive]}
              onPress={() => setActiveTab('settings')}
              activeOpacity={0.75}
              accessibilityRole="tab"
              accessibilityState={{ selected: activeTab === 'settings' }}
              accessibilityLabel="Settings and Server URL"
            >
              <Ionicons
                name={activeTab === 'settings' ? 'settings' : 'settings-outline'}
                size={22}
                color={activeTab === 'settings' ? '#1E3A8A' : '#64748B'}
              />
              <Text
                style={[
                  styles.tabLabel,
                  activeTab === 'settings' && styles.tabLabelActive,
                ]}
              >
                Settings
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    paddingTop: Platform.OS === 'android' ? 24 : 0,
  },
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  contentArea: {
    flex: 1,
  },
  tabBar: {
    flexDirection: 'row',
    height: 64, // >= 48dp HCI principle
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingBottom: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 8,
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    minHeight: 48, // >= 48dp HCI touch target
  },
  tabItemActive: {
    borderTopWidth: 2,
    borderTopColor: '#1E3A8A',
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748B',
    marginTop: 3,
  },
  tabLabelActive: {
    color: '#1E3A8A',
    fontWeight: '800',
  },
});
