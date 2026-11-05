# controlplane-identity

## Current version authority

Current development version: `0.15.0`. The services remain before the unreleased
0.24.0 milestone. Earlier 0.24/1.0 preparation and publication notes below are
historical and do not authorize those versions. Existing tags and historical
artifacts remain untouched. Development uses exact source pins and rebuilt
artifacts; no prior release is required. Version changes, tags and publication
require the owner's explicit authorization to the agent.

Shared internal-token comparison, person/portal permissions, API-key and Keycloak
validation, purpose-bound sessions, and Base wallet proof verification.
See [configuration and verification behavior](docs/identity.md).

## Development

Requires Python 3.13+ and uv 0.11.26:

```sh
bash scripts/check-package.sh
```

The script runs locked source tests, builds wheel/sdist distributions, verifies
all runtime files in both wheels, and repeats the tests in a fresh environment
outside the checkout against the wheel and an sdist-rebuilt wheel.
No service checkout, private dependency or credential is needed.

Wallet tests use mocked RPC responses. They do not establish live Base or validator
acceptance. Integration with service configuration and separately owned legacy
`api.*` aliases requires consumer integration checks.

Public module contracts are recorded in `contracts/identity.json`. Package version
and public-contract version are separate. Review contract compatibility when
changing public modules, session scope or wallet-verification behavior.

CI runs the same checks on isolated GitHub-hosted Ubuntu workers for pull requests,
main and manual runs. It uses read-only contents and pinned actions, with no
service secrets or deployment credentials.

## Release channels

Main validation retains its exact qualified files in Actions artifacts. It does
not create GitHub releases or tags. Historical `test-<commit>` prereleases remain
qualification evidence and do not establish an accepted stable release.

Stable publication requires an explicit `vMAJOR.MINOR.PATCH` tag, the exact
successful main validation artifact, compatible declared contracts and an actual
immutable stable baseline. The publisher independently verifies that evidence;
successful caller jobs alone cannot establish acceptance. Missing evidence and
first-stable bootstrap remain closed. Package qualification, coordinated consumer
acceptance and runtime deployment remain separate.

## Account lifecycle authority

The closure contract includes purpose-separated lifecycle service
credentials, canonical tenant-bound denial digests, explicit offline gateway
context and fail-closed retirement/permit/scope checks. Enforcement stays off
unless ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED is explicitly true. Native Keycloak,
tenant-session and host-setup validation consult retirement authority when enabled.
A dedicated native closure operator grant requires the configured client list,
spanopticon-account-closure audience and account:close role; ordinary application,
API-key, worker and reader identities do not substitute for that authority.

Package checks exercise these boundaries from source, installed wheel and rebuilt
sdist. General interactive sign-in age policy is not changed by this adoption;
the dedicated closure operator validation preserves its source age proof.

Closure adoption retains version 0.15.0. Current wheel/contract evidence is
regenerated from the corrected source; historical accepted records remain
unchanged. Runtime-byte differences do not authorize a release-line change.
Closure remains default-off and provider readiness is separate.

## Test qualification and stable acceptance

GitHub `test-<commit>` prereleases are development snapshots. Their embedded
package version does not reserve a stable version. Artifact and consumer evidence
belongs under `releases/qualification`. Owning-package and artifact validation
remain separate from stable release admission. Future test receipts must carry
an explicit non-stable classification.

`releases/accepted` and `SPANOPTICON_RELEASE_BASELINE_SHA` are reserved for an
actual immutable stable GitHub release. The pinned shared guard verifies the live
release channel, stable tag source and asset digests; a test snapshot cannot
become accepted through a provenance label. No stable baseline is recorded until
that release exists. Stable publication remains closed without a valid baseline;
first stable bootstrap and coordinated release qualification remain separate.
No stable version, approval prerequisite or deployment is introduced here.


### Published stable distribution

The accepted record binds the existing immutable `v0.24.0` release to its actual
GitHub release ID, source revision and published asset digests. Test snapshots
remain under `releases/qualification` and do not establish stable acceptance.
Runtime deployment and coordinated consumer acceptance remain separate.

### Actions qualification and stable publication

Main merges and workflow completion do not publish GitHub test releases. Exact
qualification files remain in Actions artifacts with finite retention. The pinned
publisher independently verifies a real immutable stable baseline and refuses
qualification snapshots, even if a caller job reports success. Existing valid
stable records are retained; no release, version change, deployment or human
approval prerequisite is introduced by this correction.

## License

This package is licensed under [Apache-2.0](LICENSE). Dependencies retain their
own licenses; this declaration does not relicense bundled third-party material.

## Interactive age-confirmation regression ownership

The ordinary Keycloak token validator now applies the same age-confirmation
policy as the dedicated closure validator. Four interactive clients require
positive age evidence; machine clients and explicitly classified service accounts
retain their existing exemption. Audience, issuer, client allowlist and retirement
checks remain in place. Seven cases transferred from Panopticon's edge suite run
here against source, installed wheel and rebuilt sdist, with matching inventories
and no skips. The provenance record names the immutable original source.
Consumers pinned to older identity commits still require a separately qualified
pin update; this owner change does not update their runtime automatically.

## Coordinated test bundles

This service opts into the `next: 0.24.0` train through
[.github/test-channel.json](.github/test-channel.json). Successful main validation
publishes its exact retained `tested-dist` files as immutable `0.24.0-test.N`
prerelease bundles. The pinned publisher verifies the run, source revision,
configuration and original Actions artifact digest without executing caller code
or receiving private dependency credentials. PRs validate without publication.

This test-channel authorization supersedes the older main-publication restriction
above. Package versions, dependency pins and accepted package baselines stay
unchanged; existing stable package admission remains separate. Coordinated
consumer/deployment selection must bind exact component commits and artifact
digests, not matching repository-local counters. No stable promotion is automatic.
Private jobs use debrunners and public jobs use hosted Ubuntu; no approval gates
are introduced. Missing original evidence or publication collisions fail closed.
