# Identity destination guidance

Read README.md and docs/identity.md. Runtime code is in src/controlplane_identity.
The historical contract snapshot is contracts/source-identity.json; its legacy
api.* aliases belong to controlplane-core, not this distribution.

Preserve the imported runtime bytes and package version during extraction.
SOURCE-MANIFEST.json records exact-source provenance. For intentional future
behavior changes, review the public contract and update provenance explicitly;
do not silently regenerate hashes to bypass the extraction check.

Run bash scripts/check-package.sh. Tests must pass with an installed wheel outside
the checkout as well as from source. Consumer/legacy alias integration is separate.

New component CI uses ubuntu-24.04, exact action SHAs, read-only contents and no
deployment credentials. Keep Actions disabled until Infra's isolation policy and
live audit cover this destination. Historical monorepo runner guidance does not
apply to this destination.
