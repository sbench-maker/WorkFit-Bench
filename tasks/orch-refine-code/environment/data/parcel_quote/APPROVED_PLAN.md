# Approved refactor direction

The maintainer has approved extracting validation and price calculation behind
one internal boundary, then making both the Python API and CLI use it. Public
imports and command syntax stay fixed. Delete the unused legacy seasonal path;
do not introduce a package dependency or change the pricing policy.

This approval covers implementation. A commit is intentionally out of scope.
