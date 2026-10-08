from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

import pytest
from graphql import build_schema, get_named_type, is_abstract_type, parse, validate
from graphql.language import print_ast
from graphql.language.ast import (
    ArgumentNode,
    BooleanValueNode,
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    Node,
    OperationDefinitionNode,
    SelectionSetNode,
    VariableNode,
)


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "review-workspace.graphql"
SCHEMA_PATH = DATA_DIR / "schema.graphql"


QUERY_REQUIRED = {
    ("Query", "project"),
    ("Project", "id"),
    ("Project", "name"),
    ("Project", "status"),
    ("Project", "client"),
    ("Project", "assets"),
    ("Client", "id"),
    ("Client", "name"),
    ("AssetConnection", "edges"),
    ("AssetConnection", "pageInfo"),
    ("AssetConnection", "totalCount"),
    ("AssetEdge", "cursor"),
    ("AssetEdge", "node"),
    ("PageInfo", "hasNextPage"),
    ("PageInfo", "endCursor"),
    ("Asset", "id"),
    ("Asset", "title"),
    ("Asset", "status"),
    ("Asset", "version"),
    ("Asset", "thumbnail"),
    ("Asset", "reviewer"),
    ("Asset", "latestDecision"),
    ("Asset", "internalNote"),
    ("AssetThumbnail", "url"),
    ("AssetThumbnail", "altText"),
    ("User", "id"),
    ("User", "displayName"),
    ("User", "avatarUrl"),
    ("ReviewDecision", "id"),
    ("ReviewDecision", "decision"),
    ("ReviewDecision", "decidedAt"),
    ("ReviewDecision", "reviewer"),
}

ASSET_CARD_REQUIRED = {
    ("Asset", "id"),
    ("Asset", "title"),
    ("Asset", "status"),
    ("Asset", "version"),
    ("Asset", "thumbnail"),
    ("Asset", "reviewer"),
    ("Asset", "latestDecision"),
    ("AssetThumbnail", "url"),
    ("AssetThumbnail", "altText"),
    ("User", "id"),
    ("User", "displayName"),
    ("User", "avatarUrl"),
    ("ReviewDecision", "id"),
    ("ReviewDecision", "decision"),
    ("ReviewDecision", "decidedAt"),
    ("ReviewDecision", "reviewer"),
}

MUTATION_REQUIRED = {
    ("Mutation", "submitAssetDecision"),
    ("SubmitAssetDecisionResult", "__typename"),
    ("SubmitAssetDecisionSuccess", "asset"),
    ("SubmitAssetDecisionSuccess", "clientMutationId"),
    ("DecisionValidationError", "code"),
    ("DecisionValidationError", "message"),
    ("DecisionValidationError", "field"),
    ("DecisionValidationError", "clientMutationId"),
    ("DecisionVersionConflict", "code"),
    ("DecisionVersionConflict", "message"),
    ("DecisionVersionConflict", "expectedVersion"),
    ("DecisionVersionConflict", "currentVersion"),
    ("DecisionVersionConflict", "asset"),
    ("DecisionVersionConflict", "clientMutationId"),
} | ASSET_CARD_REQUIRED

SUBSCRIPTION_REQUIRED = {
    ("Subscription", "assetDecisionChanged"),
    ("AssetDecisionChangedEvent", "id"),
    ("AssetDecisionChangedEvent", "occurredAt"),
    ("AssetDecisionChangedEvent", "project"),
    ("AssetDecisionChangedEvent", "actor"),
    ("AssetDecisionChangedEvent", "asset"),
    ("Project", "id"),
} | ASSET_CARD_REQUIRED

SUCCESS_BRANCH_REQUIRED = {
    ("SubmitAssetDecisionSuccess", "asset"),
    ("SubmitAssetDecisionSuccess", "clientMutationId"),
} | ASSET_CARD_REQUIRED

VALIDATION_BRANCH_REQUIRED = {
    ("DecisionValidationError", "code"),
    ("DecisionValidationError", "message"),
    ("DecisionValidationError", "field"),
    ("DecisionValidationError", "clientMutationId"),
}

