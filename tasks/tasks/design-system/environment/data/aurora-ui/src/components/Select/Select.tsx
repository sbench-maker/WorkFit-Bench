import React from "react";
import "./Select.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Select",
  variants: ["outline", "filled"],
  sizes: ["sm", "md", "large"],
  states: ["default", "hover", "focus-visible", "disabled"],
  accessibility: ["label_association", "focus_visible"]
} as const;

export type SelectProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Select(props: SelectProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-select className="select" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-select>
  );
}
