# Identity development

Read README.md and docs/identity.md. Runtime code is in src/controlplane_identity.
Public module contracts are in contracts/identity.json. Legacy api.* aliases are
owned by the separate compatibility package, not this distribution.

Run bash scripts/check-package.sh. Source and fresh external-wheel tests must
pass; wheel runtime files must match source. Keep authentication scope, token
handling and wallet proof behavior unchanged when editing packaging or CI.
Service configuration and legacy-alias integration require consumer suites.

CI uses ubuntu-24.04, exact action SHAs, read-only contents and no deployment
credentials. Keep internal migration planning and receipts in hypermesh-docs.

## Package publication permission boundary

Source/package validation keeps its existing runner policy and read-only contents.
The separate `.github/workflows/release.yml` publication job is the narrow exception:
it may use `contents: write` and `actions: read` on disposable `ubuntu-24.04` workers
solely through the exact-pinned shared package publisher. It must not check out or
execute this repository's code, install its packages, or receive private dependency
or deployment credentials. This hosted publication exception does not authorize
moving secret-bearing validation to another runner group. Stable publication must
retain any configured release-admission prerequisite for the exact tag/commit.
