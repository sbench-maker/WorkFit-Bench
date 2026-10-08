# Team operating policy

The repository is the durable memory shared by independent agent chats.

- Producer clone: `evalharbor-producer`, stays on `main`, coordinates and merges; Remy does not write feature code.
- Development clone: `evalharbor-dev`, branch `feature/sprint-1`; Nova, Sage, and Kira contribute there.
- QA clone: `evalharbor-qa`, branch `feature/qa-1`; Ivy tests merged `main`, files issues, and records sign-off rather than editing product source.
- DevOps clone: `evalharbor-devops`, branch `feature/devops-1`; Dash owns Compose and CI work.
- Use feature branch -> pull request -> regular merge. Never push directly to `main`, force-push, rebase shared feature branches, squash the sprint, or use worktrees.
- Bugs live in repository issues with component, reproduction steps, expected/actual result, and severity. Fix commits use `Fixes #NN`; QA verifies before closure.
- Each phase updates the Sprint 1 progress tracker. At handoff, record completed work, remaining work, blockers, decisions, issue/PR references, and the next safe action.
- A fresh chat must be able to resume by reading the project brief and current sprint progress without relying on prior conversation.
