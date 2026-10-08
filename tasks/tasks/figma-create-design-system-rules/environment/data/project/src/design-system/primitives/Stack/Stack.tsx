import type { CSSProperties, HTMLAttributes } from 'react';
import clsx from 'clsx';
import styles from './Stack.module.css';

type Space = '1' | '2' | '3' | '4' | '6' | '8';
export type StackProps = HTMLAttributes<HTMLDivElement> & { gap?: Space };
export function Stack({ className, gap = '4', style, ...props }: StackProps) {
  const vars = { '--stack-gap': `var(--space-${gap})`, ...style } as CSSProperties;
  return <div className={clsx(styles.root, className)} style={vars} {...props} />;
}
