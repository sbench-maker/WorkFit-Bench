import React from "react";
import "./Radio.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Radio",
  variants: ["default"],
  sizes: ["sm", "md"],
  states: ["default", "hover", "focus-visible", "disabled", "checked"],
  accessibility: ["keyboard_toggle", "label_association", "focus_visible"]
} as const;

export type RadioProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Radio(props: RadioProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-radio className="radio" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-radio>
  );
}
