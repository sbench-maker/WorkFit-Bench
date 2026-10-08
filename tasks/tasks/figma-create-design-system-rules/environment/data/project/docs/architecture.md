# Front-end architecture

The design-system layer owns reusable visual primitives. Feature folders compose primitives with domain behavior. Pages connect routing and server-state. TanStack Query owns server-state; local interaction state stays in the nearest component. New routes are registered in `src/app/router.tsx`, then the generated route ID file is refreshed by its script.
