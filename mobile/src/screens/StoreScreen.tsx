import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CustomHeader } from '../components/CustomHeader';
import { mockProducts, Product } from '../mocks/mockData';
import { EmptyState } from '../components/EmptyState';

interface StoreScreenProps {
  onSelectProduct: (product: Product) => void;
  onOpenSettings: () => void;
}

export const StoreScreen: React.FC<StoreScreenProps> = ({
  onSelectProduct,
  onOpenSettings,
}) => {
  const [products, setProducts] = useState<Product[]>(mockProducts);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const categories = [
    { id: 'all', label: 'All Apparel' },
    { id: 'jerseys', label: 'Match Kits' },
    { id: 'jackets', label: 'Jackets' },
    { id: 'warmups', label: 'Warm-ups' },
  ];

  const filteredProducts = products.filter(p => {
    const matchesCategory =
      selectedCategory === 'all' || p.category === selectedCategory;
    const matchesSearch =
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setProducts(mockProducts);
      setIsRefreshing(false);
    }, 350);
  };

  return (
    <View style={styles.screenWrapper}>
      <CustomHeader
        title="Club Store"
        subtitle="Official Mutators FC Merchandise"
        rightAction={{ icon: 'settings-outline', label: 'Settings', onPress: onOpenSettings }}
      />

      {/* Search Input Bar */}
      <View style={styles.searchBarContainer}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={20} color="#64748B" style={styles.searchIcon} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search jerseys, jackets, sizes..."
            placeholderTextColor="#94A3B8"
            value={searchQuery}
            onChangeText={setSearchQuery}
            accessibilityLabel="Search products"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity
              onPress={() => setSearchQuery('')}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Ionicons name="close-circle" size={18} color="#94A3B8" />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Category Pills */}
      <View style={styles.categoryPillsContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categoryScroll}>
          {categories.map(cat => (
            <TouchableOpacity
              key={cat.id}
              style={[
                styles.categoryPill,
                selectedCategory === cat.id && styles.categoryPillActive,
              ]}
              onPress={() => setSelectedCategory(cat.id)}
              activeOpacity={0.8}
              accessibilityRole="tab"
              accessibilityLabel={cat.label}
            >
              <Text
                style={[
                  styles.categoryPillText,
                  selectedCategory === cat.id && styles.categoryPillTextActive,
                ]}
              >
                {cat.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <ScrollView
        style={styles.productsScroll}
        contentContainerStyle={styles.productsGrid}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} colors={['#2563EB']} />
        }
      >
        {filteredProducts.length === 0 ? (
          <EmptyState
            icon="shirt-outline"
            title="No Items Match Your Filter"
            description="Try resetting your category or search terms to see the full apparel collection."
            actionLabel="Reset Filters"
            onAction={() => {
              setSearchQuery('');
              setSelectedCategory('all');
            }}
          />
        ) : (
          filteredProducts.map(product => (
            <TouchableOpacity
              key={product.id}
              style={styles.productCard}
              onPress={() => onSelectProduct(product)}
              activeOpacity={0.88}
              accessibilityRole="button"
              accessibilityLabel={`Select ${product.title} for PKR ${product.pricePKR}`}
            >
              {/* Product Badge */}
              {product.badge && (
                <View style={styles.cardBadge}>
                  <Text style={styles.cardBadgeText}>{product.badge}</Text>
                </View>
              )}

              {/* Product Visual Container */}
              <View style={styles.productVisual}>
                <Ionicons
                  name={product.category === 'jackets' ? 'shirt-outline' : 'shirt'}
                  size={58}
                  color="#1E3A8A"
                />
              </View>

              {/* Product Info */}
              <View style={styles.productBody}>
                <View style={styles.ratingRow}>
                  <Ionicons name="star" size={13} color="#D97706" />
                  <Text style={styles.ratingNumber}>{product.rating}</Text>
                  <Text style={styles.reviewsCount}>({product.reviewsCount})</Text>
                </View>

                <Text style={styles.cardTitle} numberOfLines={2}>
                  {product.title}
                </Text>

                <View style={styles.variantsInfo}>
                  <Text style={styles.variantsLabel}>Sizes: {product.sizes.join(', ')}</Text>
                </View>

                <View style={styles.cardFooter}>
                  <View>
                    <Text style={styles.priceLabel}>Price</Text>
                    <Text style={styles.priceText}>
                      PKR {product.pricePKR.toLocaleString('en-PK', { minimumFractionDigits: 2 })}
                    </Text>
                  </View>

                  <View style={styles.addToCartButton}>
                    <Text style={styles.addToCartText}>Select</Text>
                    <Ionicons name="chevron-forward" size={14} color="#FFFFFF" />
                  </View>
                </View>
              </View>
            </TouchableOpacity>
          ))
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
  searchBarContainer: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 6,
    backgroundColor: '#FFFFFF',
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F1F5F9',
    borderRadius: 12,
    paddingHorizontal: 12,
    height: 48, // >= 48dp HCI principle
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: '#0F172A',
  },
  categoryPillsContainer: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  categoryScroll: {
    paddingHorizontal: 16,
    gap: 8,
  },
  categoryPill: {
    paddingHorizontal: 16,
    minHeight: 48, // >= 48dp HCI touch target
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 24,
    backgroundColor: '#F1F5F9',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  categoryPillActive: {
    backgroundColor: '#1E3A8A',
    borderColor: '#1E3A8A',
  },
  categoryPillText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#475569',
  },
  categoryPillTextActive: {
    color: '#FFFFFF',
  },
  productsScroll: {
    flex: 1,
  },
  productsGrid: {
    padding: 16,
    paddingBottom: 40,
    gap: 16,
  },
  productCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  cardBadge: {
    position: 'absolute',
    top: 12,
    right: 12,
    backgroundColor: '#1E3A8A',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    zIndex: 2,
  },
  cardBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  productVisual: {
    height: 140,
    backgroundColor: '#EFF6FF',
    justifyContent: 'center',
    alignItems: 'center',
  },
  productBody: {
    padding: 16,
  },
  ratingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  ratingNumber: {
    fontSize: 12,
    fontWeight: '700',
    color: '#92400E',
    marginLeft: 4,
  },
  reviewsCount: {
    fontSize: 11,
    color: '#64748B',
    marginLeft: 4,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
    lineHeight: 22,
    marginBottom: 6,
  },
  variantsInfo: {
    marginBottom: 12,
  },
  variantsLabel: {
    fontSize: 12,
    color: '#64748B',
    fontWeight: '500',
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#F1F5F9',
  },
  priceLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: '#64748B',
    textTransform: 'uppercase',
  },
  priceText: {
    fontSize: 17,
    fontWeight: '900',
    color: '#1E3A8A',
  },
  addToCartButton: {
    backgroundColor: '#2563EB',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    minHeight: 48, // >= 48dp HCI principle
    borderRadius: 12,
  },
  addToCartText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
    marginRight: 4,
  },
});
