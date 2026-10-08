import { apiClient } from '@/services/apiClient';
import type { OrderSummary } from '../types';

export async function getOrders(): Promise<OrderSummary[]> {
  return apiClient.get('/orders');
}
