# Releasing controlplane-identity

This repository builds one Python distribution, `controlplane-identity`.
Release names and the version inside the wheel are different fields. Read the
wheel version after you install.

## Versions in use

| Artifact | Package version | Where it comes from |
| --- | --- | --- |
| Default branch (`pyproject.toml`) | `0.15.0` | This source tree |
| Stable admission line (`release-policy.json`, `.github/workflows/release.yml`) | `0.15` | Tag push admission |
| GitHub release [`v0.24.0`](https://github.com/hyperme-sh/controlplane-identity/releases/tag/v0.24.0) | `0.24.0` | Revision `74857a6e3b2c22eb1752329693a3f146d9489120` |
| Prerelease `0.24.0-test.0` | `0.15.0` wheel inside a `0.24.0-test.N` tag | Main qualification bundle |

`releases/accepted` records the `v0.24.0` release: GitHub release id
`434687235`, the revision above, and the published asset digests (wheel
`sha256:dc8519d07eadd07efd7d05487a44c0a29d85d5cfb2ac37fedb7f78fe8e3b3ad9`).
The public import contract in `contracts/identity.json` is version `1.0.0` and
moves separately from the package version.

The project is not published to PyPI. Install from a clone of this branch or
from a GitHub release asset. See the [README](../README.md) for the commands.

Account-closure checks and interactive age confirmation are part of the
`0.15.0` source tree and are absent from the `v0.24.0` wheel at
`74857a6e3b2c22eb1752329693a3f146d9489120`. Building this tree does not publish
a new stable release. Consumers pinned to an older commit or to that wheel
keep the checks that revision actually contains. The README lists which
checks the wheel omits.

## Qualification

[`.github/workflows/package.yml`](../.github/workflows/package.yml) runs
`bash scripts/check-package.sh` on pull requests, pushes to `main`, and manual
runs. The job uses Ubuntu 24.04, read-only contents, and pinned actions. It
does not create a GitHub release or tag.

On a push to `main`, the job uploads the wheel and sdist it just built as the
`tested-dist` artifact and keeps it for 90 days. Those bytes are the input to
the test-bundle and stable publishers. A later rebuild is a different
artifact.

`test-<commit>` tags are development snapshots. The package version embedded
in a snapshot does not reserve a stable version. Snapshot records live under
`releases/qualification`.

## Test bundles

[`.github/test-channel.json`](../.github/test-channel.json) sets the bundle
train to `next: 0.24.0`. After
[Standalone package](../.github/workflows/package.yml) succeeds on `main`,
[`.github/workflows/test-bundles.yml`](../.github/workflows/test-bundles.yml)
publishes an immutable prerelease tag `0.24.0-test.N`. The publisher checks
the workflow run, source revision, and the original `tested-dist` digest, and
it uploads those files. Pull requests run qualification and do not publish.

The `0.24.0` in the tag is the train name. The wheel's own version stays the
version that was built. `0.24.0-test.0` contains
`controlplane_identity-0.15.0-py3-none-any.whl`. A deployment manifest should
pin the component commit and the artifact digest.

## Stable releases

Pushing a `v*` tag runs
[`.github/workflows/release.yml`](../.github/workflows/release.yml).

1. Admission calls the Spanopticon component-release workflow with release
   line `0.15`, `SPANOPTICON_RELEASE_BASELINE_SHA`, and the tag name. The
   repository variable must be the full commit SHA of an accepted baseline.
   The manifest files that check reads (`releases/accepted`,
   `releases/candidate`) are described in
   [release-policy.md](release-policy.md). The `release-line` input for this
   repository is `0.15`, from `.github/workflows/release.yml`.
2. When admission succeeds, the shared release-channel action publishes the
   `tested-dist` artifact produced by `.github/workflows/package.yml` for that
   source revision. The publish job does not check out this repository or
   rebuild the wheel.

A green package run, by itself, does not publish a stable release. A
`test-<commit>` snapshot or an `0.24.0-test.N` bundle is not an accepted
stable release. The accepted record stays the immutable `v0.24.0` release
until a newer stable tag is published and recorded under `releases/accepted`.

Changing a public module, session scope, or wallet-verification behavior
requires a contract update in `contracts/identity.json`. Package qualification
compares runtime bytes of the wheel with the source tree, and it requires the
contract exported from the sdist rebuild to match. That byte comparison is
stricter than a semantic compatibility check. Service integration and live
Base RPC acceptance stay in the consumer repositories.
