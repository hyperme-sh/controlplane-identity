# Identity publication preparation

The owner remains Apache-2.0, version 0.15.0. LICENSE and NOTICE are checked
against the source in original and rebuilt wheels. Authentication, session
validation and wallet behavior are unchanged.

CI prepares a non-root consumer image under
`ghcr.io/hyperme-sh/controlplane-identity/runtime` from qualified package bytes
and hashed public dependencies. It includes installed dependency license texts
and a version/hash index, but no third-party source archives. Missing license
texts fail preparation. The image is inspected across every layer for hosted
content and secrets; offline checks compare installed runtime and legal bytes.
This is a library image with an informational default command, not an identity
server. Successful main CI publishes the qualified image to the moving `runtime:test`
channel, pulls it back, and verifies its exact image identity. Serialized
publication skips stale main revisions using an authenticated fixed-endpoint lookup.

Reachable history scanning includes fetched origin branches, tags and HEAD,
including bounded ZIP/wheel members. Old code is never executed. Deleted or
hidden refs, external archives and remote LFS data are outside this scan. Findings
remain a review queue, not publication clearance. Secret exceptions must bind
exact bytes and scanner coordinates; no history is rewritten.

GHCR uses the moving TEST channel. Integration/e2e remains nightly.
No Actions uploads, visibility changes or manual releases are introduced.

Initial CI reviewed 348 reachable commit/tag/blob objects with zero hosted-content
matches. Its 24 secret-scanner matches were runtime source hashes in historical
contract manifests, each verified against a reachable source blob. Exceptions
bind exact exported bytes, scanner rule and line coordinates. No broad path
exceptions were added. The image retains legal texts for 38 installed
distributions; owner and dependency notices are checked in the final image.

Retained-image review inventories both tags and untagged retained GHCR versions,
then inspects every Linux amd64 layer without executing old images. Unavailable
registry access is reported explicitly, never treated as proof of absence.
After publication, strict inventory and retained-layer scans must succeed.
Deleted images and other registries remain outside this review.
