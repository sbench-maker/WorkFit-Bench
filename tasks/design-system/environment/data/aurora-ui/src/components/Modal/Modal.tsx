import React from "react";
import "./Modal.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Modal",
  variants: ["default"],
  sizes: [],
  states: ["closed", "opening", "open", "closing"],
  accessibility: ["escape_dismiss", "focus_trap", "accessible_name"]
} as const;

export type ModalProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Modal(props: ModalProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-modal className="modal" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-modal>
  );
}
