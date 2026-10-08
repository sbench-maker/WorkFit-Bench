import { render, screen } from '@testing-library/react';
import { OrderSummaryCard } from './OrderSummaryCard';

it('labels the order summary', () => {
  render(<OrderSummaryCard order={{ id: 'ord-17', customerName: 'Cedar Labs', status: 'Ready' }} />);
  expect(screen.getByRole('region', { name: 'Cedar Labs' })).toBeVisible();
});
