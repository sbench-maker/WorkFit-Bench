import React from "react";
import "./Skeleton.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Skeleton",
  variants: ["default"],
  sizes: [],
  states: ["default"],
  accessibility: []
} as const;

export type SkeletonProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Skeleton(props: SkeletonProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-skeleton className="skeleton" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-skeleton>
  );
}
