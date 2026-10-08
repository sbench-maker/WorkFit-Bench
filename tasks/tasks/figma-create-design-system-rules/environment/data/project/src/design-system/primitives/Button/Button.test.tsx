import { render, screen } from '@testing-library/react';
import { Button } from './Button';

it('forwards native button behavior', () => {
  render(<Button disabled>Archive order</Button>);
  expect(screen.getByRole('button', { name: 'Archive order' })).toBeDisabled();
});
