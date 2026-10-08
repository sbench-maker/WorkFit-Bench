import React from "react";
import "./IconButton.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "IconButton",
  variants: ["primary", "quiet", "danger"],
  sizes: ["sm", "md", "lg"],
  states: ["default", "hover", "active", "focus-visible", "disabled", "loading"],
  accessibility: ["keyboard_activation", "focus_visible"]
} as const;

export type IconButtonProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function IconButton(props: IconButtonProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-iconbutton className="iconbutton" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-iconbutton>
  );
}
