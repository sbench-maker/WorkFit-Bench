import React from "react";
import "./Tabs.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Tabs",
  variants: ["default", "line", "pills"],
  sizes: ["sm", "md", "lg"],
  states: ["default", "hover", "focus-visible", "selected", "disabled"],
  accessibility: ["arrow_keys", "roving_tabindex", "focus_visible"]
} as const;

export type TabsProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Tabs(props: TabsProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-tabs className="tabs" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-tabs>
  );
}
