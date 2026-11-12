# controlplane-identity

Python library for identity checks in the Hypermesh control plane. It compares
internal service tokens, validates API keys and Keycloak access tokens, mints
and checks purpose-bound session JWTs, and verifies Base wallet proofs. Callers
keep their own settings, lease tickets, SIWE challenges, and database writes.

## Why

Hosts, renters, and operators reach the control plane with different
credentials: a browser login, a renter API key, a host-setup device token, and
a wallet signature that binds a payout address. The control-plane edge, the
Hypermesh gateway, auth, and api-keys-service have to apply the same rules to
those credentials. This package is that shared implementation. An API-key
session, a tenant session, and a host-setup session each carry their own issuer
and purpose, so a token minted for one path fails closed on the others.

## How it works

Import the library and call `configure_identity` once, before any JWT or API-key
helper. Unconfigured calls raise `RuntimeError`. Hypermesh does this from
`controlplane-api` settings at process start. The library runs inside that
process.

This section describes the source tree on this branch, package **0.15.0**.
The published `v0.24.0` wheel is an earlier build. Interactive age confirmation
and account retirement, both described below, are in this tree and absent from
that wheel. The install section lists the exact checks.

| Module | Responsibility |
| --- | --- |
| `configuration` | Process-wide Keycloak URLs, client allowlists, API-key exchange secret, and internal token |
| `internal_token` | Constant-time compare of the `X-Internal-Token` header |
| `api_keys_client` | `POST {base}/api/v1/internal/validate` on api-keys-service |
| `security.keycloak_jwt` | RS256 access tokens via JWKS, plus dedicated host-setup and account-closure checks |
| `security.api_key_exchange_jwt` | 300-second HS256 session after a key validates (`spanopticon_auth=api_key`) |
| `security.tenant_session_jwt` | 900-second tenant session, and a separate 900-second host-setup session |
| `portal_controls` | Org and group grants for host, renter, billing, and IR |
| `person_bind` | Person and checkout subject from token claims |
| `account_lifecycle` | Optional retirement checks against the account-closure guard |
| `wallet` | EIP-191 personal-sign proofs on one configured Base chain |

Session issuers are fixed:

- API-key exchange: `https://spanopticon.internal/api-key`
- Tenant session: `https://spanopticon.internal/tenant-session` (`spanopticon_auth=tenant_session`)
- Host setup: `https://spanopticon.internal/host-setup`, audience `hypermesh-host-setup`, claim `purpose=host_setup`

The host-setup session carries subject, email, and tenant. Roles, permissions,
and groups stay off that token. `try_decode_tenant_session_jwt` returns `None`
for it, and `mint_tenant_session_jwt` refuses `azp=hypermesh-host-setup`.

Keycloak validation is RS256 against the configured issuer, audience set, and
`azp` allowlist. `validate` rejects the host-setup client. `validate_host_setup`
accepts that client only when audience and `azp` are both `hypermesh-host-setup`.
Interactive clients `controlplane-frontend`, `controlplane-mobile`,
`controlplane-device`, and `hypermesh-native` need a positive integer
`terms_and_conditions` timestamp. Tokens with `account_type=service` skip that
check.

Portal groups are `host`, `renter`, `billing`, `ir`, and `ir_export`. Keycloak
paths such as `/org/renter` and labels such as `Billing Group` normalize to
those names. Realm roles `billing_manager`, `ir_door`, and `ir_receipts` map
onto billing, IR, and IR export.

| Grant | Who receives it |
| --- | --- |
| Checkout and lease visibility | `renter` |
| Host status | `host` |
| Mint API keys | `admin`, `billing`, or `renter` |
| Invite members and assign groups | realm role `admin` |
| IR door | `admin` or `ir` |
| IR receipt export | `admin` or `ir_export` |

Checkout stays on the `renter` group and host status stays on the `host` group,
including for callers who also have the `admin` role. Checkout and billing
subjects come from the token `sub` (`uuid_from_sub`). `client_metadata_without_retarget`
removes client-supplied `lease_id` and `listing_id` before settlement, which
keeps a request on the lease the server already chose.

`BaseWalletVerifier` accepts Base mainnet (`8453`) or Base Sepolia (`84532`).
It checks `eth_chainId`, pins `eth_getCode` and `eth_call` to one block, and
uses only those read-only methods. Externally owned accounts recover an
EIP-191 personal signature (low-s, `v` 27 or 28). Contract accounts use
ERC-1271. An ERC-6492 wrapper is forwarded to an operator-configured
`CounterfactualValidator` (`isValidSig`) whose runtime code hash is pinned.
An exact EIP-7702 delegation designator (`0xef0100` plus a 20-byte address)
tries personal-sign recovery and then ERC-1271 on the account. The RPC URL
and validator address are server configuration. A returned checksum address
is evidence of wallet control. The caller still has to parse SIWE, enforce
domain, URI, and expiry, and consume a single-use nonce before it stores a
session or a payout binding.

