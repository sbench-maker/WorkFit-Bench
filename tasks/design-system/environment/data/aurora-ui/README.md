# Aurora UI audit snapshot

This is a complete, fictional repository snapshot for the 3.4.0 release review. The registry defines scope and usage frequency; policy files define approved names, required states/accessibility behaviors, token rules, exceptions, and migration policy. Within each TSX file, `componentContract` is the frozen implementation boundary: its arrays record the public API and the behaviors actually wired into the internal runtime; runtime bodies are outside this snapshot. Component CSS and Markdown pages are included in full.
