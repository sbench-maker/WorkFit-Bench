import React from "react";
import "./Button.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Button",
  variants: ["primary", "secondary", "ghost", "danger"],
  sizes: ["sm", "md", "lg"],
  states: ["default", "hover", "active", "focus-visible", "disabled"],
  accessibility: ["keyboard_activation", "accessible_name", "focus_visible"]
} as const;

export type ButtonProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Button(props: ButtonProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-button className="button" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-button>
  );
}
