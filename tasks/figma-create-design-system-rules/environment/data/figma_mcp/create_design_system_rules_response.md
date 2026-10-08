# Captured Figma MCP response

The project rule file should define a repeatable Figma implementation flow and then specialize it to the repository.

## Required Figma flow

1. Call `get_design_context` for the exact node or variant.
2. If that response is too large or truncated, call `get_metadata`, identify the smaller node set, and call `get_design_context` again only for those nodes.
3. Call `get_screenshot` for the same node or variant.
4. Start implementation only after the structured context and screenshot are both available; obtain referenced assets from the MCP assets endpoint.
5. Translate generated code into the repository's framework, component, styling, routing, state, and data-access conventions.
6. Compare the completed behavior and visuals with the Figma screenshot before finishing.

## Asset behavior

- Use localhost image or SVG sources returned by the MCP response directly while retrieving the asset.
- Do not add icon packages or substitute placeholders when the payload already provides an asset.
- Document the repository directory used for persisted assets.

## Repository specialization

Document component locations and reuse rules, design-token sources, styling technique, import/export conventions, tests, accessibility, and any architectural boundaries that Figma-generated code must respect.
