"""Synthetic scanner regressions; credential-shaped values exist only in memory/temp fixtures."""

import base64
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
SCANNER = ROOT / "tools/security/current_tree_secrets.py"
WRAPPER = ROOT / "scripts/Invoke-CurrentTreeCredentialScan.ps1"


def synthetic_password():
    return "Pass" + "word=synthetic-value"


class CurrentTreeSecretTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCANNER.is_file(), "General current-tree scanner must exist")
        spec = importlib.util.spec_from_file_location("current_tree_secrets", SCANNER)
        self.scanner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.scanner
        spec.loader.exec_module(self.scanner)

    def test_high_confidence_formats_have_metadata_only(self):
        values = [
            "AIza" + "A" * 35,
            "AKIA" + "A" * 16,
            "ghp_" + "A" * 36,
            "github_pat_" + "A" * 70,
            "-----BEGIN " + "PRIVATE KEY-----",
            synthetic_password(),
            '"client_' + 'sec' + 'ret": "synthetic-value"',
            '"Signing' + 'Key": "synthetic-value"',
            '{"type":"service_' + 'account","private_' + 'key":"synthetic-value"}',
        ]
        for value in values:
            with self.subTest(kind=values.index(value)):
                findings = self.scanner.scan_text("candidate.txt", value)
                self.assertTrue(findings)
                rendered = self.scanner.format_findings(findings)
                self.assertNotIn(value, rendered)
                self.assertNotIn("synthetic-value", rendered)

    def test_base64_service_account_is_detected_without_decoded_value(self):
        payload = '{"type":"service_' + 'account","private_' + 'key":"' + "x" * 100 + '"}'
        encoded = base64.b64encode(payload.encode()).decode()
        findings = self.scanner.scan_text("resource.txt", encoded)
        self.assertEqual(["gcp-service-account-base64"], [item.rule for item in findings])
        self.assertNotIn(encoded, self.scanner.format_findings(findings))

    def test_external_defaults_and_env_reads_are_not_credentials(self):
        for text in ['"client_secret": ""', '"SigningKey": ""', '"ConnectionStrings": {}',
                     'Environment.GetEnvironmentVariable("JWT_SIGNING_KEY")']:
            self.assertEqual([], self.scanner.scan_text("candidate.txt", text))

    def test_standalone_and_semicolon_password_aliases_are_detected(self):
        for value in [synthetic_password(), '"P' + 'wd=synthetic-value"',
                      "Server=db;" + synthetic_password()]:
            self.assertIn("connection-string-password", [f.rule for f in self.scanner.scan_text("a.txt", value)])

    def test_python_identifier_placeholders_are_narrowly_exempted(self):
        for value in ['connection = f"Server=db;Pass' + 'word={runtime_password};Database=app"',
                      'connection = f"Host=db;P' + 'wd={settings.database_password}"']:
            self.assertEqual([], self.scanner.scan_text("adapter.py", value))

    def test_same_line_literal_is_not_exempted_by_other_placeholder(self):
        text = 'a = f"P' + 'wd={runtime_password}"; b = "' + synthetic_password() + '"'
        findings = self.scanner.scan_text("adapter.py", text)
        self.assertEqual(1, len(findings))
        self.assertEqual("connection-string-password", findings[0].rule)

    def test_non_python_fake_fstrings_comments_and_literal_expressions_are_not_exempted(self):
        values = [
            ("a.txt", 'f"P' + 'wd={runtime_password}"'),
            ("a.py", '# f"P' + 'wd={runtime_password}"'),
            ("a.py", 'a = "f\\\"P' + 'wd={runtime_password}\\\""'),
            ("a.py", 'a = f"P' + 'wd={literal-secret}"'),
            ("a.py", 'a = f"P' + 'wd={runtime_password}-suffix"'),
        ]
        for path, value in values:
            self.assertTrue(self.scanner.scan_text(path, value))

    def test_holder_markers_must_share_one_declaration(self):
        holder = "public sealed class Holder { var data = Properties" + ".Resources.Provider; " + \
                 "var credential = GoogleCredential.FromStream(data); }"
        self.assertEqual(["embedded-credential-holder-class"],
                         [f.rule for f in self.scanner.scan_text("a.cs", holder)])
        split = "public class Holder { var data = Properties" + ".Resources.Provider; }\n" + \
                "public class Reader { var credential = GoogleCredential.FromStream(stream); }"
        self.assertEqual([], self.scanner.scan_text("a.cs", split))
        contract = "public interface IHolder { GoogleCredential Credential { get; } " + \
                   "ServiceAccountCredential Account { get; } }"
        self.assertEqual(["credential-holder-contract"], [f.rule for f in self.scanner.scan_text("a.cs", contract)])

    def test_allowlist_requires_exact_content_and_explicit_review(self):
        text = synthetic_password()
        finding = self.scanner.scan_text("candidate.txt", text)[0]
        exception = self.scanner.ReviewedException(
            path="candidate.txt", rule=finding.rule, line=1,
            content_sha256=self.scanner.content_digest(text),
            approval_url="https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/197")
        self.assertEqual([], self.scanner.scan_text("candidate.txt", text, exceptions=(exception,)))
        self.assertTrue(self.scanner.scan_text("other.txt", text, exceptions=(exception,)))
        self.assertTrue(self.scanner.scan_text("candidate.txt", text + "\n", exceptions=(exception,)))
        invalid = self.scanner.ReviewedException("candidate.txt", finding.rule, 1,
                                                self.scanner.content_digest(text), "")
        self.assertRaises(self.scanner.ScanFailure, self.scanner.scan_text,
                          "candidate.txt", text, exceptions=(invalid,))
        self.assertEqual((), self.scanner.REVIEWED_EXCEPTIONS)

    def test_reviewed_exception_cannot_hide_changed_invalid_utf8_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init", "--quiet")
            text = synthetic_password()
            (root / "candidate.txt").write_bytes(text.encode() + bytes([255]))
            self.git(root, "add", "candidate.txt")
            self.scanner.REVIEWED_EXCEPTIONS = (self.scanner.ReviewedException(
                "candidate.txt", "connection-string-password", 1, self.scanner.content_digest(text),
                "https://github.com/MALIEV-Co-Ltd/Legacy.Maliev.Workflows/issues/197"),)
            self.assertEqual(1, len(self.scanner.scan_repository(root)))

    def test_metadata_cannot_inject_workflow_commands_or_echo_key_filename(self):
        token = "ghp_" + "A" * 36
        text = synthetic_password()
        output = self.scanner.format_findings(self.scanner.scan_text(token + "\n::error::x.txt", text))
        self.assertNotIn(token, output)
        self.assertEqual(1, len(output.splitlines()))
        self.assertIn("path", json.loads(output))

    def test_metadata_does_not_echo_base64_credential_in_filename(self):
        payload = '{"type":"service_' + 'account","private_' + 'key":"' + "x" * 100 + '"}'
        encoded = base64.b64encode(payload.encode()).decode()
        findings = self.scanner.scan_text(encoded + ".txt", synthetic_password())
        self.assertNotIn(encoded, self.scanner.format_findings(findings))

    def test_read_error_is_fail_closed_and_never_echoes_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init", "--quiet")
            (root / "tracked.txt").write_text("safe")
            self.git(root, "add", "tracked.txt")
            with mock.patch.object(Path, "read_bytes", side_effect=OSError("synthetic-value")):
                self.assertRaises(self.scanner.ScanFailure, self.scanner.scan_repository, root)

    def test_scans_current_tracked_tree_not_history_untracked_or_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init", "--quiet")
            self.git(root, "config", "user.email", "fixture@example.invalid")
            self.git(root, "config", "user.name", "Scanner fixture")
            (root / "tracked.txt").write_text(synthetic_password())
            self.git(root, "add", "tracked.txt")
            self.git(root, "commit", "--quiet", "-m", "synthetic historical fixture")
            (root / "tracked.txt").write_text("safe current content")
            (root / ".gitignore").write_text("ignored.txt\n")
            (root / "ignored.txt").write_text(synthetic_password())
            (root / "untracked.txt").write_text(synthetic_password())
            self.assertEqual([], self.scanner.scan_repository(root))
            self.git(root, "add", "--force", "ignored.txt")
            findings = self.scanner.scan_repository(root)
            self.assertEqual(["ignored.txt"], [f.path for f in findings])

    def test_deleted_tracked_file_and_non_repository_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertRaises(self.scanner.ScanFailure, self.scanner.scan_repository, root)
            self.git(root, "init", "--quiet")
            (root / "tracked.txt").write_text("safe")
            self.git(root, "add", "tracked.txt")
            (root / "tracked.txt").unlink()
            self.assertRaises(self.scanner.ScanFailure, self.scanner.scan_repository, root)

    def test_symlink_and_gitlink_fail_without_reading_external_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init", "--quiet")
            object_id = self.git(root, "hash-object", "-w", "--stdin", input="external.txt").stdout.strip()
            for mode in ["120000", "160000"]:
                self.git(root, "update-index", "--add", "--cacheinfo", mode, object_id, "external")
                self.assertRaises(self.scanner.ScanFailure, self.scanner.scan_repository, root)

    def test_cli_exit_codes_and_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init", "--quiet")
            (root / "candidate.txt").write_text("safe")
            self.git(root, "add", "candidate.txt")
            self.assertEqual(0, self.cli(root).returncode)
            (root / "candidate.txt").write_text(synthetic_password())
            result = self.cli(root)
            self.assertEqual(1, result.returncode)
            self.assertNotIn("synthetic-value", result.stdout + result.stderr)
            (root / "candidate.txt").unlink()
            result = self.cli(root)
            self.assertEqual(2, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(2, self.cli(root, "--allow-all").returncode)

    def test_missing_git_fails_closed_without_raw_diagnostics(self):
        result = self.cli(ROOT, env={**os.environ, "PATH": ""})
        self.assertEqual(2, result.returncode)
        self.assertNotIn("Traceback", result.stderr)

    def test_unsupported_python_version_fails_before_repository_inspection(self):
        with mock.patch.object(sys, "version_info", (3, 10, 0)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, self.scanner.main([str(ROOT)]))

    def test_real_powershell_wrapper_propagates_clean_finding_and_incomplete_exits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init", "--quiet")
            candidate = root / "candidate.txt"
            candidate.write_text("safe")
            self.git(root, "add", candidate.name)
            self.assertEqual(0, self.wrapper(root).returncode)
            candidate.write_text(synthetic_password())
            result = self.wrapper(root)
            self.assertEqual(1, result.returncode)
            self.assertNotIn("synthetic-value", result.stdout + result.stderr)
            candidate.unlink()
            self.assertEqual(2, self.wrapper(root).returncode)

    def test_real_wrapper_missing_python_is_redacted_and_fail_closed(self):
        result = self.wrapper(ROOT, env={**os.environ, "PATH": ""})
        self.assertEqual(2, result.returncode)
        self.assertIn("details redacted", result.stderr)
        self.assertNotIn("CommandNotFound", result.stderr)

    def test_wrapper_preserves_finding_exit_under_strict_native_error_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init", "--quiet")
            (root / "candidate.txt").write_text(synthetic_password())
            self.git(root, "add", "candidate.txt")
            command = "$PSNativeCommandUseErrorActionPreference = $true; " + \
                      "& $env:SCANNER_WRAPPER -RepositoryPath $env:SCANNER_REPOSITORY"
            result = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-Command", command],
                                    text=True, capture_output=True, env={**os.environ,
                                    "SCANNER_WRAPPER": str(WRAPPER), "SCANNER_REPOSITORY": str(root)})
            self.assertEqual(1, result.returncode)
            self.assertNotIn("synthetic-value", result.stdout + result.stderr)

    def test_all_candidate_artifacts_are_secretless_before_git_tracking(self):
        paths = [
            "tools/security/current_tree_secrets.py",
            "tools/security/tests/test_current_tree_secrets.py",
            "scripts/Invoke-CurrentTreeCredentialScan.ps1",
            "actions/dotnet-validate/action.yml",
            ".github/workflows/dotnet-validate.yml",
            ".github/workflows/validate.yml",
            "tests/Legacy.Maliev.Workflows.Tests/RepositoryContractTests.cs",
            "tests/Legacy.Maliev.Workflows.Tests/CurrentTreeCredentialScannerTests.cs",
            "migration/current-tree-security-bundle-evidence-20260930.md",
        ]
        for relative in paths:
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8-sig")
                self.assertEqual([], self.scanner.scan_text(relative, text))

    @staticmethod
    def git(root, *args, input=None):
        return subprocess.run(["git", "-C", str(root), *args], input=input, text=True,
                              capture_output=True, check=True)

    @staticmethod
    def cli(root, *args, env=None):
        return subprocess.run([sys.executable, "-B", str(SCANNER), str(root), *args],
                              text=True, capture_output=True, env=env)

    @staticmethod
    def wrapper(root, env=None):
        executable = shutil.which("pwsh")
        if executable is None:
            raise AssertionError("PowerShell 7 is required; missing tool must not skip acceptance")
        return subprocess.run([executable, "-NoProfile", "-File", str(WRAPPER), "-RepositoryPath", str(root)],
                              text=True, capture_output=True, env=env)


if __name__ == "__main__":
    unittest.main()
