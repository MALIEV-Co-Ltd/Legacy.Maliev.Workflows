#!/usr/bin/env python3
"""Scan only current tracked files of an explicitly selected Git worktree; never echo values."""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


class ScanFailure(Exception):
    """Inspection could not be completed; callers must fail closed."""


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    rule: str
    line: int


@dataclass(frozen=True)
class ReviewedException:
    path: str
    rule: str
    line: int
    content_sha256: str
    approval_url: str


# No historical inline exemption or caller-provided allowlist is inherited.
# A future exception requires explicit approval, exact file digest and source review.
REVIEWED_EXCEPTIONS: tuple[ReviewedException, ...] = ()
MAX_FILE_BYTES = 128 * 1024 * 1024
PATTERNS = {
    "gcp-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "aws-access-key-id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{60,255})\b"),
    "pem-private-key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "connection-string-password": re.compile(
        r"(?i)(?:;\s*|(?:^|[\"'])\s*)(?:password|pwd)\s*=\s*[^;\s\"'<>,]+"),
    "oauth-client-secret-json": re.compile(
        r"(?i)[\"'](?:client_secret|clientsecret)[\"']\s*:\s*[\"'][^\"']+[\"']"),
    "jwt-signing-secret-json": re.compile(
        r"(?i)[\"'](?:jwt[_-]?secret|secretkey|signingkey|secret)[\"']\s*:\s*[\"'][^\"']+[\"']"),
    "legacy-credential-class": re.compile(r"\b(?:class|interface)\s+I?ServiceAccount\b"),
}
BASE64_CANDIDATE = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{100,}={0,2}(?![A-Za-z0-9+/=])")


def content_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def placeholder_ranges(path: str, text: str) -> list[tuple[int, int]]:
    """Only real Python f-string AST nodes permit an exact identifier-only password value."""
    if not path.lower().endswith(".py"):
        return []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    lines = text.splitlines(keepends=True)

    def offset(line: int, column: int) -> int:
        return sum(len(value) for value in lines[:line - 1]) + len(
            lines[line - 1].encode("utf-8")[:column].decode("utf-8"))

    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            ranges.append((offset(node.lineno, node.col_offset), offset(node.end_lineno, node.end_col_offset)))
    return ranges


def scan_text(path: str, text: str, *, exceptions=None, raw_digest=None) -> list[Finding]:
    reviewed = REVIEWED_EXCEPTIONS if exceptions is None else exceptions
    for item in reviewed:
        if not (item.path and item.rule in PATTERNS and item.line > 0
                and re.fullmatch(r"[0-9a-f]{64}", item.content_sha256)
                and re.fullmatch(r"https://github\.com/MALIEV-Co-Ltd/[^/]+/(?:issues|pull)/[1-9][0-9]*", item.approval_url)):
            raise ScanFailure("Invalid reviewed exception")
    digest = content_digest(text) if raw_digest is None else raw_digest
    allowed = {(item.path, item.rule, item.line) for item in reviewed if item.content_sha256 == digest}
    findings = set()
    ranges = placeholder_ranges(path, text)

    def add(rule: str, position: int):
        finding = Finding(path, rule, text.count("\n", 0, position) + 1)
        if (finding.path, finding.rule, finding.line) not in allowed:
            findings.add(finding)

    for rule, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            if rule == "connection-string-password":
                value = match.group().split("=", 1)[1].strip()
                if (re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\}", value)
                        and any(start <= match.start() and match.end() <= end for start, end in ranges)):
                    continue
            add(rule, match.start())

    type_match = re.search(r'["\']type["\']\s*:\s*["\']service_account["\']', text)
    if type_match and re.search(r'["\']private_key["\']\s*:', text):
        add("gcp-service-account-json", type_match.start())
    declarations = list(re.finditer(
        r"(?m)^[ \t]*(?:(?:public|internal|private|protected|sealed|abstract|static|partial|new)\s+)*"
        r"(?P<kind>class|interface)\s+[A-Za-z_][A-Za-z0-9_]*\b", text))
    for index, declaration in enumerate(declarations):
        end = declarations[index + 1].start() if index + 1 < len(declarations) else len(text)
        block = text[declaration.start():end]
        if declaration.group("kind") == "class" and re.search(r"\bProperties\s*\.\s*Resources\s*\.\s*\w+", block) \
                and re.search(r"\b(?:GoogleCredential\s*\.\s*FromStream|ServiceAccountCredential\s*\.\s*FromServiceAccountData)\s*\(", block):
            add("embedded-credential-holder-class", declaration.start())
        if declaration.group("kind") == "interface" and re.search(r"\bGoogleCredential\b", block) \
                and re.search(r"\bServiceAccountCredential\b", block):
            add("credential-holder-contract", declaration.start())
    for candidate in BASE64_CANDIDATE.finditer(text):
        try:
            decoded = base64.b64decode(candidate.group(), validate=True).decode("utf-8", errors="ignore")
        except (binascii.Error, ValueError):
            continue
        if "service_account" in decoded and "private_key" in decoded:
            add("gcp-service-account-base64", candidate.start())
    return sorted(findings)


def git(root: Path, *args) -> bytes:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True, timeout=30)
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise ScanFailure("Git inspection failed") from None


def scan_repository(selected: Path) -> list[Finding]:
    try:
        selected = selected.resolve(strict=True)
        root = Path(git(selected, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve(strict=True)
        records = git(root, "ls-files", "--stage", "-z").decode("utf-8", errors="strict")
        findings = []
        for record in records.split("\0"):
            if not record:
                continue
            metadata, relative = record.split("\t", 1)
            mode, _object_id, stage = metadata.split(" ")
            if mode not in ("100644", "100755") or stage != "0":
                raise ScanFailure("Unsupported tracked entry")
            path = root / relative
            if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
                raise ScanFailure("Tracked path is outside repository or not a file")
            if any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(root)):
                raise ScanFailure("Tracked path uses a symbolic link")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ScanFailure("Tracked file exceeds inspection bound")
            # Binary files are still scanned for ASCII credentials; no ignored/untracked traversal.
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig", errors="ignore")
            findings.extend(scan_text(relative.replace("\\", "/"), text, raw_digest=hashlib.sha256(raw).hexdigest()))
        return sorted(set(findings))
    except (OSError, UnicodeError, ValueError):
        raise ScanFailure("Tracked current-tree inspection failed") from None


def format_findings(findings) -> str:
    lines = []
    for finding in sorted(findings):
        path = finding.path
        if scan_text("metadata.txt", path, exceptions=()):
            path = "[redacted-path]"
        lines.append(json.dumps({"rule": finding.rule, "path": path, "line": finding.line}, ensure_ascii=True))
    return "\n".join(lines)


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        raise ScanFailure("Invalid scanner arguments")


def main(argv=None) -> int:
    try:
        if sys.version_info < (3, 11):
            raise ScanFailure("Unsupported Python version")
        parser = SafeParser(description=__doc__)
        parser.add_argument("repository_root", type=Path)
        args = parser.parse_args(argv)
        findings = scan_repository(args.repository_root)
        if findings:
            print(format_findings(findings), file=sys.stderr)
            print(f"[current-tree-scan] Findings: {len(findings)}; values redacted", file=sys.stderr)
            return 1
        print("[current-tree-scan] Findings: 0")
        return 0
    except Exception:
        print("[current-tree-scan] FAILED: inspection incomplete; details redacted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
