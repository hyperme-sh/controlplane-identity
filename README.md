# controlplane-identity

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

Closure adoption uses release version 1.0.0 on line 1.0. The conservative release
contract covers every packaged runtime byte; it cannot certify changed identity
code as a patch or minor release. The major version records that compatibility
boundary without replacing the immutable accepted 0.24.0 artifact or weakening
admission. Candidate metadata is regenerated from the exact built wheel; accepted
baseline files remain unchanged. This version does not establish production or
provider readiness. Closure remains default-off, and consumers must adopt the
new immutable revision and qualify their own behavior.

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
