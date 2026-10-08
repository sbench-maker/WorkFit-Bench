import React from "react";
import "./Breadcrumb.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Breadcrumb",
  variants: ["default"],
  sizes: ["sm", "md", "lg"],
  states: ["default", "hover", "focus-visible", "selected", "disabled"],
  accessibility: ["arrow_keys", "home_end", "roving_tabindex", "focus_visible"]
} as const;

export type BreadcrumbProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Breadcrumb(props: BreadcrumbProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-breadcrumb className="breadcrumb" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-breadcrumb>
  );
}
