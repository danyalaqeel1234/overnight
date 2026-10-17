import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Product } from '../mocks/mockData';
import { useCartStore } from '../store/cartStore';

interface ProductDetailModalProps {
  product: Product;
  onClose: () => void;
  onSuccessCheckout: () => void;
}

export const ProductDetailModal: React.FC<ProductDetailModalProps> = ({
  product,
  onClose,
  onSuccessCheckout,
}) => {
  const {
    selectedSize,
    selectedColor,
    setSelectedSize,
    setSelectedColor,
    quantity,
    setQuantity,
    isCheckingOut,
    checkoutError,
    executeCheckout,
  } = useCartStore();

  const [activeToken, setActiveToken] = useState('tok_success');

  const handleCheckout = async () => {
    const success = await executeCheckout(activeToken);
    if (success) {
      onSuccessCheckout();
    }
  };

  return (
    <View style={styles.modalOverlay}>
      <View style={styles.modalContent}>
        {/* Modal Top Handle & Close */}
        <View style={styles.modalHeader}>
          <View style={styles.dragPill} />
          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            accessibilityRole="button"
            accessibilityLabel="Close product modal"
          >
            <Ionicons name="close" size={24} color="#0F172A" />
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.scrollArea} contentContainerStyle={styles.scrollContent}>
          {/* Product Header Visual */}
          <View style={styles.visualContainer}>
            <View style={[styles.colorPreviewBubble, { backgroundColor: selectedColor.hex }]} />
            <Ionicons name="shirt" size={72} color="#1E3A8A" />
            <View style={styles.badgePill}>
              <Text style={styles.badgePillText}>Official Club Merch</Text>
            </View>
          </View>

          <Text style={styles.productTitle}>{product.title}</Text>
          <Text style={styles.productDescription}>{product.description}</Text>

          {/* Pricing Row */}
          <View style={styles.pricingCard}>
            <View>
              <Text style={styles.pricingLabel}>Matchday Price</Text>
              <Text style={styles.pricingValue}>
                PKR {product.pricePKR.toLocaleString('en-PK', { minimumFractionDigits: 2 })}
              </Text>
            </View>
            <View style={styles.deliveryBadge}>
              <Ionicons name="flash" size={14} color="#059669" />
              <Text style={styles.deliveryText}>Instant Digital Receipt</Text>
            </View>
          </View>

          {/* VARIANT PICKER 1: SIZE (>= 48dp touch targets) */}
          <View style={styles.sectionBlock}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Select Size</Text>
              <Text style={styles.selectedVariantLabel}>Selected: {selectedSize}</Text>
            </View>
            <View style={styles.sizesRow}>
              {product.sizes.map(size => {
                const isSelected = selectedSize === size;
                return (
                  <TouchableOpacity
                    key={size}
                    style={[styles.sizeOptionButton, isSelected && styles.sizeOptionButtonSelected]}
                    onPress={() => setSelectedSize(size)}
                    activeOpacity={0.8}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: isSelected }}
                    accessibilityLabel={`Size ${size}`}
                  >
                    <Text
                      style={[styles.sizeOptionText, isSelected && styles.sizeOptionTextSelected]}
                    >
                      {size}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* VARIANT PICKER 2: COLOR (>= 48dp touch targets) */}
          <View style={styles.sectionBlock}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Select Colour Edition</Text>
              <Text style={styles.selectedVariantLabel}>{selectedColor.name}</Text>
            </View>
            <View style={styles.colorsList}>
              {product.colors.map(color => {
                const isSelected = selectedColor.name === color.name;
                return (
                  <TouchableOpacity
                    key={color.name}
                    style={[styles.colorOptionRow, isSelected && styles.colorOptionRowSelected]}
                    onPress={() => setSelectedColor(color)}
                    activeOpacity={0.8}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: isSelected }}
                    accessibilityLabel={`Color ${color.name}`}
                  >
                    <View style={[styles.colorChip, { backgroundColor: color.hex }]} />
                    <Text
                      style={[styles.colorNameText, isSelected && styles.colorNameTextSelected]}
                    >
                      {color.name}
                    </Text>
                    {isSelected && (
                      <Ionicons name="checkmark-circle" size={20} color="#2563EB" />
                    )}
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Payment Method Verification */}
          <View style={styles.sectionBlock}>
            <View style={styles.sectionHeaderRow}>
              <Text style={styles.sectionTitle}>Payment Simulation</Text>
              <Text style={styles.selectedVariantLabel}>Mock Gateway</Text>
            </View>
            <View style={styles.tokenBox}>
              <View style={styles.tokenTopRow}>
                <Ionicons name="card" size={18} color="#2563EB" />
                <Text style={styles.tokenTitle}>Mock Payment Token</Text>
              </View>
              <Text style={styles.tokenValue}>{activeToken}</Text>
              <Text style={styles.tokenNote}>
                Pre-configured for 100% reliable evaluation demo.
              </Text>
            </View>
          </View>

          {/* Error Banner */}
          {checkoutError && (
            <View style={styles.errorBanner}>
              <Ionicons name="alert-circle" size={18} color="#DC2626" />
              <Text style={styles.errorBannerText}>{checkoutError}</Text>
            </View>
          )}
        </ScrollView>

        {/* Bottom Sticky Action Bar */}
        <View style={styles.modalBottomBar}>
          <View style={styles.totalSummary}>
            <Text style={styles.totalLabel}>Total Payable</Text>
            <Text style={styles.totalAmount}>
              PKR {product.pricePKR.toLocaleString('en-PK', { minimumFractionDigits: 2 })}
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.checkoutButton, isCheckingOut && styles.checkoutButtonDisabled]}
            onPress={handleCheckout}
            disabled={isCheckingOut}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel="Complete checkout using mock token tok_success"
          >
            {isCheckingOut ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <>
                <Ionicons name="shield-checkmark" size={18} color="#FFFFFF" style={{ marginRight: 6 }} />
                <Text style={styles.checkoutButtonText}>Checkout (tok_success)</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    justifyContent: 'flex-end',
    zIndex: 99,
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    maxHeight: '90%',
    paddingBottom: 24,
  },
  modalHeader: {
    alignItems: 'center',
    paddingTop: 12,
    paddingBottom: 8,
    position: 'relative',
  },
  dragPill: {
    width: 44,
    height: 5,
    borderRadius: 3,
    backgroundColor: '#CBD5E1',
  },
  closeButton: {
    position: 'absolute',
    right: 18,
    top: 10,
    width: 48, // >= 48dp HCI principle
    height: 48,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollArea: {
    paddingHorizontal: 20,
  },
  scrollContent: {
    paddingBottom: 16,
  },
  visualContainer: {
    height: 150,
    backgroundColor: '#F1F5F9',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    position: 'relative',
    overflow: 'hidden',
  },
  colorPreviewBubble: {
    position: 'absolute',
    top: 14,
    left: 14,
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  badgePill: {
    position: 'absolute',
    bottom: 12,
    backgroundColor: '#1E3A8A',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgePillText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  productTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0F172A',
    marginBottom: 6,
  },
  productDescription: {
    fontSize: 13,
    color: '#64748B',
    lineHeight: 19,
    marginBottom: 16,
  },
  pricingCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    padding: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 18,
  },
  pricingLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#64748B',
    textTransform: 'uppercase',
  },
  pricingValue: {
    fontSize: 20,
    fontWeight: '900',
    color: '#1E3A8A',
  },
  deliveryBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  deliveryText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#166534',
    marginLeft: 4,
  },
  sectionBlock: {
    marginBottom: 18,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: '#0F172A',
  },
  selectedVariantLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#2563EB',
  },
  sizesRow: {
    flexDirection: 'row',
    gap: 10,
  },
  sizeOptionButton: {
    flex: 1,
    minHeight: 48, // >= 48dp HCI principle
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#CBD5E1',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
  },
  sizeOptionButtonSelected: {
    borderColor: '#2563EB',
    backgroundColor: '#EFF6FF',
  },
  sizeOptionText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#475569',
  },
  sizeOptionTextSelected: {
    color: '#2563EB',
  },
  colorsList: {
    gap: 8,
  },
  colorOptionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 48, // >= 48dp HCI principle
    paddingHorizontal: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    backgroundColor: '#FFFFFF',
  },
  colorOptionRowSelected: {
    borderColor: '#2563EB',
    backgroundColor: '#EFF6FF',
  },
  colorChip: {
    width: 22,
    height: 22,
    borderRadius: 11,
    marginRight: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  colorNameText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: '#334155',
  },
  colorNameTextSelected: {
    color: '#1E3A8A',
    fontWeight: '700',
  },
  tokenBox: {
    backgroundColor: '#F1F5F9',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  tokenTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  tokenTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1E3A8A',
    marginLeft: 6,
  },
  tokenValue: {
    fontSize: 14,
    fontWeight: '800',
    color: '#0F172A',
    fontFamily: 'monospace',
  },
  tokenNote: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#FEE2E2',
    marginBottom: 14,
  },
  errorBannerText: {
    fontSize: 12,
    color: '#B91C1C',
    marginLeft: 8,
    flex: 1,
    fontWeight: '600',
  },
  modalBottomBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
  totalSummary: {
    flex: 1,
  },
  totalLabel: {
    fontSize: 11,
    color: '#64748B',
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  totalAmount: {
    fontSize: 18,
    fontWeight: '900',
    color: '#0F172A',
  },
  checkoutButton: {
    backgroundColor: '#2563EB',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50, // >= 48dp HCI principle
    paddingHorizontal: 20,
    borderRadius: 14,
    shadowColor: '#2563EB',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  checkoutButtonDisabled: {
    opacity: 0.7,
  },
  checkoutButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
});
