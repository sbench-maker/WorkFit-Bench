"""Public annotation names expected by the source skill documentation."""

from enum import Enum


class AnnotationKind(str, Enum):
    ASSUMPTION = "assumption"
    PRECONDITION = "precondition"
    POSTCONDITION = "postcondition"
    INVARIANT = "invariant"
    BLAST_RADIUS = "blast_radius"
    PRIVILEGE_BOUNDARY = "privilege_boundary"
    TAINT_PROPAGATION = "taint_propagation"
    FINDING = "finding"
    AUDIT_NOTE = "audit_note"
