import React from "react";
import "./Card.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Card",
  variants: ["default", "outlined", "elevated"],
  sizes: [],
  states: ["default"],
  accessibility: ["semantic_structure"]
} as const;

export type CardProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Card(props: CardProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-card className="card" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-card>
  );
}
