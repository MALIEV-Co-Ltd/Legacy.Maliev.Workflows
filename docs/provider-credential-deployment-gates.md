# Provider credential configuration and release gates

The source change [c5fe0e4446f4bf96917d6d1e2a84216f9ea0bea3](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/c5fe0e4446f4bf96917d6d1e2a84216f9ea0bea3), parent `e2fbd8e608748bf6f9f1e58824beb41cd1b0f379`, removed embedded provider credentials and added configuration, scanning and operational gates. This document adapts its deployment-gate documentation to the split repositories. It does not authorize credential rotation, application deployment, provider traffic or source retirement.

## NotificationService configuration

The old EmailService key was `Email:Brevo:ApiKey` (`Email__Brevo__ApiKey` in environment variables). Legacy.NotificationService binds `Brevo:ApiKey`; supply it externally as `Brevo__ApiKey`, using the owner's approved secret provider. This describes the current binding, not an added alias for the old key. Keep required sender identities configured through the existing `Brevo:Senders` options.

When the Brevo provider is selected, the provider key must be nonblank. NotificationService validates its options at startup; an absent or blank key must fail configuration rather than fall back to a tracked resource. The separately selected Development recording provider does not establish real provider configuration or delivery. The existing NotificationService acceptance of the Brevo configuration behavior is separate from actual provider delivery or acceptance of another consumer's configuration.

Do not place provider keys or client credentials in `.resx`, generated resource comments, generated XML documentation, appsettings, deployment manifests or images. Do not copy historical resource files into a split repository. Preserve the separately approved runtime permissions, sender configuration, retry limits and delivery gates.

## Release and rotation sequence

An authorized operator must provision the external replacement and verify the intended workload uses it before removing the old provider credential. Verify the actual provider request only within separately authorized operational work. Once the replacement is verified, revoke or rotate previously exposed provider credentials through the approved provider process. Removing a value from current source does not revoke it, rewrite Git history or prove a live replacement works.

Scans, unit tests and a passing hosted validation job establish their bounded code and inspection contracts. They do not prove deployment, production configuration, provider delivery or credential rotation.

## Shared scanner contracts

The reusable `dotnet-validate.yml` workflow and `actions/dotnet-validate` composite invoke the trusted resource scanner and current-tree scanner before restore. Consumers must pin a reviewed full Workflows commit SHA. Each caller must retain its own exact-pin and native execution evidence; shared workflow tests do not prove adoption by every split repository.

`scripts/Invoke-JwtSigningResourceScan.ps1` enumerates the caller's entire tracked Git tree, including when invoked from a subdirectory. `scripts/JwtSigningResourceScanner.ps1` rejects provider API/client credential resources, generated resource comments and generated XML summaries without printing the value. Malformed `.resx` input and unreadable resource inputs fail closed. Generated XML documentation is inspected with bounded regular expressions; oversized XML input or an inspection failure also fails closed. `tools/security/current_tree_secrets.py`, invoked through `scripts/Invoke-CurrentTreeCredentialScan.ps1`, separately inspects the current tracked tree for its supported credential formats. No historical inline exemption or broad configuration allowlist is inherited.

Existing provider-resource publication tests cover rejected `.resx`, generated XML and generated comments plus permitted nonsecret metadata. Existing caller-scope tests execute the real shared caller steps for provider and JWT resources outside a nested working directory. These tests preserve the separation between scanner detection, service configuration and operational release gates.

## PayPal and other source obligations

The historical source document temporarily described external PayPal sandbox/live client configuration. Later source [f79657bdd06b878dc99fe45fbf26c40eeffb25f0](https://github.com/MALIEV-Co-Ltd/maliev-web/commit/f79657bdd06b878dc99fe45fbf26c40eeffb25f0) removed retired provider remnants and that deployment-gate section. This document does not restore a PayPal integration or authorize its activation. Explicit per-path retirement approval remains a separate MigrationTracking obligation; a source classification label or absence of a target caller is not that approval.

This provider slice does not dispose of other wave0 database, JWT, reCAPTCHA, Google Cloud Storage or Maps configuration obligations. Their producer, consumer and operational acceptance remains with the existing owners. Migration counts and whole-source disposition are recorded only in Legacy.Maliev.MigrationTracking.
