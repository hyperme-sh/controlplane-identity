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
enabled. See the [shared release contract](https://github.com/hyperme-sh/.github/blob/3352fb1347e7920ec1d5cd14792ba3038a81abcb/actions/release-channel/README.md).
