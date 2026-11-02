# controlplane-identity

Private shared identity package extracted from `FyberLabs/panopticon`. It owns
internal-token comparison, person/portal permissions, API-key and Keycloak
validation, purpose-bound sessions, and Base wallet proof verification.
See [the identity contract](docs/identity.md) for configuration and scope.

## Standalone development

Requires Python 3.13+ and uv 0.11.26. From this checkout:

```sh
uv sync --frozen
bash scripts/check-package.sh
```

The check verifies retained source bytes, runs the source tests, builds a wheel
and sdist, and runs the same tests from an unrelated directory against both the
wheel and a wheel rebuilt from the sdist. Test dependencies come from `uv.lock`.
No sibling repository, workspace package, private dependency or credential is
needed. Wallet RPC responses are mocked; these checks do not establish live Base
or validator acceptance.

## Extraction provenance

`EXTRACTION.json` is the original history-import receipt. `SOURCE-MANIFEST.json`
records relocation from source commit
`2d92d13f38d491c298631b9b9296979c1fbadd19`, including SHA-256 hashes. Runtime
Python files are unchanged. The wallet suite and complete historical identity
snapshot were copied from that same revision. The snapshot includes legacy
`api.*` aliases owned by `controlplane-core`; those aliases are not distributed
by this package and remain a paired consumer-integration check.

Package version stays **0.14.0**. The historical source-contract version recorded
in `contracts/source-identity.json` is separate. Packaging adds no public API or
wire change. Historical source guidance is retained in `docs/source-AGENTS.md`.

## CI and adoption

The package workflow uses disposable GitHub-hosted Ubuntu workers, read-only
contents permission, exact allowed action pins and no deployment environment.
Actions remain disabled pending the destination policy review and live isolation
audit in `FyberLabs/infra`; adding the workflow does not enable them.

This PR prepares standalone packaging. It does not release a tag, switch service
consumers, qualify financial evidence, remove Panopticon source, or move runtime
ownership. Consumer adoption still needs immutable dependency pins, authenticated
fetch and compatibility tests with the separately owned legacy aliases.
