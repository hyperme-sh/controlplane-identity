# controlplane-identity

Shared internal-token comparison, person/portal permissions, API-key validation,
Keycloak validation and purpose-bound session tokens. Public module contracts are
recorded in `contracts/identity.json`.

The package has no dependency on `api` or product implementations. An application
calls `controlplane_identity.configuration.configure_identity(settings)` before
using configured JWT or API-key operations. The settings object implements
`IdentitySettings`; existing secret rejection, audience/client allowlists and
host-setup purpose checks are preserved. Unconfigured operations fail rather than
using credential defaults. The `controlplane_api.config` (also aliased as `api.core.config`) performs this binding
for current services.

Legacy modules alias the shared implementation, preserving module monkeypatches,
validator caches and callers that still use `api.*`. These aliases are supplied
by the separate compatibility package and are not part of this distribution.

## Base wallet proof verifier

`controlplane_identity.wallet.BaseWalletVerifier` verifies EIP-191 personal-sign
proofs against one operator-configured Base chain: 8453 or 84532. It checks the RPC
chain ID and pins contract reads and calls to one block. EOAs use signature
recovery; deployed wallets use ERC-1271. ERC-6492 wrappers are handled first and
forwarded unchanged to an operator-reviewed universal validator implementing
`isValidSig(address,bytes32,bytes)`. Configure its address and expected runtime
code hash through `CounterfactualValidator`; without that configuration wrappers
fail closed. The validator must implement deployment/preparation simulation for
both deployed and counterfactual wallets. This package does not deploy it.

Only read-only RPC methods are used, with bounded time, signature/message size
and contract-call gas. RPC URL and validator configuration belong to the server,
never the submitted proof. Validator acceptance tests use mocked RPC responses;
real validator and Base integration acceptance remain pending.

Services own challenge construction, SIWE parsing/domain/URI/time checks,
single-use nonce consumption, subject/purpose binding and verified-address session
or payout persistence. They must validate the signed challenge's chain against the
configured chain before calling the verifier. A successful signature is evidence
of wallet control, not a session or payout authorization.

An exact EIP-7702 delegation designator (`0xef0100` followed by a 20-byte
address) permits personal-sign recovery for the account's own key. If recovery
does not match, verification falls back to ERC-1271 on the account address, not
the delegate address. Other nonempty code always uses ERC-1271. ECDSA recovery
accepts only low-s signatures with wallet-standard v=27/28; contract proofs retain
their original bytes and contract-defined validation rules.
