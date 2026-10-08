# Orbit accessibility handoff

The starter is expected to meet WCAG 2.1 AA. Normal text needs at least 4.5:1 contrast, and focus indicators/control boundaries need at least 3:1 against adjacent colors. Do not use color as the only validation cue.

Use native `button` and `input` elements. Loading buttons must prevent activation and expose busy state; icon-only buttons need a caller-provided accessible name. Every input needs an associated visible label in its FormField. Hint and error text must be connected through IDs, invalid inputs must expose `aria-invalid`, and validation errors must be announced.

Alerts use a polite status announcement for routine information and an assertive alert for urgent errors. A Modal is a labeled, modal dialog: move focus inside on open, keep Tab and Shift+Tab within it, close on Escape, provide a named close control, restore focus to the opener, and restore page scrolling on cleanup. All interactive components need a visible `:focus-visible` treatment.
