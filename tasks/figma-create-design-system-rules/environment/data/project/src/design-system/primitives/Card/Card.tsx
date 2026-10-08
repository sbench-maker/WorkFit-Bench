import type { HTMLAttributes } from 'react';
import clsx from 'clsx';
import styles from './Card.module.css';

export type CardProps = HTMLAttributes<HTMLElement>;
export function Card({ className, ...props }: CardProps) {
  return <section className={clsx(styles.root, className)} {...props} />;
}
