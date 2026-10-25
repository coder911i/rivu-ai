# Branch and Pull Request Policy

## Branch names

Use one of these prefixes:

- `fix/<short-bug>` — bug fixes
- `feat/<short-feature>` — user-facing features
- `refactor/<short-area>` — behavior-preserving code restructuring
- `test/<short-area>` — tests and test infrastructure
- `docs/<short-topic>` — documentation
- `chore/<short-task>` — repository and tooling maintenance

Use lowercase kebab-case. Avoid creating a new branch for each tiny follow-up if it belongs in the existing open feature branch.

## Pull request checklist

- [ ] Explain the user-visible or operational problem.
- [ ] Keep the diff focused; avoid unrelated formatting and file moves.
- [ ] Add/update tests for behavior changes.
- [ ] Run backend tests relevant to the changed module.
- [ ] Run `npm run build` for frontend changes.
- [ ] Run `npm run test:e2e` when the change affects a user flow.
- [ ] Record any test that could not run and why.
- [ ] Verify no real secrets, customer data, generated reports, or local build artifacts are included.
- [ ] Check deployment configuration and migration compatibility when relevant.

## Branch cleanup

Do not delete branches just because they look old. First confirm whether each branch has an open PR, unique commits not merged into `main`, or a deployment/release dependency. Delete only branches confirmed merged or intentionally abandoned after their work has been preserved.

## Release rule

A green frontend build does not prove the backend refinery works. Report frontend, backend, E2E, and deployment checks separately. Do not describe a skipped integration test as a pass.
