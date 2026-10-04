"""Bounded command-level tests for the source export validator; no SDK or Docker."""
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate-host-dependency-context.py"
CALLER = "ff8fcf61684566b150fe06d88f2ee0c41bc6a33f"
REQUIRED = ["nuget.config"] + [f"Legacy.Maliev.AccountingService.{p}/Legacy.Maliev.AccountingService.{p}.csproj" for p in ("Api", "Application", "Domain", "Data")] + [f".dependencies/Legacy.Maliev.{p}/src/Legacy.Maliev.{p}/Legacy.Maliev.{p}.csproj" for p in ("ServiceDefaults", "CompatibilityContracts")]
IDENTITIES = dict(sourceBase=CALLER, publisherHead="e3a6093324a24968876782153286f52db8b29fd8", defaultsHead="8f4f5f27b226ffe406c4c79b1903742e8c2e7dd3", defaultsTree="2b02094f45bcd3ac112a2c6da66dc2a4bb6994c0", contractsHead="78e48ffc4ee000df0510cba5e7c7a3c4c4d539d7", contractsTree="b8172e57562f2e276554e47d4fa0964736c8cbe8", dockerfileSha256="2150a1d560902ed683a3e0c9aa39c8572a66c3dd48fb1e8b404451feab860fcc", policySha256="5984866d3f136fd22a64d3147c942eac8423638bf2f5703232c2d11cc1ed0db5")


