# Legacy Auth transition

This optional distribution bridges deployed Panopticon Auth credentials to
standalone consumers. It is separate from the canonical identity wheel and its
accepted contract. Canonical validators and token minting remain unchanged.

Services must explicitly import `controlplane_legacy_auth_bridge` and set
`CONTROLPLANE_ACCEPT_LEGACY_AUTH=1`. Otherwise only canonical credentials work.
The transition uses the configured non-default API-key exchange secret, HS256,
exact legacy issuers, credential kinds and tenant binding. Verified legacy claims
retain their original issuer and authorization grants; only the canonical auth
marker and tenant namespace are supplied to consumers. No JWT is re-signed.
Host-setup credentials require their exact audience and purpose and cannot carry
roles, permissions or groups. Conflicting tenant aliases or auth namespaces fail.

Enable this only for a named deployment with an existing legacy Auth producer.
Remove the deployment opt-in after Auth and callers issue canonical credentials,
then remove this dependency from consumers. Never use it to bypass membership,
interactive login, smoke-session, purpose or tenant checks.
