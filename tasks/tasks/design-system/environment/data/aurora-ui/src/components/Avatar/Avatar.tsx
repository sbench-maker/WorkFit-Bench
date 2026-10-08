import React from "react";
import "./Avatar.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Avatar",
  variants: ["default"],
  sizes: [],
  states: ["default"],
  accessibility: ["semantic_structure"]
} as const;

export type AvatarProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Avatar(props: AvatarProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-avatar className="avatar" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-avatar>
  );
}
