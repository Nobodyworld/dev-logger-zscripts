"""Build a deterministic, static-first inventory of tracked legacy helpers.

The default operation parses source with :mod:`ast`; it never imports or executes
helper modules.  An already-built wheel may be supplied for package-content
verification.  Dynamic import eligibility is reported, but probes are deliberately
not run by this evidence-only tool.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import zipfile
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs/operations/legacy_helper_inventory.json"
HELPER_DIRECTORY = "zscripts/helpers"
REQUESTED_HELPER_GLOB = "zscripts/helpers/**/*.py"
RISK_LEVELS = ("low", "moderate", "high", "critical-review")
DISPOSITIONS = (
    "retain-supported",
    "quarantine-from-wheel",
    "migrate-separate-package",
    "archive",
    "delete-candidate",
    "manual-review",
)

NETWORK_ROOTS = {
    "aiohttp",
    "ftplib",
    "googleapiclient",
    "http",
    "imaplib",
    "openai",
    "poplib",
    "requests",
    "smtplib",
    "socket",
    "urllib",
}
NETWORK_CALL_PARTS = {
    "build",
    "create_connection",
    "get",
    "post",
    "put",
    "request",
    "send",
    "sendmail",
    "urlopen",
}
CREDENTIAL_RE = re.compile(r"(?:api[_-]?key|credential|password|secret|token)", re.IGNORECASE)
ORGANIZATION_RE = re.compile(
    r"(?:ORGANIZATION_STORAGE_ROOT|ORGANIZATION_STORAGE|org_path|Shared Documents|"
    r"Nobodyworld|OneDrive|SharePoint)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/Users/[^/]+|/home/[^/]+|\\\\[^\\]+\\)")
CONFIG_REFERENCE_RE = re.compile(
    r"(?:^|[/\\])(?:configs?|settings?)(?:[/\\]|\.(?:json|ya?ml|toml|ini|env)$)",
    re.IGNORECASE,
)


class InventoryError(RuntimeError):
    """Raised when authoritative inventory inputs cannot be analyzed safely."""


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise InventoryError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def tracked_helper_paths() -> list[str]:
    """Return the authoritative, sorted repository-relative helper paths."""
    paths = [line for line in _git("ls-files", HELPER_DIRECTORY).splitlines() if line.endswith(".py")]
    normalized = [PurePosixPath(path).as_posix() for path in paths]
    if len(normalized) != len(set(normalized)):
        duplicates = sorted(path for path, count in Counter(normalized).items() if count > 1)
        raise InventoryError(f"git returned duplicate tracked helper paths: {duplicates}")
    return sorted(normalized)


def _tracked_files(pathspec: str) -> list[str]:
    return sorted(PurePosixPath(line).as_posix() for line in _git("ls-files", pathspec).splitlines() if line)


def _tracked_under(directory: str, suffix: str) -> list[str]:
    prefix = f"{directory.rstrip('/')}/"
    return sorted(
        PurePosixPath(line).as_posix()
        for line in _git("ls-files", directory).splitlines()
        if line.startswith(prefix) and line.endswith(suffix)
    )


def _module_name(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".")


def _domain(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[2] if len(parts) > 3 else "root"


def _qualified_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value, aliases)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _literal_strings(tree: ast.AST) -> list[tuple[int, str]]:
    values: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append((getattr(node, "lineno", 0), node.value))
    return values


def _contains_runtime_expression(node: ast.AST | None) -> bool:
    if node is None:
        return False
    runtime_nodes = (
        ast.Await,
        ast.Call,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
        ast.NamedExpr,
        ast.Yield,
        ast.YieldFrom,
    )
    return any(isinstance(child, runtime_nodes) for child in ast.walk(node))


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    candidates = ((left, right), (right, left))
    return any(
        isinstance(name, ast.Name)
        and name.id == "__name__"
        and isinstance(value, ast.Constant)
        and value.value == "__main__"
        for name, value in candidates
    )


def _top_level_executable(tree: ast.Module) -> tuple[bool, list[dict[str, Any]]]:
    has_main_guard = False
    statements: list[dict[str, Any]] = []
    for node in tree.body:
        if isinstance(node, ast.If) and _is_main_guard(node):
            has_main_guard = True
            continue
        if isinstance(
            node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if not _contains_runtime_expression(value):
                continue
        names = sorted({child.id for child in ast.walk(node) if isinstance(child, ast.Name)})
        rendered = type(node).__name__
        if names:
            rendered = f"{rendered} referencing {', '.join(names[:8])}"
        statements.append(
            {
                "line": getattr(node, "lineno", 0),
                "statement": type(node).__name__,
                "summary": rendered[:180],
            }
        )
    return has_main_guard, statements


def _import_data(
    tree: ast.Module,
    helper_basenames: set[str],
    repository_root_modules: set[str],
) -> dict[str, Any]:
    aliases: dict[str, str] = {}
    imported_names: list[str] = []
    valid_helpers: set[str] = set()
    relatives: set[str] = set()
    obsolete: set[str] = set()
    root_imports: set[str] = set()
    third_party: set[str] = set()
    local_roots = {"adapters", "agents", "schemas", "scripts", "tests", "zscripts"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            entries = [(alias.name, alias.asname or alias.name.split(".", 1)[0]) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            rendered_base = "." * node.level + base
            if node.level:
                relatives.add(rendered_base)
            entries = []
            for alias in node.names:
                full_name = f"{base}.{alias.name}" if base else alias.name
                entries.append((rendered_base or full_name, alias.asname or alias.name))
                aliases[alias.asname or alias.name] = full_name
        else:
            continue

        for imported, local_name in entries:
            imported_names.append(imported)
            aliases.setdefault(local_name, imported)
            normalized = imported.lstrip(".")
            root = normalized.split(".", 1)[0]
            if imported.startswith("."):
                continue
            if normalized == "zscripts.helpers" or normalized.startswith("zscripts.helpers."):
                valid_helpers.add(normalized)
            elif normalized == "helpers" or normalized.startswith("helpers."):
                obsolete.add(normalized)
            elif root not in sys.stdlib_module_names and (
                root in repository_root_modules or root in helper_basenames
            ):
                root_imports.add(normalized)
            elif root and root not in sys.stdlib_module_names and root not in local_roots:
                third_party.add(root)

    return {
        "aliases": aliases,
        "imported_names": sorted(set(imported_names)),
        "internal_imports": sorted(valid_helpers),
        "relative_imports": sorted(relatives),
        "obsolete_top_level_helper_imports": sorted(obsolete),
        "repository_root_imports": sorted(root_imports),
        "third_party_imports": sorted(third_party),
    }


def _classify_calls(
    tree: ast.Module,
    aliases: dict[str, str],
    imported_names: Iterable[str],
) -> dict[str, Any]:
    flags = {
        "filesystem_read": False,
        "filesystem_write": False,
        "filesystem_move_or_delete": False,
        "subprocess_or_shell": False,
        "network_or_api": False,
        "environment_access": False,
        "credential_access": False,
        "organization_specific": False,
    }
    evidence: set[str] = set()
    imported_roots = {name.lstrip(".").split(".", 1)[0] for name in imported_names}
    if imported_roots & NETWORK_ROOTS:
        flags["network_or_api"] = True
        evidence.add(f"network/API import: {sorted(imported_roots & NETWORK_ROOTS)[0]}")
    if "dotenv" in imported_roots:
        flags["environment_access"] = True
        flags["credential_access"] = True
        evidence.add("credential/environment loader import: dotenv")
    if "subprocess" in imported_roots:
        flags["subprocess_or_shell"] = True
        evidence.add("external command import: subprocess")

    credential_context = False
    for line, value in _literal_strings(tree):
        if ORGANIZATION_RE.search(value) or LOCAL_PATH_RE.search(value):
            flags["organization_specific"] = True
            evidence.add(f"organization/local-path assumption at line {line}")
        if CONFIG_REFERENCE_RE.search(value):
            evidence.add(f"repository-root configuration reference at line {line}: {value[:80]}")
        if CREDENTIAL_RE.search(value):
            credential_context = True

    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)):
            name = _qualified_name(node, aliases) or ""
            if ORGANIZATION_RE.search(name):
                flags["organization_specific"] = True
                evidence.add(f"organization-specific identifier at line {getattr(node, 'lineno', 0)}: {name}")
        if not isinstance(node, ast.Call):
            continue
        name = _qualified_name(node.func, aliases) or "<dynamic-call>"
        short = name.rsplit(".", 1)[-1]
        line = getattr(node, "lineno", 0)

        if name == "open" or name.endswith(".open"):
            mode = "r"
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                    mode = str(keyword.value.value)
            if any(character in mode for character in "wax+"):
                flags["filesystem_write"] = True
                evidence.add(f"filesystem write call at line {line}: {name} mode={mode}")
            else:
                flags["filesystem_read"] = True
                evidence.add(f"filesystem read call at line {line}: {name}")
            file_arguments = [
                argument.value
                for argument in node.args[:1]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
            ]
            if any(CREDENTIAL_RE.search(value) for value in file_arguments):
                flags["credential_access"] = True
                evidence.add(f"credential-like file access at line {line}: {name}")

        if short in {"read_bytes", "read_text"}:
            flags["filesystem_read"] = True
            evidence.add(f"filesystem read call at line {line}: {name}")
        if short in {"write_bytes", "write_text", "mkdir"} or name in {
            "os.makedirs",
            "shutil.copy",
            "shutil.copy2",
            "shutil.copyfile",
            "shutil.copytree",
        }:
            flags["filesystem_write"] = True
            evidence.add(f"filesystem write call at line {line}: {name}")
        if short in {"unlink", "rename"} or name in {
            "os.remove",
            "os.unlink",
            "os.rename",
            "os.replace",
            "shutil.move",
            "shutil.rmtree",
        }:
            flags["filesystem_move_or_delete"] = True
            evidence.add(f"filesystem move/delete call at line {line}: {name}")

        if name.startswith("subprocess.") or name in {"os.system", "os.popen", "commands.getoutput"}:
            flags["subprocess_or_shell"] = True
            evidence.add(f"external command call at line {line}: {name}")
        if short in {"run_command", "execute_command", "shell_exec"}:
            flags["subprocess_or_shell"] = True
            evidence.add(f"external command wrapper at line {line}: {name}")

        root = name.split(".", 1)[0]
        if root in NETWORK_ROOTS and (short in NETWORK_CALL_PARTS or root in {"openai", "googleapiclient"}):
            flags["network_or_api"] = True
            evidence.add(f"network/API call at line {line}: {name}")
        if short in {"OpenAI", "Client", "build", "urlopen", "sendmail", "create_connection"} and (
            root in NETWORK_ROOTS or "google" in name.lower() or "openai" in name.lower()
        ):
            flags["network_or_api"] = True
            evidence.add(f"remote client construction/call at line {line}: {name}")

        if name in {"os.getenv", "os.environ.get"} or name.startswith("os.environ."):
            flags["environment_access"] = True
            evidence.add(f"environment access at line {line}: {name}")
            arguments = [
                arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            ]
            if credential_context or any(CREDENTIAL_RE.search(value) for value in arguments):
                flags["credential_access"] = True
                evidence.add(f"credential environment lookup at line {line}: {name}")
        if short in {"load_dotenv", "dotenv_values", "find_dotenv"}:
            flags["environment_access"] = True
            flags["credential_access"] = True
            evidence.add(f"credential/environment loader call at line {line}: {name}")
        if any(keyword.arg and CREDENTIAL_RE.search(keyword.arg) for keyword in node.keywords):
            flags["credential_access"] = True
            evidence.add(f"credential-like call argument at line {line}: {name}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            name = _qualified_name(node.value, aliases) or ""
            if name == "os.environ":
                flags["environment_access"] = True
                evidence.add(f"environment access at line {getattr(node, 'lineno', 0)}: os.environ[]")
                if isinstance(node.slice, ast.Constant) and CREDENTIAL_RE.search(str(node.slice.value)):
                    flags["credential_access"] = True
                    evidence.add(f"credential environment lookup at line {getattr(node, 'lineno', 0)}")

    return {**flags, "call_evidence": sorted(evidence)}


def _repository_root_modules() -> set[str]:
    modules = set()
    for path in _git("ls-files").splitlines():
        if "/" not in path:
            modules.add(PurePosixPath(path).stem)
    return modules


def _repository_config_references(tree: ast.Module) -> list[str]:
    references: set[str] = {
        "<local-path configuration reference>" if LOCAL_PATH_RE.search(value) else value.replace("\\", "/")
        for _, value in _literal_strings(tree)
        if CONFIG_REFERENCE_RE.search(value)
    }
    for node in ast.walk(tree):
        fragments = [
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        ]
        config_dirs = [fragment for fragment in fragments if fragment.lower() in {"config", "configs"}]
        config_files = [
            fragment
            for fragment in fragments
            if re.search(r"\.(?:json|ya?ml|toml|ini|env)$", fragment, re.IGNORECASE)
        ]
        for directory in config_dirs:
            for filename in config_files:
                references.add(f"{directory}/{filename}")
    return sorted(references)


def _test_and_documentation_evidence(
    module_path: str,
    module_name: str,
    domain: str,
    test_text: dict[str, str],
    doc_text: dict[str, str],
    registry_text: str,
    package_init_text: str,
) -> dict[str, Any]:
    def references(text: str, value: str) -> bool:
        return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])", text))

    stem = PurePosixPath(module_path).stem
    slash_module = module_name.replace(".", "/")
    direct_test_name = f"tests/test_{stem}.py"
    direct_tests: set[str] = set()
    importing_tests: set[str] = set()
    indirect_tests: set[str] = set()
    domain_tests: set[str] = set()
    parent_module = module_name.rsplit(".", 1)[0]
    reexported = stem != "__init__" and (f".{stem}" in package_init_text or module_name in package_init_text)

    for path, text in test_text.items():
        if path == direct_test_name:
            direct_tests.add(path)
        if any(references(text, value) for value in (module_name, slash_module, module_path)):
            importing_tests.add(path)
        elif reexported and references(text, parent_module):
            indirect_tests.add(path)
        elif domain != "root" and (
            f"helpers.{domain}" in text or f"helpers/{domain}" in text or domain in PurePosixPath(path).stem
        ):
            domain_tests.add(path)

    documentation: set[str] = set()
    for path, text in doc_text.items():
        path_parts = PurePosixPath(path).parts
        is_domain_doc = (
            len(path_parts) >= 3 and path_parts[:2] == ("docs", "helpers") and domain in path_parts
        )
        is_module_reference = any(
            references(text, value) for value in (module_name, module_path, slash_module)
        )
        is_module_doc = stem != "__init__" and stem in PurePosixPath(path).stem
        if is_domain_doc or is_module_reference or is_module_doc:
            documentation.add(path)

    registry_exposed = any(
        references(registry_text, value) for value in (module_name, module_path, slash_module)
    )
    return {
        "tests": sorted(direct_tests | importing_tests | indirect_tests | domain_tests),
        "direct_tests": sorted(direct_tests),
        "importing_tests": sorted(importing_tests),
        "indirect_tests": sorted(indirect_tests),
        "domain_tests": sorted(domain_tests),
        "documentation": sorted(documentation),
        "registry_exposed": registry_exposed,
    }


def _wheel_members(wheel_path: Path | None) -> tuple[set[str], str]:
    if wheel_path is None:
        return set(), "not-checked"
    resolved = wheel_path.resolve()
    if not resolved.is_file():
        raise InventoryError(f"wheel does not exist: {wheel_path}")
    with zipfile.ZipFile(resolved) as archive:
        return set(archive.namelist()), "checked"


def is_dynamic_probe_eligible(record: dict[str, Any]) -> bool:
    """Return whether a module passes the conservative probe exclusion policy."""
    exclusions = (
        "filesystem_write",
        "filesystem_move_or_delete",
        "subprocess_or_shell",
        "network_or_api",
        "credential_access",
        "organization_specific",
    )
    return not any(record[key] for key in exclusions) and not record["top_level_executable_statements"]


def classify_source(source: str, filename: str = "<synthetic>") -> dict[str, Any]:
    """Classify a synthetic source fixture without filesystem or Git access."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise InventoryError(f"syntax error in {filename}:{exc.lineno}:{exc.offset}: {exc.msg}") from exc
    imports = _import_data(tree, set(), set())
    calls = _classify_calls(tree, imports["aliases"], imports["imported_names"])
    has_main_guard, executable = _top_level_executable(tree)
    return {
        **{key: value for key, value in imports.items() if key not in {"aliases", "imported_names"}},
        **calls,
        "top_level_executable_statements": executable,
        "has_main_guard": has_main_guard,
    }


