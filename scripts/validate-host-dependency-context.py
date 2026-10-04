#!/usr/bin/env python3
"""Bounded Accounting export inspection; no extraction or runtime acceptance."""
import argparse
import hashlib
import json
import pathlib
import re
import os
import shutil
import tempfile
import tarfile

PROFILE = "accounting-host-dependencies-v1"
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_MEMBER = 1024 * 1024
MAX_METADATA = 16384
MAX_ENTRIES = 2048
REQUIRED = ["nuget.config"] + [f"Legacy.Maliev.AccountingService.{p}/Legacy.Maliev.AccountingService.{p}.csproj" for p in ("Api", "Application", "Domain", "Data")] + [f".dependencies/Legacy.Maliev.{p}/src/Legacy.Maliev.{p}/Legacy.Maliev.{p}.csproj" for p in ("ServiceDefaults", "CompatibilityContracts")]
IDENTITIES = dict(sourceBase="ff8fcf61684566b150fe06d88f2ee0c41bc6a33f", publisherHead="e3a6093324a24968876782153286f52db8b29fd8", defaultsHead="8f4f5f27b226ffe406c4c79b1903742e8c2e7dd3", defaultsTree="2b02094f45bcd3ac112a2c6da66dc2a4bb6994c0", contractsHead="78e48ffc4ee000df0510cba5e7c7a3c4c4d539d7", contractsTree="b8172e57562f2e276554e47d4fa0964736c8cbe8", dockerfileSha256="2150a1d560902ed683a3e0c9aa39c8572a66c3dd48fb1e8b404451feab860fcc", policySha256="5984866d3f136fd22a64d3147c942eac8423638bf2f5703232c2d11cc1ed0db5")


class Rejected(ValueError):
    """A fixed category, never input content."""


class BoundedReader:
    def __init__(self, stream):
        self.stream = stream
        self.total = 0

    def read(self, length):
        if length < 0:
            reject("unbounded-read")
        data = self.stream.read(min(length, MAX_ARCHIVE - self.total + 1))
        self.total += len(data)
        if self.total > MAX_ARCHIVE:
            reject("archive-bound")
        return data


def reject(category):
    raise Rejected(category)


def normalized(name):
    if not name or name.startswith("/") or "\\" in name or ":" in name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        reject("unsafe-member")
    pieces = name.split("/")
    if ".." in pieces:
        reject("unsafe-member")
    parts = [p for p in pieces if p not in ("", ".")]
    if not parts or parts[0] != "context" or any(p.lower() == ".git" for p in parts):
        reject("unsafe-member")
    return "/".join(parts)


def read_exact(stream, length):
    data = stream.read(length)
    if len(data) != length:
        reject("truncated-archive")
    return data


def pax_fields(data):
    fields = {}
    offset = 0
    allowed = {"path", "size", "mtime", "atime", "ctime", "uid", "gid", "uname", "gname"}
    while offset < len(data):
        space = data.find(b" ", offset, offset + 16)
        if space < 0 or not data[offset:space].isdigit():
            reject("invalid-metadata")
        length = int(data[offset:space])
        if length < 5 or offset + length > len(data) or data[offset + length - 1] != 10:
            reject("invalid-metadata")
        record = data[space + 1:offset + length - 1].decode("utf-8", "strict")
        key, separator, value = record.partition("=")
        if not separator or key not in allowed or key in fields:
            reject("invalid-metadata")
        fields[key] = value
        offset += length
    return fields


def members(stream):
    """Inspect physical headers before metadata reads; yield bounded file bytes."""
    count = 0
    names = set()
    pending = None
    while True:
        block = read_exact(stream, 512)
        if block == bytes(512):
            if pending is not None or read_exact(stream, 512) != bytes(512):
                reject("invalid-end-marker")
            while trailing := stream.read(65536):
                if any(trailing):
                    reject("trailing-archive-data")
            return
        count += 1
        if count > MAX_ENTRIES:
            reject("entry-bound")
        info = tarfile.TarInfo.frombuf(block, "utf-8", "strict")
        if block[257:263] not in (b"ustar\0", bytes(6)):
            reject("unsupported-format")
        if info.size < 0:
            reject("member-bound")
        if info.type == tarfile.XHDTYPE:
            if pending is not None or info.size > MAX_METADATA:
                reject("metadata-bound")
            pending = pax_fields(read_exact(stream, info.size))
            if any(read_exact(stream, (-info.size) % 512)):
                reject("invalid-padding")
            continue
        if info.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
            reject("unsupported-member")
        if info.size > MAX_MEMBER:
            reject("member-bound")
        if pending is not None:
            info.name = pending.get("path", info.name)
            if "size" in pending and (not pending["size"].isdigit() or int(pending["size"]) != info.size):
                reject("invalid-metadata")
            pending = None
        name = normalized(info.name)
        if name == "context" and info.type != tarfile.DIRTYPE:
            reject("invalid-root-member")
        if name in names:
            reject("duplicate-member")
        names.add(name)
        if info.type == tarfile.DIRTYPE and info.size:
            reject("invalid-directory")
        content = read_exact(stream, info.size)
        if any(read_exact(stream, (-info.size) % 512)):
            reject("invalid-padding")
        yield name, info.type, content


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            reject("duplicate-provenance")
        result[key] = value
    return result


