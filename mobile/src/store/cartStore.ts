import { create } from 'zustand';
import { Product, mockPinnedProduct } from '../mocks/mockData';
import { apiClient } from '../api/client';

export interface OrderReceipt {
  orderId: string;
  product: Product;
  selectedSize: string;
  selectedColor: { name: string; hex: string };
  quantity: number;
  totalPKR: number;
  paymentToken: string;
  status: 'PAID' | 'FAILED';
  timestamp: string;
  deliveryEstimate: string;
}

interface CartState {
  selectedProduct: Product | null;
  selectedSize: string;
  selectedColor: { name: string; hex: string };
  quantity: number;
  isCheckingOut: boolean;
  checkoutError: string | null;
  lastReceipt: OrderReceipt | null;

  selectProduct: (product: Product) => void;
  setSelectedSize: (size: string) => void;
  setSelectedColor: (color: { name: string; hex: string }) => void;
  setQuantity: (qty: number) => void;
  executeCheckout: (paymentToken?: string) => Promise<boolean>;
  clearCart: () => void;
  clearReceipt: () => void;
}

export const useCartStore = create<CartState>((set, get) => ({
  selectedProduct: mockPinnedProduct,
  selectedSize: 'L',
  selectedColor: mockPinnedProduct.colors[0],
  quantity: 1,
  isCheckingOut: false,
  checkoutError: null,
  lastReceipt: null,

  selectProduct: (product: Product) => {
    set({
      selectedProduct: product,
      selectedSize: product.sizes[0] || 'M',
      selectedColor: product.colors[0] || { name: 'Standard', hex: '#000000' },
      quantity: 1,
      checkoutError: null,
    });
  },

  setSelectedSize: (size: string) => set({ selectedSize: size }),
  setSelectedColor: (color: { name: string; hex: string }) => set({ selectedColor: color }),
  setQuantity: (qty: number) => set({ quantity: Math.max(1, qty) }),

  executeCheckout: async (paymentToken: string = 'tok_success') => {
    const { selectedProduct, selectedSize, selectedColor, quantity } = get();
    if (!selectedProduct) {
      set({ checkoutError: 'No item selected for checkout' });
      return false;
    }

    set({ isCheckingOut: true, checkoutError: null });

    try {
      const response = await apiClient.checkoutOrder({
        productId: selectedProduct.id,
        variantSize: selectedSize,
        variantColor: selectedColor.name,
        quantity,
        paymentToken,
      });

      const receipt: OrderReceipt = {
        orderId: response.orderId,
        product: selectedProduct,
        selectedSize,
        selectedColor,
        quantity,
        totalPKR: response.totalPKR || 4500.0,
        paymentToken,
        status: 'PAID',
        timestamp: new Date().toLocaleDateString('en-PK', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }),
        deliveryEstimate: '2-3 Business Days (Express Dispatch)',
      };

      set({
        isCheckingOut: false,
        lastReceipt: receipt,
        checkoutError: null,
      });
      return true;
    } catch (err: any) {
      set({
        isCheckingOut: false,
        checkoutError: err?.message || 'Payment could not be completed with the provided token.',
      });
      return false;
    }
  },

  clearCart: () => {
    set({
      selectedProduct: null,
      checkoutError: null,
    });
  },

  clearReceipt: () => {
    set({ lastReceipt: null });
  },
}));