def _risk_and_disposition(record: dict[str, Any]) -> tuple[str, str, str]:
    dangerous = any(
        record[key]
        for key in (
            "filesystem_write",
            "filesystem_move_or_delete",
            "subprocess_or_shell",
            "network_or_api",
            "credential_access",
            "organization_specific",
        )
    )
    combined = (
        (record["credential_access"] and record["network_or_api"])
        or (record["organization_specific"] and record["filesystem_move_or_delete"])
        or (record["top_level_executable_statements"] and dangerous)
    )
    broken_imports = bool(
        record["obsolete_top_level_helper_imports"]
        or record["repository_root_imports"]
        or record["repository_root_config_references"]
    )
    if combined:
        risk = "critical-review"
    elif dangerous:
        risk = "high"
    elif (
        record["filesystem_read"]
        or record["environment_access"]
        or record["top_level_executable_statements"]
        or broken_imports
        or record["third_party_imports"]
    ):
        risk = "moderate"
    else:
        risk = "low"

    if risk in {"critical-review", "high"}:
        disposition = "quarantine-from-wheel"
        rationale = (
            "Risk-bearing legacy behavior should be removed from the core wheel before any support claim."
        )
    elif record["third_party_imports"]:
        disposition = "migrate-separate-package"
        rationale = (
            "Optional dependencies and bounded static risk favor a separately owned compatibility package."
        )
    elif broken_imports or record["top_level_executable_statements"]:
        disposition = "quarantine-from-wheel"
        rationale = "Import/path or import-time behavior is incompatible with a supported core-wheel surface."
    elif record["direct_tests"] or record["importing_tests"]:
        disposition = "retain-supported"
        rationale = "Static risk is low and direct test evidence supports temporary compatibility retention."
    else:
        disposition = "manual-review"
        rationale = "Static risk is low, but support evidence is insufficient for an automatic disposition."
    return risk, disposition, rationale


