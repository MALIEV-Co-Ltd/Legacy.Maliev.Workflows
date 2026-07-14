# Legacy.Maliev.Workflows

Reusable CI/CD and publication gates for services migrated from the private MALIEV legacy monorepo into fresh public repositories.

## Trust boundaries

Pull-request validation is fork-safe and secretless. It runs with read-only repository contents, never uses `pull_request_target`, and receives no environment secret, cloud identity, package-write permission, GitHub App token, or personal access token. Validation may build, test, format, audit dependencies, scan for secrets, and scan containers; it cannot publish or deploy.

Deployment is a separate trusted boundary. Image publication and GitOps handoff may run only for a push to protected `main`, after the exact commit has passed its required validation check. Deployment jobs bind to a protected GitHub environment and use least-privilege OpenID Connect federation. Service repositories hand an immutable image digest to `maliev-gitops`; they do not run `kubectl`, Helm, or Argo commands against the cluster.

## Public history contract

Every consumer repository must be named `Legacy.Maliev.*` and start from a clean export with a new root commit. The private `maliev-web` `.git` directory, remotes, historical objects, credentials, generated secret material, backups, archives, dumps, and local environment files must never be copied. Any credential encountered during extraction is treated as compromised and rotated before publication.

## Cost boundary

This standard uses public GitHub Actions and existing MALIEV infrastructure. It creates no new billable Google Cloud resource, cluster, node pool, load balancer, or hosted runner. Migrated workloads remain in the existing `maliev-legacy` namespace and use the existing secret-delivery boundary.

## Consumer interfaces

The repository will expose these immutable, SHA-pinned interfaces:

- `.github/workflows/dotnet-validate.yml`: reusable .NET 10 validation for self-contained services, accepting `solution`, `working-directory`, and `dotnet-version`.
- `actions/dotnet-validate/action.yml`: composite validation for callers that first check out service-specific sibling dependencies.
- `.github/workflows/publish-image.yml`: trusted image build, scan, and publication through Workload Identity Federation, returning an immutable `sha256` digest.
- `actions/gitops-handoff/action.yml`: secretless composite handoff of one validated image digest to a pull request in `MALIEV-Co-Ltd/maliev-gitops`.
- `scripts/Test-LegacyPublication.ps1`: fail-closed local gate for a fresh-history public repository candidate.
- `scripts/Publish-LegacyRepository.ps1`: publication, protection, and GitHub setting readback after the local gate succeeds.

Consumers must reference shared actions and reusable workflows by a complete 40-character commit SHA, never by a branch or floating tag. Shared workflows and actions store no service or deployment credential. The GitOps composite action accepts a token only from the service-owned job that invokes it. That caller job must bind its own protected deployment `environment`, restrict execution to protected `main`, and pass its environment-scoped secret explicitly.

## GitOps handoff adoption

Contract `v1` initially allowlists only this established mapping:

```text
Legacy.Maliev.CountryService
  -> 3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml
  -> image entry legacy-maliev-country-service
```

That dormant path is not yet present on `maliev-gitops` main. The GitOps adoption task must land and validate the dormant manifest before enabling a service caller. Until then, the action fails closed because its allowlisted target does not exist.

A service repository owns the protected environment and thin caller job:

```yaml
jobs:
  gitops-handoff:
    needs: publish
    if: >-
      github.ref == 'refs/heads/main' &&
      github.ref_protected == true &&
      (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
    environment: production
    runs-on: ubuntu-24.04
    permissions:
      contents: read
    steps:
      - name: Hand immutable digest to GitOps
        uses: MALIEV-Co-Ltd/Legacy.Maliev.Workflows/actions/gitops-handoff@<40-character-commit-sha>
        with:
          service: Legacy.Maliev.CountryService
          image: asia-southeast1-docker.pkg.dev/example/legacy-maliev-country-service
          digest: ${{ needs.publish.outputs.digest }}
          gitops-path: 3-apps/_legacy-country-service/overlays/legacy/kustomization.yaml
          token: ${{ secrets.GITOPS_TOKEN }}
```

The action reports `changed=false` and `status=no-op` when the requested digest is already present; in that state it does not create a branch, push, or open a pull request. Unknown services and contract versions require an explicit reviewed allowlist update.

The caller token must be limited to `MALIEV-Co-Ltd/maliev-gitops` with only repository **Contents: read and write** and **Pull requests: read and write** permissions. It needs no workflow, administration, organization, package, or cluster permission. Checkout uses the token with credential persistence disabled; push receives an ephemeral per-command authorization header, `gh` receives `GH_TOKEN` only for its PR command step, and the action verifies that neither Git credential configuration nor an authenticated remote URL remains afterward.

## Repository contract

Run the executable source contract with:

```powershell
dotnet test .\Legacy.Maliev.Workflows.slnx
```

During initial construction, this contract intentionally remains red until the required workflows, scripts, and Dependabot configuration are implemented in later validated slices.
