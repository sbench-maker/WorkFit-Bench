import React from "react";
import "./Table.css";

// This frozen source boundary records the public API and the behaviors wired
// into Aurora's internal runtime; implementation bodies are outside the release snapshot.
export const componentContract = {
  name: "Table",
  variants: ["default", "striped"],
  sizes: ["sm", "md"],
  states: ["default", "loading", "empty"],
  accessibility: ["header_association", "caption_or_label", "sort_announcement"]
} as const;

export type TableProps = {
  variant?: typeof componentContract.variants[number];
  size?: typeof componentContract.sizes[number];
  disabled?: boolean;
  children?: React.ReactNode;
};

export function Table(props: TableProps) {
  const { variant = componentContract.variants[0], size, disabled, children } = props;
  return (
    <aurora-table className="table" data-variant={variant} data-size={size} data-disabled={disabled}>
      {children}
    </aurora-table>
  );
}
