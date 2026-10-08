import React from "react";
import "./Toast.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Toast",
  variants: ["info", "success", "warning", "danger"],
  sizes: ["sm", "medium"],
  states: ["default"],
  accessibility: ["non_color_cue"]
} as const;

export type ToastProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Toast(props: ToastProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-toast className="toast" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-toast>
  );
}
