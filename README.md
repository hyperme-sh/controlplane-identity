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

Successful main-push validation retains the validated Python wheel and source distribution and publishes
an immutable `test-<commit>` GitHub prerelease. Push a `vMAJOR.MINOR.PATCH`
tag at that tested commit to promote the exact files to a stable release,
without rebuilding. Repository visibility applies to all package assets.
Package metadata versions are preserved; these are GitHub distribution snapshots,
not automatic PyPI publication or service deployment.

Promotion requires the original Actions artifact (90-day requested retention;
organization policy may shorten it). Expired evidence fails closed: validate a
new main revision. The publisher verifies the run, source, workflow and artifact
digest independently of release metadata. Repository immutable releases must be
enabled. See the [shared release contract](https://github.com/hyperme-sh/.github/blob/7749591fccd30d46ba9b0adabe82114001c9d0de/actions/release-channel/README.md).

## Account lifecycle authority

The additive contract version 0.24 includes purpose-separated lifecycle service
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

Closure adoption is rebased onto the published 0.24 owner history. The candidate
contract binds the newly built development snapshot; accepted baseline files
remain unchanged. This is code/package qualification, not permission to replace
the accepted 0.24.0 artifact or bypass version/compatibility admission. A future
release still requires coordinated version selection and the existing admission
checks. Closure remains default-off.
