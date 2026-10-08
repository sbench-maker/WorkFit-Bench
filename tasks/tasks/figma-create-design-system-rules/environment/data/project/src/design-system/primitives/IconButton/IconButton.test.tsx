import { render, screen } from '@testing-library/react';
import { IconButton } from './IconButton';

it('has an accessible name', () => {
  render(<IconButton label="Open filters" icon={<svg aria-hidden="true" />} />);
  expect(screen.getByRole('button', { name: 'Open filters' })).toBeVisible();
});