Account-closure enforcement stays off until
`ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED=true`. When it is on, Keycloak,
tenant-session, and host-setup validation call
`ACCOUNT_CLOSURE_GUARD_URL/api/v1/internal/account-lifecycle/check` with
`X-Account-Lifecycle-Token`. A closure operator token is separate: audience
`spanopticon-account-closure`, an allowlisted `azp`, and realm role
`account:close`. Inside `offline_gateway_verification()`, those token checks
skip the remote guard so the paid gateway can apply its local revocation list.
Guard and operations tokens are different secrets of at least 32 ASCII
characters.

Public module shapes are recorded in `contracts/identity.json` (contract
version `1.0.0`, independent of the package version). Verification details are
in [docs/identity.md](docs/identity.md). Legacy `api.*` import paths live in
[`controlplane-core`](https://github.com/hyperme-sh/controlplane-core), not in
this wheel. The optional
[`controlplane-legacy-auth-bridge`](compatibility/README.md) package accepts
older Auth credentials only when the process sets
`CONTROLPLANE_ACCEPT_LEGACY_AUTH=1`.

## Practical use

The package on this branch is `controlplane-identity` **0.15.0**. It requires
Python 3.13 or newer and installs `fastapi>=0.135.0`, `httpx>=0.28.1`,
`pyjwt[crypto]>=2.10.1`, `eth-account>=0.13.0`, `eth-abi>=5.0.0`,
`eth-utils>=5.0.0`, and `eth-keys>=0.7.0`. It is not on PyPI.

Work from this tree with uv 0.11.26 (the version CI installs):

```sh
git clone https://github.com/hyperme-sh/controlplane-identity.git
cd controlplane-identity
uv sync --frozen
```

The accepted stable wheel is package **0.24.0**, published on the
[`v0.24.0`](https://github.com/hyperme-sh/controlplane-identity/releases/tag/v0.24.0)
release from revision `74857a6e3b2c22eb1752329693a3f146d9489120`:

```sh
uv pip install \
  "https://github.com/hyperme-sh/controlplane-identity/releases/download/v0.24.0/controlplane_identity-0.24.0-py3-none-any.whl"
```

That revision's wheel contains the checks in the examples below: internal
tokens, API-key validation and exchange sessions, Keycloak RS256 validation
with the audience and `azp` allowlists, host-setup sessions, portal grants,
person binding, and Base wallet proofs. Two checks described above are only
in this source tree:

- **Interactive age confirmation.** On this tree, `validate` and
  `validate_closure_operator` reject `controlplane-frontend`,
  `controlplane-mobile`, `controlplane-device`, and `hypermesh-native` unless
  `terms_and_conditions` is a positive integer timestamp (`account_type=service`
  is exempt). `security/keycloak_jwt.py` at `74857a6e` has no age check, so
  the `v0.24.0` wheel accepts those clients without that timestamp.
- **Account retirement.** This tree provides `controlplane_identity.account_lifecycle`.
  `ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED=true` makes Keycloak validation and
  tenant-session and host-setup decoding call the closure guard.
  `validate_closure_operator` requires audience `spanopticon-account-closure`
  and realm role `account:close`. The `v0.24.0` tree has no
  `account_lifecycle.py` and no `validate_closure_operator`. Setting the
  environment variable in a process that imported that wheel leaves retirement
  enforcement off, because the installed code never reads it.

The examples below use functions that exist on this tree and on the `v0.24.0`
tag. Run them with `uv run python` from the clone after the configuration
object exists. Hypermesh services get that object from `controlplane_api.config`,
which already calls `configure_identity`. A standalone program supplies its own:

```python
from controlplane_identity.configuration import configure_identity

class Settings:
    smoke_session_claim = "smoke_session"
    keycloak_jwks_url = "https://id.example.com/realms/hypermesh/protocol/openid-connect/certs"
    keycloak_issuer = "https://id.example.com/realms/hypermesh"
    keycloak_client_id = "controlplane-frontend"
    keycloak_jwks_request_host = None

    def usable_api_keys_internal_token(self) -> str | None:
        return "replace-with-the-api-keys-service-token"

    def usable_api_key_exchange_secret(self) -> str | None:
        return "replace-with-a-dedicated-hs256-secret"

    def keycloak_allowed_audience_set(self) -> set[str]:
        return {"controlplane-frontend"}

    def keycloak_allowed_azp_set(self) -> set[str]:
        return {
            "controlplane-frontend",
            "controlplane-mobile",
            "controlplane-device",
            "hypermesh-native",
        }

configure_identity(Settings())
```

Internal token compare, portal grants, and the two session types:

```python
import uuid

from controlplane_identity.internal_token import INTERNAL_TOKEN_HEADER, internal_token_matches
from controlplane_identity.portal_controls import evaluate_portal_controls
from controlplane_identity.security.api_key_exchange_jwt import (
    mint_api_key_session_jwt,
    try_decode_api_key_session_jwt,
)
from controlplane_identity.security.tenant_session_jwt import (
    mint_host_setup_session,
    try_decode_host_setup_session,
    try_decode_tenant_session_jwt,
)

assert INTERNAL_TOKEN_HEADER == "X-Internal-Token"
assert internal_token_matches("expected", "expected")
assert internal_token_matches("presented", "expected") is False

renter = evaluate_portal_controls(["renter"], [])
assert renter.can_checkout and renter.can_see_leases and renter.can_mint_keys
host = evaluate_portal_controls([], ["/host"])
assert host.can_see_host_status and host.can_checkout is False

tenant_id = uuid.uuid4()
api_token = mint_api_key_session_jwt(
    key_record_id=uuid.uuid4(),
    tenant_id=tenant_id,
    scopes=["marketplace.read"],
)
api_claims = try_decode_api_key_session_jwt(api_token)
assert api_claims["spanopticon_auth"] == "api_key"
assert api_claims["https://spanopticon.dev/tenant_id"] == str(tenant_id)

setup = mint_host_setup_session(
    claims={"azp": "hypermesh-host-setup", "sub": "host-user", "email": "host@example.com"},
    tenant_id=tenant_id,
)
assert try_decode_host_setup_session(setup)["purpose"] == "host_setup"
assert try_decode_tenant_session_jwt(setup) is None
```

API-key validation calls api-keys-service. `None` means the internal token is
unset, the HTTP call failed, or the service did not return `valid: true`. A
truthy result already means the key belongs to `tenant_id`:

```python
import uuid
from controlplane_identity.api_keys_client import validate_api_key_remote

record = await validate_api_key_remote(
    base_url="http://api-keys-service:8000",
    api_key="prefix.secret",
    tenant_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
)
```

Keycloak access tokens:

```python
from controlplane_identity.security.keycloak_jwt import get_keycloak_jwt_validator

validator = get_keycloak_jwt_validator()
claims = await validator.validate(access_token)
setup_claims = await validator.validate_host_setup(host_setup_access_token)
```

Wallet proof. Chain id `1` is refused before any RPC. A real proof uses the
operator RPC URL (auth-service reads `AUTH_SIWE_BASE_RPC_URL`) and the message
the service issued:

```python
import httpx
from controlplane_identity.wallet import BaseWalletVerifier, WalletProofError

async with httpx.AsyncClient() as client:
    verifier = BaseWalletVerifier(
        chain_id=8453,  # 84532 is Base Sepolia
        rpc_url="https://base-rpc.example",
        client=client,
    )
    signer = await verifier.verify_personal_signature(
        address="0x1111111111111111111111111111111111111111",
        message=siwe_message_issued_by_the_service,
        signature=signature_bytes,
        chain_id=8453,
    )
```

Any chain other than 8453 or 84532 fails in the constructor, before an RPC
call:

```python
import httpx
from controlplane_identity.wallet import BaseWalletVerifier

try:
    BaseWalletVerifier(
        chain_id=1,
        rpc_url="https://base-rpc.example",
        client=httpx.AsyncClient(),
    )
except ValueError as exc:
    print(exc)  # Configure Base mainnet (8453) or Sepolia (84532)
```

`WalletProofError` covers a chain mismatch, a bad signature, an unexpected RPC
response, and a contract wallet that rejects the proof. Tests in this
repository mock those RPC responses.

## How Hypermesh uses it

`controlplane-api` builds one settings object and calls `configure_identity`
at import. Edge, gateway, auth, user-service, and api-keys-service then share
that process configuration. `controlplane-core` re-exports these modules under
the historical `api.*` names so existing services keep one implementation.

**Control-plane edge.** `GatewayAuthMiddleware` handles REST and GraphQL.
A browser or device bearer is a Keycloak access token. An `X-Api-Key` header
is posted to api-keys-service `/api/v1/internal/validate` with
`X-Internal-Token`, then exchanged for the 300-second API-key session so
downstream routes see an access token. Tenant id is `https://spanopticon.dev/tenant_id`
or `tenant_id` on the claims. Service-to-service routes use
`request_has_internal_token`. Host setup is limited to its own routes:
`GET /auth/host-setup/me`, `POST /auth/host-setup/enrollment/grant`, and
`POST /auth/host-setup/session` require `validate_host_setup`. Host
registration and onboarding (`POST /api/v1/hypermesh/host-registrations`,
registration complete, `approve-activation`, and `approve-resume`) require the
host-setup session. Opaque `hm_site_` tokens are left for hypermesh-service.

**Hypermesh gateway.** Renter chat accepts a portal JWT or an API key, and
still requires a signed lease ticket (`hm1`, from
[hypermesh-ticket](https://github.com/hyperme-sh/hypermesh-ticket)). This
library leaves lease payment on the ticket. `verify_jwt_locally` accepts an
API-key exchange JWT or a Keycloak access token and checks the access token
with the cached JWKS. An agent key
(`prefix.secret`, bearer or `X-Api-Key`) is checked with `validate_api_key_remote`
against `HYPERMESH_API_KEYS_URL` (default `http://api-keys-service:8000`). The
key tenant must match the ticket tenant. Completions do not import portal
controls and do not call api-keys-service. Host device secrets (`hm_dev_`),
gateway secrets (`hm_gw_`), and site tokens (`hm_site_`) are rejected as renter
identity.

**auth-service.** Wallet binding issues a SIWE nonce for the signed-in Keycloak
subject, then `BaseWalletVerifier` checks the personal signature on the
configured Base chain. The RPC URL and optional ERC-6492 validator come from
`AUTH_SIWE_BASE_RPC_URL`, `AUTH_SIWE_6492_VALIDATOR_ADDRESS`, and
`AUTH_SIWE_6492_VALIDATOR_CODE_HASH`. The stored row is the checksum address.
Connect-session payout facts take tenant authority from a tenant-session JWT
and authentication time from a live introspection of the browser OIDC token.

**api-keys-service and user-service.** Internal validate routes require
`internal_token_matches` against the configured service token. Mint and revoke
use `can_mint_keys` from portal controls. The user service evaluates the same
controls for the portal membership tree: a renter checks out and sees leases,
a host sees host status, and an org admin invites and assigns groups.

**Lease subject.** Checkout and billing take the person from the token `sub`.
Client metadata is passed through `client_metadata_without_retarget` so a
request cannot retarget `lease_id` or `listing_id`.

## Develop and test

Python 3.13+ and uv 0.11.26:

```sh
bash scripts/check-package.sh
```

The script checks `uv.lock`, runs the suite from source, builds the wheel and
sdist, checks packaged runtime files against the source tree, and repeats the
tests in a fresh environment outside the checkout against the wheel and a wheel
rebuilt from the sdist. No service checkout or private dependency is required.
Wallet tests use mocked RPC responses. Behavior that depends on service
settings or legacy `api.*` aliases is covered in the consumer repositories.
See [docs/identity.md](docs/identity.md) and `contracts/identity.json`.

Pull requests, pushes to `main`, and manual runs execute
[`.github/workflows/package.yml`](.github/workflows/package.yml) on Ubuntu
24.04 with read-only contents. A push to `main` also uploads the built
distributions as the `tested-dist` artifact (90-day retention).

## Release and versioning

This branch packages `controlplane-identity` **0.15.0**. The import contract
in `contracts/identity.json` is version **1.0.0**. The
[`v0.24.0`](https://github.com/hyperme-sh/controlplane-identity/releases/tag/v0.24.0)
GitHub release is the accepted stable wheel (package 0.24.0). Main validation
can publish prerelease bundles named `0.24.0-test.N`; the wheel inside keeps
the package version that was built (`0.15.0` in `0.24.0-test.0`). Channels,
admission, and the accepted record are described in
[docs/releasing.md](docs/releasing.md).

## License

This package is licensed under [Apache-2.0](LICENSE). Dependencies retain their
own licenses.

The `startup` module validates a private deployment envelope containing the
unchanged canonical binding, its SHA-256, and separate owner profile/network and
Keycloak broker settings. `validate` returns a detached normalized mapping;
`fingerprint` covers the whole mapping. `binding_fingerprint` covers canonical
binding JSON with its trailing newline. `load` requires a bounded private regular
file owned by the process, without symlinks or additional hard links.

`verify_claims` selects the configured account from already verified Keycloak
broker claims. It uses the configured broker alias and immutable Entra tenant
and object IDs, never email or token roles. Raw Entra ID tokens use
`EntraAccountBinding` instead. Neither matcher authenticates a token, proves
possession of the configured SEA key, grants roles, or provisions a person.
Owners must reject unsupported tenant scopes before writes and read explicit
organization roles and each platform/Keycloak admin flag independently.
