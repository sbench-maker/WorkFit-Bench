import { Card, Stack } from '@/design-system';
import type { OrderSummary } from '@/features/orders/types';
import styles from './OrderSummaryCard.module.css';

export function OrderSummaryCard({ order }: { order: OrderSummary }) {
  return (
    <Card aria-labelledby={`order-${order.id}`}>
      <Stack gap="2">
        <h2 id={`order-${order.id}`} className={styles.title}>{order.customerName}</h2>
        <span className={styles.status}>{order.status}</span>
      </Stack>
    </Card>
  );
}