CONFLICT_BRANCH_REQUIRED = {
    ("DecisionVersionConflict", "code"),
    ("DecisionVersionConflict", "message"),
    ("DecisionVersionConflict", "expectedVersion"),
    ("DecisionVersionConflict", "currentVersion"),
    ("DecisionVersionConflict", "asset"),
    ("DecisionVersionConflict", "clientMutationId"),
} | ASSET_CARD_REQUIRED


@lru_cache(maxsize=1)
def _schema():
    return build_schema(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_document() -> tuple[DocumentNode | None, str | None]:
    try:
        text = OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, f"cannot read {OUTPUT_PATH}: {exc}"
    if not text.strip():
        return None, f"{OUTPUT_PATH} is empty"
    try:
        return parse(text), None
    except Exception as exc:
        return None, f"GraphQL syntax error: {exc}"


def _document_or_skip() -> DocumentNode:
    document, error = _load_document()
    if document is None:
        pytest.skip(f"blocked by unreadable artifact; scored by artifact_usability: {error}")
    return document


def _validated_document_or_skip() -> DocumentNode:
    document = _document_or_skip()
    errors = validate(_schema(), document)
    if errors:
        pytest.skip("blocked by schema-invalid document; scored by schema_and_variables")
    return document


def _fragments(document: DocumentNode) -> dict[str, FragmentDefinitionNode]:
    return {
        definition.name.value: definition
        for definition in document.definitions
        if isinstance(definition, FragmentDefinitionNode)
    }


def _operations(document: DocumentNode) -> list[OperationDefinitionNode]:
    return [
        definition
        for definition in document.definitions
        if isinstance(definition, OperationDefinitionNode)
    ]


def _expanded_level(
    selection_set: SelectionSetNode,
    fragments: dict[str, FragmentDefinitionNode],
    stack: tuple[str, ...] = (),
):
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            yield selection
        elif isinstance(selection, InlineFragmentNode):
            yield from _expanded_level(selection.selection_set, fragments, stack)
        elif isinstance(selection, FragmentSpreadNode):
            name = selection.name.value
            if name not in stack and name in fragments:
                yield from _expanded_level(fragments[name].selection_set, fragments, stack + (name,))


def _root_fields(operation: OperationDefinitionNode, document: DocumentNode) -> set[str]:
    return {field.name.value for field in _expanded_level(operation.selection_set, _fragments(document))}


def _operation_for_root(
    document: DocumentNode, kind: str, root_field: str
) -> OperationDefinitionNode | None:
    matches = [
        operation
        for operation in _operations(document)
        if operation.operation.value == kind and root_field in _root_fields(operation, document)
    ]
    return matches[0] if len(matches) == 1 else None


def _walk_nodes(value):
    if isinstance(value, Node):
        yield value
        for key in value.keys:
            yield from _walk_nodes(getattr(value, key, None))
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk_nodes(item)


def _root_type(operation: OperationDefinitionNode):
    return {
        "query": _schema().query_type,
        "mutation": _schema().mutation_type,
        "subscription": _schema().subscription_type,
    }[operation.operation.value]


def _collect_coordinates_from_selection(
    selection_set: SelectionSetNode,
    parent_type,
    fragments: dict[str, FragmentDefinitionNode],
    stack: tuple[str, ...] = (),
) -> tuple[set[tuple[str, str]], list[tuple[str, str, FieldNode]]]:
    coordinates: set[tuple[str, str]] = set()
    typed_nodes: list[tuple[str, str, FieldNode]] = []
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            field_name = selection.name.value
            coordinates.add((parent_type.name, field_name))
            typed_nodes.append((parent_type.name, field_name, selection))
            if selection.selection_set is not None and field_name != "__typename":
                field_def = parent_type.fields.get(field_name)
                if field_def is not None:
                    child_type = get_named_type(field_def.type)
                    child_coords, child_nodes = _collect_coordinates_from_selection(
                        selection.selection_set, child_type, fragments, stack
                    )
                    coordinates |= child_coords
                    typed_nodes.extend(child_nodes)
        elif isinstance(selection, InlineFragmentNode):
            next_type = parent_type
            if selection.type_condition is not None:
                next_type = _schema().get_type(selection.type_condition.name.value)
            child_coords, child_nodes = _collect_coordinates_from_selection(
                selection.selection_set, next_type, fragments, stack
            )
            coordinates |= child_coords
            typed_nodes.extend(child_nodes)
        elif isinstance(selection, FragmentSpreadNode):
            name = selection.name.value
            if name in stack or name not in fragments:
                continue
            fragment = fragments[name]
            next_type = _schema().get_type(fragment.type_condition.name.value)
            child_coords, child_nodes = _collect_coordinates_from_selection(
                fragment.selection_set, next_type, fragments, stack + (name,)
            )
            coordinates |= child_coords
            typed_nodes.extend(child_nodes)
    return coordinates, typed_nodes


def _operation_coordinates(
    operation: OperationDefinitionNode, document: DocumentNode
) -> tuple[set[tuple[str, str]], list[tuple[str, str, FieldNode]]]:
    return _collect_coordinates_from_selection(
        operation.selection_set, _root_type(operation), _fragments(document)
    )


def _allow_only_required(
    actual: set[tuple[str, str]], required: set[tuple[str, str]], context: str
) -> None:
    missing = sorted(required - actual)
    extras = sorted(coordinate for coordinate in actual - required if coordinate[1] != "__typename")
    assert not missing, f"{context} is missing UI-required schema fields: {missing}"
    assert not extras, f"{context} requests fields the UI contract does not consume: {extras}"


def _field_arguments(node: FieldNode) -> dict[str, ArgumentNode]:
    return {argument.name.value: argument for argument in node.arguments}


def _assert_user_selection(node: FieldNode, fragments, context: str) -> None:
    assert node.selection_set is not None, f"{context} must select reviewer identity fields"
    actual, _ = _collect_coordinates_from_selection(
        node.selection_set, _schema().get_type("User"), fragments
    )
    required = {("User", "id"), ("User", "displayName"), ("User", "avatarUrl")}
    _allow_only_required(actual, required, context)


def _assert_asset_card_selection(
    node: FieldNode,
    fragments: dict[str, FragmentDefinitionNode],
    context: str,
    *,
    include_internal_note: bool,
) -> None:
    assert node.selection_set is not None, f"{context} must select the asset card payload"
    actual, typed_nodes = _collect_coordinates_from_selection(
        node.selection_set, _schema().get_type("Asset"), fragments
    )
    required = set(ASSET_CARD_REQUIRED)
    if include_internal_note:
        required.add(("Asset", "internalNote"))
    _allow_only_required(actual, required, context)

    reviewer_nodes = [
        child
        for parent, name, child in typed_nodes
        if (parent, name) in {("Asset", "reviewer"), ("ReviewDecision", "reviewer")}
    ]
    assert len(reviewer_nodes) == 2, (
        f"{context} must carry both the assigned reviewer and latest-decision reviewer identities"
    )
    for index, reviewer in enumerate(reviewer_nodes, start=1):
        _assert_user_selection(reviewer, fragments, f"{context} reviewer selection {index}")


def _variant_accepts(type_condition_name: str, variant_name: str) -> bool:
    condition = _schema().get_type(type_condition_name)
    variant = _schema().get_type(variant_name)
    if condition is variant:
        return True
    return bool(is_abstract_type(condition) and _schema().is_sub_type(condition, variant))


def _variant_coordinates(
    selection_set: SelectionSetNode,
    parent_type,
    variant_name: str,
    fragments: dict[str, FragmentDefinitionNode],
    stack: tuple[str, ...] = (),
) -> set[tuple[str, str]]:
    coordinates: set[tuple[str, str]] = set()
    for selection in selection_set.selections:
        if isinstance(selection, FieldNode):
            field_name = selection.name.value
            coordinates.add((parent_type.name, field_name))
            if selection.selection_set is not None and field_name != "__typename":
                field_def = parent_type.fields.get(field_name)
                if field_def is not None:
                    coordinates |= _collect_coordinates_from_selection(
                        selection.selection_set, get_named_type(field_def.type), fragments, stack
                    )[0]
        elif isinstance(selection, InlineFragmentNode):
            if selection.type_condition is None:
                coordinates |= _variant_coordinates(
                    selection.selection_set, parent_type, variant_name, fragments, stack
                )
            else:
                condition_name = selection.type_condition.name.value
                if _variant_accepts(condition_name, variant_name):
                    coordinates |= _collect_coordinates_from_selection(
                        selection.selection_set,
                        _schema().get_type(condition_name),
                        fragments,
                        stack,
                    )[0]
        elif isinstance(selection, FragmentSpreadNode):
            name = selection.name.value
            if name in stack or name not in fragments:
                continue
            fragment = fragments[name]
            condition_name = fragment.type_condition.name.value
            if _variant_accepts(condition_name, variant_name):
                coordinates |= _collect_coordinates_from_selection(
                    fragment.selection_set,
                    _schema().get_type(condition_name),
                    fragments,
                    stack + (name,),
                )[0]
    return coordinates


def _submit_result_selection(operation: OperationDefinitionNode, document: DocumentNode):
    fields = list(_expanded_level(operation.selection_set, _fragments(document)))
    submit = [field for field in fields if field.name.value == "submitAssetDecision"]
    assert len(submit) == 1 and submit[0].selection_set is not None
    return submit[0].selection_set


def test_operation_scope():
    document = _document_or_skip()
    operations = _operations(document)
    unnamed = [operation.operation.value for operation in operations if operation.name is None]
    assert not unnamed, f"all production operations must be named; unnamed kinds: {unnamed}"

    expected_roots = {
        "query": {"project"},
        "mutation": {"submitAssetDecision"},
        "subscription": {"assetDecisionChanged"},
    }
    observed = {kind: set() for kind in expected_roots}
    for operation in operations:
        kind = operation.operation.value
        assert kind in expected_roots, f"unexpected operation kind: {kind}"
        observed[kind] |= _root_fields(operation, document)
    assert observed == expected_roots, (
        f"operation roots are {observed}, expected {expected_roots}; the client bundle must cover "
        "only the requested workspace, decision, and live-update flows"
    )
    for kind, root in (("query", "project"), ("mutation", "submitAssetDecision"), ("subscription", "assetDecisionChanged")):
        matches = [
            op for op in operations if op.operation.value == kind and root in _root_fields(op, document)
        ]
        assert len(matches) == 1, f"expected one unambiguous {kind} operation for {root}, found {len(matches)}"


def test_schema_and_variable_integrity():
    document = _document_or_skip()
    errors = validate(_schema(), document)
    assert not errors, "document does not validate against schema.graphql:\n" + "\n".join(
        f"- {error.message}" for error in errors
    )

    literal_arguments = []
    for node in _walk_nodes(document):
        if isinstance(node, ArgumentNode) and not isinstance(node.value, VariableNode):
            literal_arguments.append(f"{node.name.value}={print_ast(node.value)}")
    assert not literal_arguments, (
        "field and directive inputs must remain reusable variables, not embedded request values: "
        + ", ".join(literal_arguments)
    )


def test_workspace_query_contract():
    document = _validated_document_or_skip()
    operation = _operation_for_root(document, "query", "project")
    if operation is None:
        pytest.skip("blocked by missing/ambiguous project query; scored by operation_scope")
    coordinates, typed_nodes = _operation_coordinates(operation, document)
    _allow_only_required(coordinates, QUERY_REQUIRED, "workspace query")
    fragments = _fragments(document)

    asset_card_nodes = [
        node for parent, name, node in typed_nodes if parent == "AssetEdge" and name == "node"
    ]
    assert len(asset_card_nodes) == 1, "the paged asset edge must expose one asset card selection"
    _assert_asset_card_selection(
        asset_card_nodes[0], fragments, "workspace asset card", include_internal_note=True
    )

    asset_nodes = [node for parent, name, node in typed_nodes if parent == "Project" and name == "assets"]
    assert len(asset_nodes) == 1, "workspace query must select the Project.assets connection once"
    assert set(_field_arguments(asset_nodes[0])) == {"first", "after", "filter"}, (
        "Project.assets must expose the UI contract's first, after, and filter inputs for forward paging"
    )

    note_nodes = [node for parent, name, node in typed_nodes if parent == "Asset" and name == "internalNote"]
    assert len(note_nodes) == 1, "internalNote must appear once in the workspace query"
    include_directives = [directive for directive in note_nodes[0].directives if directive.name.value == "include"]
    assert len(include_directives) == 1, "internalNote must be gated by one @include directive"
    include_args = {argument.name.value: argument for argument in include_directives[0].arguments}
    assert set(include_args) == {"if"} and isinstance(include_args["if"].value, VariableNode), (
        "the internal-note include condition must be controlled by a Boolean variable"
    )
    toggle_name = include_args["if"].value.name.value
    definitions = {
        definition.variable.name.value: definition
        for definition in operation.variable_definitions or ()
    }
    assert toggle_name in definitions, "the internal-note toggle variable is not declared by the query"
    toggle = definitions[toggle_name]
    assert print_ast(toggle.type) in {"Boolean", "Boolean!"}, "the internal-note toggle must be Boolean"
    if isinstance(toggle.default_value, BooleanValueNode):
        assert toggle.default_value.value is False, "the privacy-sensitive internal note cannot default to included"
    elif print_ast(toggle.type) == "Boolean":
        pytest.fail("a nullable internal-note toggle needs a false default to satisfy @include safely")


def test_decision_mutation_contract():
    document = _validated_document_or_skip()
    operation = _operation_for_root(document, "mutation", "submitAssetDecision")
    if operation is None:
        pytest.skip("blocked by missing/ambiguous decision mutation; scored by operation_scope")
    coordinates, typed_nodes = _operation_coordinates(operation, document)
    _allow_only_required(coordinates, MUTATION_REQUIRED, "decision mutation")

    result_selection = _submit_result_selection(operation, document)
    fragments = _fragments(document)
    asset_nodes = [
        (parent, node)
        for parent, name, node in typed_nodes
        if name == "asset" and parent in {"SubmitAssetDecisionSuccess", "DecisionVersionConflict"}
    ]
    assert {parent for parent, _ in asset_nodes} == {
        "SubmitAssetDecisionSuccess",
        "DecisionVersionConflict",
    }, "both success and version-conflict outcomes must return the current asset card"
    assert len(asset_nodes) == 2, "each Asset-returning mutation outcome must select the card once"
    for parent, asset_node in asset_nodes:
        _assert_asset_card_selection(
            asset_node, fragments, f"{parent}.asset", include_internal_note=False
        )
    branch_requirements = {
        "SubmitAssetDecisionSuccess": SUCCESS_BRANCH_REQUIRED,
        "DecisionValidationError": VALIDATION_BRANCH_REQUIRED,
        "DecisionVersionConflict": CONFLICT_BRANCH_REQUIRED,
    }
    for variant, required in branch_requirements.items():
        actual = _variant_coordinates(
            result_selection,
            _schema().get_type("SubmitAssetDecisionResult"),
            variant,
            fragments,
        )
        missing = sorted(required - actual)
        assert not missing, f"{variant} cannot render/update the client without fields: {missing}"


def test_live_update_subscription_contract():
    document = _validated_document_or_skip()
    operation = _operation_for_root(document, "subscription", "assetDecisionChanged")
    if operation is None:
        pytest.skip("blocked by missing/ambiguous live-update subscription; scored by operation_scope")
    coordinates, typed_nodes = _operation_coordinates(operation, document)
    _allow_only_required(coordinates, SUBSCRIPTION_REQUIRED, "decision-change subscription")
    fragments = _fragments(document)
    asset_nodes = [
        node
        for parent, name, node in typed_nodes
        if parent == "AssetDecisionChangedEvent" and name == "asset"
    ]
    assert len(asset_nodes) == 1, "the live event must select one current asset card"
    _assert_asset_card_selection(
        asset_nodes[0], fragments, "subscription asset", include_internal_note=False
    )
    actor_nodes = [
        node
        for parent, name, node in typed_nodes
        if parent == "AssetDecisionChangedEvent" and name == "actor"
    ]
    assert len(actor_nodes) == 1, "the live event must select its actor once"
    _assert_user_selection(actor_nodes[0], fragments, "subscription actor")