def _read_text_map(paths: Iterable[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        absolute = ROOT / PurePosixPath(path)
        if not absolute.is_file():
            raise InventoryError(f"tracked file is missing: {path}")
        result[path] = absolute.read_text(encoding="utf-8", errors="replace")
    return result


def build_inventory(wheel_path: Path | None = None) -> dict[str, Any]:
    """Analyze every tracked helper and return the deterministic JSON payload."""
    helper_paths = tracked_helper_paths()
    helper_basenames = {
        PurePosixPath(path).stem for path in helper_paths if not path.endswith("/__init__.py")
    }
    test_paths = _tracked_under("tests", ".py")
    doc_paths = _tracked_under("docs", ".md")
    test_text = _read_text_map(test_paths)
    doc_text = _read_text_map(doc_paths)
    registry_path = ROOT / "configs/registry.yaml"
    registry_text = (
        registry_path.read_text(encoding="utf-8", errors="replace") if registry_path.is_file() else ""
    )
    wheel_members, wheel_status = _wheel_members(wheel_path)
    root_modules = _repository_root_modules()
    records: list[dict[str, Any]] = []

    for relative in helper_paths:
        absolute = ROOT / PurePosixPath(relative)
        if not absolute.is_file():
            raise InventoryError(f"tracked helper file is missing: {relative}")
        source = absolute.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            raise InventoryError(f"syntax error in {relative}:{exc.lineno}:{exc.offset}: {exc.msg}") from exc

        module_name = _module_name(relative)
        domain = _domain(relative)
        imports = _import_data(tree, helper_basenames, root_modules)
        calls = _classify_calls(tree, imports["aliases"], imports["imported_names"])
        has_main_guard, executable = _top_level_executable(tree)
        package_init_path = ROOT / PurePosixPath(relative).parent / "__init__.py"
        package_init_text = (
            package_init_path.read_text(encoding="utf-8", errors="replace")
            if package_init_path.is_file()
            else ""
        )
        linkage = _test_and_documentation_evidence(
            relative,
            module_name,
            domain,
            test_text,
            doc_text,
            registry_text,
            package_init_text,
        )
        wheel_included = relative in wheel_members if wheel_status == "checked" else None
        record: dict[str, Any] = {
            "path": relative,
            "module": module_name,
            "domain": domain,
            "source_lines": len(source.splitlines()),
            "third_party_imports": imports["third_party_imports"],
            "internal_imports": imports["internal_imports"],
            "relative_imports": imports["relative_imports"],
            "obsolete_top_level_helper_imports": imports["obsolete_top_level_helper_imports"],
            "repository_root_imports": imports["repository_root_imports"],
            "repository_root_config_references": _repository_config_references(tree),
            "top_level_executable_statements": executable,
            "filesystem_read": calls["filesystem_read"],
            "filesystem_write": calls["filesystem_write"],
            "filesystem_move_or_delete": calls["filesystem_move_or_delete"],
            "subprocess_or_shell": calls["subprocess_or_shell"],
            "network_or_api": calls["network_or_api"],
            "environment_access": calls["environment_access"],
            "credential_access": calls["credential_access"],
            "organization_specific": calls["organization_specific"],
            "has_main_guard": has_main_guard,
            **linkage,
            "wheel_included": wheel_included,
            "static_risk": "low",
            "recommended_disposition": "manual-review",
            "recommendation_rationale": "",
            "dynamic_import_probe": {
                "eligible": False,
                "status": "not-run",
                "reason": "Optional dynamic probing was omitted; the inventory is static-first and evidence-only.",
            },
            "evidence": calls["call_evidence"],
        }
        risk, disposition, rationale = _risk_and_disposition(record)
        record["static_risk"] = risk
        record["recommended_disposition"] = disposition
        record["recommendation_rationale"] = rationale
        record["dynamic_import_probe"]["eligible"] = is_dynamic_probe_eligible(record)
        records.append(record)

    domain_counts = Counter(record["domain"] for record in records)
    risk_counts = Counter(record["static_risk"] for record in records)
    disposition_counts = Counter(record["recommended_disposition"] for record in records)
    third_party = sorted({item for record in records for item in record["third_party_imports"]})
    requested_glob_paths = {
        PurePosixPath(line).as_posix()
        for line in _git("ls-files", REQUESTED_HELPER_GLOB).splitlines()
        if line
    }

    def module_count(key: str) -> int:
        return sum(bool(record[key]) for record in records)

    summary = {
        "total_modules": len(records),
        "requested_glob_module_count": len(requested_glob_paths),
        "tracked_root_level_modules_added": len(set(helper_paths) - requested_glob_paths),
        "total_source_lines": sum(record["source_lines"] for record in records),
        "modules_by_domain": dict(sorted(domain_counts.items())),
        "modules_by_risk": {risk: risk_counts.get(risk, 0) for risk in RISK_LEVELS},
        "modules_by_disposition": {
            disposition: disposition_counts.get(disposition, 0) for disposition in DISPOSITIONS
        },
        "third_party_dependencies": third_party,
        "third_party_dependency_count": len(third_party),
        "modules_with_obsolete_import_paths": module_count("obsolete_top_level_helper_imports"),
        "modules_with_repository_root_imports": module_count("repository_root_imports"),
        "modules_with_repository_root_config_references": module_count("repository_root_config_references"),
        "modules_with_import_time_executable_statements": module_count("top_level_executable_statements"),
        "modules_with_filesystem_reads": module_count("filesystem_read"),
        "modules_with_filesystem_writes": module_count("filesystem_write"),
        "modules_with_filesystem_move_or_delete": module_count("filesystem_move_or_delete"),
        "modules_with_filesystem_write_move_or_delete": sum(
            record["filesystem_write"] or record["filesystem_move_or_delete"] for record in records
        ),
        "modules_with_subprocess_or_shell": module_count("subprocess_or_shell"),
        "modules_with_network_or_api": module_count("network_or_api"),
        "modules_with_environment_access": module_count("environment_access"),
        "modules_with_credential_access": module_count("credential_access"),
        "modules_with_organization_specific_assumptions": module_count("organization_specific"),
        "modules_with_direct_tests": module_count("direct_tests"),
        "modules_imported_by_tests": module_count("importing_tests"),
        "modules_indirectly_imported_by_tests": module_count("indirect_tests"),
        "modules_with_domain_tests_only": sum(
            bool(record["domain_tests"])
            and not record["direct_tests"]
            and not record["importing_tests"]
            and not record["indirect_tests"]
            for record in records
        ),
        "modules_with_documentation": module_count("documentation"),
        "modules_exposed_in_registry": sum(record["registry_exposed"] for record in records),
        "modules_eligible_for_dynamic_probe": sum(
            record["dynamic_import_probe"]["eligible"] for record in records
        ),
        "modules_dynamically_probed": 0,
        "dynamic_import_failures": 0,
        "wheel_check_status": wheel_status,
        "wheel_modules_included": sum(record["wheel_included"] is True for record in records),
        "wheel_modules_missing": sum(record["wheel_included"] is False for record in records),
    }
    return {
        "schema_version": 1,
        "authoritative_git_scope": HELPER_DIRECTORY,
        "requested_helper_glob": REQUESTED_HELPER_GLOB,
        "methodology": "Tracked-file enumeration plus Python standard-library AST analysis; helper source is never executed.",
        "safety_restrictions": [
            "No helper module is imported or executed by default.",
            "No timestamps or local absolute paths are emitted.",
            "Dynamic probing is eligibility-only and never runs in this tool.",
        ],
        "risk_levels": list(RISK_LEVELS),
        "disposition_values": list(DISPOSITIONS),
        "summary": summary,
        "modules": records,
    }


def write_inventory(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--wheel", type=Path, help="already-built wheel to inspect without installing it")
    arguments = parser.parse_args(argv)
    try:
        payload = build_inventory(arguments.wheel)
        write_inventory(payload, arguments.output)
    except (InventoryError, OSError, UnicodeError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"legacy helper inventory failed: {exc}\n")
    print(
        f"Wrote {payload['summary']['total_modules']} helper records to "
        f"{arguments.output.resolve().relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
