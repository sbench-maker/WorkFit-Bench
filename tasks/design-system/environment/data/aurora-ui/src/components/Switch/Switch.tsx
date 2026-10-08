import React from "react";
import "./Switch.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Switch",
  variants: ["default"],
  sizes: ["sm", "md"],
  states: ["default", "hover", "focus-visible", "disabled", "checked"],
  accessibility: ["keyboard_toggle", "label_association", "focus_visible"]
} as const;

export type SwitchProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Switch(props: SwitchProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-switch className="switch" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-switch>
  );
}
