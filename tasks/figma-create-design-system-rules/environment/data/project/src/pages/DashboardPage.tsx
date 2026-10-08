import { useQuery } from '@tanstack/react-query';
import { Stack } from '@/design-system';
import { getOrders } from '@/features/orders/api/getOrders';
import { OrderSummaryCard } from '@/features/orders/components/OrderSummaryCard/OrderSummaryCard';

export function DashboardPage() {
  const orders = useQuery({ queryKey: ['orders'], queryFn: getOrders });
  return <main><Stack>{orders.data?.map(order => <OrderSummaryCard key={order.id} order={order} />)}</Stack></main>;
}
