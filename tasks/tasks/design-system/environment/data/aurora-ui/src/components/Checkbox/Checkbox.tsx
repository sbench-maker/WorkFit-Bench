import React from "react";
import "./Checkbox.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Checkbox",
  variants: ["default"],
  sizes: ["sm", "md"],
  states: ["default", "hover", "focus-visible", "disabled"],
  accessibility: ["keyboard_toggle", "label_association", "focus_visible"]
} as const;

export type CheckboxProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Checkbox(props: CheckboxProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-checkbox className="checkbox" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-checkbox>
  );
}
