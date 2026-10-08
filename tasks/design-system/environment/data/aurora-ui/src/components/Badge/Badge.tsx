import React from "react";
import "./Badge.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Badge",
  variants: ["neutral", "info", "success", "warning", "critical"],
  sizes: ["sm", "md"],
  states: ["default"],
  accessibility: ["non_color_cue"]
} as const;

export type BadgeProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Badge(props: BadgeProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-badge className="badge" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-badge>
  );
}