class ContextTests(unittest.TestCase):
    def probe(self, mutate=None, extra=(), missing=None, raw=None, manifest_raw=None, stage=False):
        with tempfile.TemporaryDirectory(prefix="workflows-accounting-python-") as directory:
            archive = pathlib.Path(directory) / "context.tar"
            provenance = pathlib.Path(directory) / "provenance.json"
            data = b"owned-source-canary"
            manifest = dict(schemaVersion=1, profile="accounting-host-dependencies-v1", callerHead=CALLER, **IDENTITIES,
                            requiredSources={p: hashlib.sha256(data).hexdigest() for p in REQUIRED})
            if mutate:
                mutate(manifest)
            provenance.write_text(manifest_raw or json.dumps(manifest), encoding="utf-8")
            with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as writer:
                for path in REQUIRED:
                    if path != missing:
                        member = tarfile.TarInfo("context/" + path)
                        member.size = len(data)
                        writer.addfile(member, io.BytesIO(data))
                for member, content in extra:
                    writer.addfile(member, io.BytesIO(content) if content else None)
                if stage:
                    fixtures = ROOT / "tests/fixtures/accounting-context"
                    for source, target in [("accounting.dockerignore", ".dockerignore"), ("Accounting.Api.Dockerfile", "Legacy.Maliev.AccountingService.Api/Dockerfile")]:
                        content = (fixtures / source).read_bytes()
                        member = tarfile.TarInfo("context/" + target)
                        member.size = len(content)
                        writer.addfile(member, io.BytesIO(content))
            if raw:
                archive.write_bytes(raw(archive.read_bytes()))
            command = [sys.executable, "-B", str(SCRIPT), "--profile", "accounting-host-dependencies-v1", "--caller-ref", CALLER,
                       "--archive", str(archive), "--provenance", str(provenance)]
            if stage:
                command.extend(["--stage-root", directory])
            result = subprocess.run(command, capture_output=True, timeout=5)
            self.assertNotIn(data, result.stdout + result.stderr)
            self.assertNotIn(b"Traceback", result.stdout + result.stderr)
            if stage and result.returncode == 0:
                context = pathlib.Path(json.loads(result.stdout)["stageDirectory"])
                self.assertEqual(pathlib.Path(directory), context.parent)
                self.assertTrue(context.name.startswith("workflows-accounting-context-"))
                self.assertEqual(data, (context / "nuget.config").read_bytes())
                self.assertEqual((ROOT / "tests/fixtures/accounting-context/accounting.dockerignore").read_bytes(), (context / ".dockerignore").read_bytes())
            if stage and result.returncode != 0:
                self.assertEqual([], list(pathlib.Path(directory).glob("workflows-accounting-context-*")))
            return result

    def rejects(self, **kwargs):
        result = self.probe(**kwargs)
        self.assertEqual(1, result.returncode)
        receipt = json.loads(result.stdout)
        self.assertEqual("rejected", receipt["status"])

    def test_accepts_export_without_runtime_claim(self):
        result = self.probe()
        self.assertEqual(0, result.returncode)
        receipt = json.loads(result.stdout)
        self.assertFalse(receipt["provesLockedRestore"])
        self.assertFalse(receipt["provesPinnedDependencyCheckout"])
        self.assertEqual(7, receipt["requiredSourceCount"])

    def test_missing_sources(self):
        for path in REQUIRED:
            with self.subTest(path=path):
                self.rejects(missing=path)

    def test_wrong_identities(self):
        for field in ["callerHead", *IDENTITIES]:
            with self.subTest(field=field):
                self.rejects(mutate=lambda m: m.__setitem__(field, "0" * len(m[field])))

    def test_manifest_controls(self):
        self.rejects(mutate=lambda m: m["requiredSources"].pop(REQUIRED[0]))
        self.rejects(mutate=lambda m: m["requiredSources"].__setitem__(REQUIRED[0], "0" * 64))
        self.rejects(mutate=lambda m: m.__setitem__("unknown", "owned-manifest-canary"))
        self.rejects(manifest_raw='{"schemaVersion":1,"schemaVersion":1}')
        self.rejects(manifest_raw=" " * 65537)

    def test_unsafe_paths(self):
        for name in ["../escape", "/absolute", "context/nested/../../escape", "context/back\\slash", "C:/drive", "context/.git/config", "context/.dependencies/repo/.git/config"]:
            with self.subTest(name=name):
                self.rejects(extra=[(tarfile.TarInfo(name), b"")])

    def test_special_members(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE]:
            member = tarfile.TarInfo("context/special")
            member.type = kind
            member.linkname = "context/target"
            with self.subTest(kind=kind):
                self.rejects(extra=[(member, b"")])

    def test_duplicate_and_member_bound(self):
        self.rejects(extra=[(tarfile.TarInfo("context/" + REQUIRED[0]), b"")])
        member = tarfile.TarInfo("context/large")
        member.size = 1048577
        self.rejects(extra=[(member, b"x" * member.size)])

    def test_physical_pax_bound_and_truncation(self):
        pax = tarfile.TarInfo("pax")
        pax.type = tarfile.XHDTYPE
        pax.size = 16385
        self.rejects(raw=lambda _: pax.tobuf() + b"x" * pax.size + bytes(1024))
        self.rejects(raw=lambda data: data[:550])
        self.rejects(raw=lambda data: data + b"unexpected")

    def test_stage_preserves_exact_policy_and_dockerfile_without_publish(self):
        result = self.probe(stage=True)
        self.assertEqual(0, result.returncode)
        self.assertFalse(json.loads(result.stdout)["provesPinnedDependencyCheckout"])

    def test_failed_stage_removes_only_owned_directory(self):
        self.rejects(stage=True, missing=REQUIRED[0])

    def test_regular_context_root_rejected_before_staging(self):
        self.rejects(stage=True, extra=[(tarfile.TarInfo("context"), b"")])

    def test_directory_context_root_preserved_as_stage_directory(self):
        member = tarfile.TarInfo("context/")
        member.type = tarfile.DIRTYPE
        result = self.probe(stage=True, extra=[(member, b"")])
        self.assertEqual(0, result.returncode)

    def test_deep_bounded_json_returns_redacted_rejection(self):
        for depth in (2000, 30000):
            with self.subTest(depth=depth):
                self.rejects(manifest_raw="[" * depth + "0" + "]" * depth)


if __name__ == "__main__":
    unittest.main()
