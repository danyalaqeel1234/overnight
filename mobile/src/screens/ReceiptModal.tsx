import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { OrderReceipt } from '../store/cartStore';

interface ReceiptModalProps {
  receipt: OrderReceipt;
  onDone: () => void;
}

export const ReceiptModal: React.FC<ReceiptModalProps> = ({
  receipt,
  onDone,
}) => {
  return (
    <View style={styles.modalOverlay}>
      <View style={styles.receiptContainer}>
        {/* Top Success Badge */}
        <View style={styles.successIconHeader}>
          <View style={styles.iconCircle}>
            <Ionicons name="checkmark" size={36} color="#FFFFFF" />
          </View>
          <Text style={styles.successHeading}>Payment Successful!</Text>
          <Text style={styles.successSubtitle}>
            Your official matchday order is confirmed
          </Text>
        </View>

        <ScrollView style={styles.receiptBodyScroll} showsVerticalScrollIndicator={false}>
          {/* Main Paper Receipt Card */}
          <View style={styles.paperCard}>
            <View style={styles.orderIdBar}>
              <View>
                <Text style={styles.orderIdLabel}>ORDER IDENTIFIER</Text>
                <Text style={styles.orderIdValue}>{receipt.orderId}</Text>
              </View>
              <View style={styles.statusPill}>
                <Text style={styles.statusPillText}>{receipt.status}</Text>
              </View>
            </View>

            <View style={styles.dividerDashed} />

            {/* Line Items */}
            <View style={styles.lineItem}>
              <View style={styles.lineItemIcon}>
                <Ionicons name="shirt" size={24} color="#1E3A8A" />
              </View>
              <View style={styles.lineItemDetails}>
                <Text style={styles.itemTitle}>{receipt.product.title}</Text>
                <Text style={styles.itemMeta}>
                  Size: {receipt.selectedSize} • Color: {receipt.selectedColor.name}
                </Text>
                <Text style={styles.itemQuantity}>Qty: {receipt.quantity}</Text>
              </View>
            </View>

            <View style={styles.dividerDashed} />

            {/* Transaction Ledger */}
            <View style={styles.ledgerRow}>
              <Text style={styles.ledgerLabel}>Subtotal</Text>
              <Text style={styles.ledgerValue}>
                PKR {receipt.totalPKR.toLocaleString('en-PK', { minimumFractionDigits: 2 })}
              </Text>
            </View>

            <View style={styles.ledgerRow}>
              <Text style={styles.ledgerLabel}>NaSCon Express Shipping</Text>
              <Text style={[styles.ledgerValue, styles.freeShipping]}>FREE (Complimentary)</Text>
            </View>

            <View style={styles.ledgerRow}>
              <Text style={styles.ledgerLabel}>Payment Token</Text>
              <Text style={[styles.ledgerValue, styles.tokenFont]}>{receipt.paymentToken}</Text>
            </View>

            <View style={styles.ledgerRow}>
              <Text style={styles.ledgerLabel}>Timestamp</Text>
              <Text style={styles.ledgerValue}>{receipt.timestamp}</Text>
            </View>

            <View style={styles.dividerSolid} />

            {/* Grand Total Requirement: Exactly PKR 4500.00 */}
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>TOTAL AMOUNT</Text>
              <Text style={styles.totalValue}>
                PKR {receipt.totalPKR.toLocaleString('en-PK', { minimumFractionDigits: 2 })}
              </Text>
            </View>
          </View>

          {/* Delivery Note */}
          <View style={styles.dispatchNoteCard}>
            <Ionicons name="cube-outline" size={20} color="#2563EB" />
            <View style={styles.dispatchTextContainer}>
              <Text style={styles.dispatchTitle}>Pickup at Team Stall</Text>
              <Text style={styles.dispatchSub}>
                Show this digital receipt at FAST National Arena Stall #04 to collect.
              </Text>
            </View>
          </View>
        </ScrollView>

        {/* Primary CTA (>= 48dp touch target) */}
        <View style={styles.receiptActions}>
          <TouchableOpacity
            style={styles.doneButton}
            onPress={onDone}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel="Done and return to store"
          >
            <Ionicons name="checkmark-done" size={20} color="#FFFFFF" style={{ marginRight: 8 }} />
            <Text style={styles.doneButtonText}>Done & Return to Store</Text>
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
    backgroundColor: 'rgba(15, 23, 42, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
    zIndex: 100,
  },
  receiptContainer: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    width: '100%',
    maxWidth: 380,
    maxHeight: '92%',
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.2,
    shadowRadius: 20,
    elevation: 8,
  },
  successIconHeader: {
    alignItems: 'center',
    marginBottom: 16,
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#16A34A',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
    shadowColor: '#16A34A',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  successHeading: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0F172A',
  },
  successSubtitle: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  receiptBodyScroll: {
    maxHeight: 380,
  },
  paperCard: {
    backgroundColor: '#F8FAFC',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  orderIdBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  orderIdLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#64748B',
    letterSpacing: 0.5,
  },
  orderIdValue: {
    fontSize: 15,
    fontWeight: '800',
    color: '#1E3A8A',
    fontFamily: 'monospace',
    marginTop: 2,
  },
  statusPill: {
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  statusPillText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#166534',
  },
  dividerDashed: {
    height: 1,
    borderWidth: 1,
    borderColor: '#CBD5E1',
    borderStyle: 'dashed',
    marginVertical: 12,
  },
  dividerSolid: {
    height: 1,
    backgroundColor: '#CBD5E1',
    marginVertical: 12,
  },
  lineItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  lineItemIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: '#EFF6FF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  lineItemDetails: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0F172A',
  },
  itemMeta: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  itemQuantity: {
    fontSize: 11,
    fontWeight: '700',
    color: '#2563EB',
    marginTop: 1,
  },
  ledgerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  ledgerLabel: {
    fontSize: 12,
    color: '#64748B',
  },
  ledgerValue: {
    fontSize: 12,
    fontWeight: '600',
    color: '#1E293B',
  },
  freeShipping: {
    color: '#16A34A',
    fontWeight: '700',
  },
  tokenFont: {
    fontFamily: 'monospace',
    color: '#2563EB',
    fontWeight: '700',
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 4,
  },
  totalLabel: {
    fontSize: 13,
    fontWeight: '800',
    color: '#0F172A',
  },
  totalValue: {
    fontSize: 20,
    fontWeight: '900',
    color: '#1E3A8A',
  },
  dispatchNoteCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EFF6FF',
    padding: 12,
    borderRadius: 12,
    marginTop: 12,
    borderWidth: 1,
    borderColor: '#DBEAFE',
  },
  dispatchTextContainer: {
    marginLeft: 10,
    flex: 1,
  },
  dispatchTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1E3A8A',
  },
  dispatchSub: {
    fontSize: 11,
    color: '#475569',
    marginTop: 1,
    lineHeight: 15,
  },
  receiptActions: {
    marginTop: 16,
  },
  doneButton: {
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
  doneButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
});
