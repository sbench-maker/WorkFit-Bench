import React from "react";
import "./TextInput.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "TextInput",
  variants: ["outline", "filled"],
  sizes: ["sm", "md", "lg"],
  states: ["default", "hover", "focus-visible", "disabled"],
  accessibility: ["label_association", "error_announcement", "focus_visible"]
} as const;

export type TextInputProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function TextInput(props: TextInputProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-textinput className="textinput" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-textinput>
  );
}