def load_provenance(path, caller):
    with pathlib.Path(path).open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        reject("provenance-bound")
    manifest = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    fields = {"schemaVersion", "profile", "callerHead", "requiredSources", *IDENTITIES}
    if not isinstance(manifest, dict) or set(manifest) != fields:
        reject("invalid-provenance")
    if type(manifest["schemaVersion"]) is not int or manifest["schemaVersion"] != 1 or manifest["profile"] != PROFILE:
        reject("invalid-provenance")
    if not re.fullmatch(r"[0-9a-f]{40}", caller) or manifest["callerHead"] != caller:
        reject("identity-mismatch")
    if any(manifest[key] != value for key, value in IDENTITIES.items()):
        reject("identity-mismatch")
    sources = manifest["requiredSources"]
    if not isinstance(sources, dict) or set(sources) != set(REQUIRED) or any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in sources.values()):
        reject("invalid-source-provenance")
    return manifest


def validate(archive, provenance, caller, stage_root=None):
    manifest = load_provenance(provenance, caller)
    path = pathlib.Path(archive)
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE:
        reject("archive-bound")
    found = {}
    stage = None
    identity_files = {".dockerignore": IDENTITIES["policySha256"], "Legacy.Maliev.AccountingService.Api/Dockerfile": IDENTITIES["dockerfileSha256"]}
    observed_identity = {}
    completed = False
    try:
        if stage_root is not None:
            parent = pathlib.Path(stage_root).resolve(strict=True)
            if not parent.is_dir():
                reject("invalid-stage-root")
            stage = pathlib.Path(tempfile.mkdtemp(prefix="workflows-accounting-context-", dir=parent))
        with path.open("rb") as stream:
            if os.fstat(stream.fileno()).st_size > MAX_ARCHIVE:
                reject("archive-bound")
            for name, kind, content in members(BoundedReader(stream)):
                relative = name.removeprefix("context/")
                if relative in REQUIRED:
                    if kind not in (tarfile.REGTYPE, tarfile.AREGTYPE) or not content:
                        reject("missing-source")
                    found[relative] = hashlib.sha256(content).hexdigest()
                if relative in identity_files:
                    observed_identity[relative] = hashlib.sha256(content).hexdigest()
                if stage is not None and name != "context":
                    destination = stage.joinpath(*relative.split("/"))
                    if not destination.is_relative_to(stage):
                        reject("unsafe-member")
                    if kind == tarfile.DIRTYPE:
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with destination.open("xb") as target:
                            target.write(content)
        if set(found) != set(REQUIRED):
            reject("missing-source")
        if found != manifest["requiredSources"]:
            reject("source-digest-mismatch")
        if any(observed_identity[p] != identity_files[p] for p in observed_identity):
            reject("context-identity-mismatch")
        if stage is not None and observed_identity != identity_files:
            reject("missing-context-identity")
        receipt = {"status": "accepted", "profile": PROFILE, "requiredSourceCount": len(found), "scope": "source-context-export-only", "provesLockedRestore": False, "provesPinnedDependencyCheckout": False, "provesDockerignoreSemantics": False, "contextIdentityFilesMatched": observed_identity == identity_files}
        if stage is not None:
            receipt["stageDirectory"] = str(stage)
        completed = True
        return receipt
    finally:
        if stage is not None and not completed:
            if stage.parent != parent or not stage.name.startswith("workflows-accounting-context-"):
                reject("invalid-cleanup-target")
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--caller-ref", required=True)
    parser.add_argument("--stage-root", help="Optional existing output parent; create one owned UUID context, preserving exact owner policy")
    args = parser.parse_args()
    try:
        if args.profile != PROFILE:
            reject("unknown-profile")
        receipt = validate(args.archive, args.provenance, args.caller_ref, args.stage_root)
    except (Rejected, OSError, ValueError, UnicodeError, RecursionError, tarfile.TarError) as error:
        category = str(error) if isinstance(error, Rejected) else "invalid-input"
        print(json.dumps({"status": "rejected", "profile": PROFILE, "category": category, "scope": "source-context-export-only"}, sort_keys=True))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
