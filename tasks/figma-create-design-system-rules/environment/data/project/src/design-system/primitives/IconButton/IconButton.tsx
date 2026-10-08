import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Button } from '@/design-system/primitives/Button';
import styles from './IconButton.module.css';

type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
  label: string;
  icon: ReactNode;
};
export function IconButton({ label, icon, ...props }: IconButtonProps) {
  return <Button className={styles.root} aria-label={label} {...props}>{icon}</Button>;
}
