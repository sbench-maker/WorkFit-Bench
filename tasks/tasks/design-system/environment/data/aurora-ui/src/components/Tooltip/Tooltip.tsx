import React from "react";
import "./Tooltip.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Tooltip",
  variants: ["default", "inverse"],
  sizes: [],
  states: ["closed", "open"],
  accessibility: ["hover_and_focus", "describedby_link"]
} as const;

export type TooltipProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Tooltip(props: TooltipProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-tooltip className="tooltip" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-tooltip>
  );
}
