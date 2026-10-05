# controlplane-identity

Shared internal-token comparison, person/portal permissions, API-key validation,
Keycloak validation and purpose-bound session tokens. Public modules are declared
in `scripts/import_boundaries.json` and `scripts/ownership.json`.

The package has no dependency on `api` or product implementations. An application
calls `controlplane_identity.configuration.configure_identity(settings)` before
using configured JWT or API-key operations. The settings object implements
`IdentitySettings`; existing secret rejection, audience/client allowlists and
host-setup purpose checks are preserved. Unconfigured operations fail rather than
using credential defaults. The legacy `api.core.config` performs this binding
for current services.

Legacy modules alias the shared implementation, preserving module monkeypatches,
validator caches and callers that still use `api.*`. Public source contracts use
the workspace's 0.9.0 train. No public publication is performed here.
