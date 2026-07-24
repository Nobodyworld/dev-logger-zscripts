"""Standard-library AST analyzer that never imports target modules."""

from __future__ import annotations

import ast
import copy
import io
import tokenize
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from zscripts.domain.repository_review import (
    DiagnosticRecord,
    FileRecord,
    ImportRecord,
    ModuleRecord,
    SymbolRecord,
    stable_digest,
)
from zscripts.infrastructure.repository_discovery import AnalysisCancelled, DiscoveredFile

CancellationCheck = Callable[[], bool]
ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True, slots=True)
class PythonAnalysisResult:
    """Sorted metadata evidence extracted from discovered Python files."""

    files: tuple[FileRecord, ...]
    modules: tuple[ModuleRecord, ...]
    symbols: tuple[SymbolRecord, ...]
    diagnostics: tuple[DiagnosticRecord, ...]


class PythonAnalyzer:
    """Extract generic Python structure using :mod:`ast` only."""

    def analyze(
        self,
        files: Sequence[DiscoveredFile],
        *,
        cancelled: CancellationCheck | None = None,
        progress: ProgressCallback | None = None,
    ) -> PythonAnalysisResult:
        cancellation = cancelled or (lambda: False)
        updated_files: list[FileRecord] = []
        modules: list[ModuleRecord] = []
        symbols: list[SymbolRecord] = []
        diagnostics: list[DiagnosticRecord] = []
        included = tuple(item for item in files if item.record.included)
        processed_count = 0

        for discovered in files:
            if cancellation():
                raise AnalysisCancelled("Repository analysis was cancelled.")
            record = discovered.record
            if not record.included:
                updated_files.append(record)
                continue
            if progress is not None:
                progress(processed_count, len(included), record.relative_path)
            parsed = self._analyze_file(discovered)
            updated_files.append(parsed.file)
            if parsed.module is not None:
                modules.append(parsed.module)
            symbols.extend(parsed.symbols)
            diagnostics.extend(parsed.diagnostics)
            processed_count += 1

        if progress is not None:
            progress(len(included), len(included), "")
        return PythonAnalysisResult(
            files=tuple(sorted(updated_files, key=lambda item: item.relative_path)),
            modules=tuple(sorted(modules, key=lambda item: (item.module_name, item.module_id))),
            symbols=tuple(
                sorted(
                    symbols,
                    key=lambda item: (
                        item.relative_path,
                        item.start_line,
                        item.start_column,
                        item.symbol_id,
                    ),
                )
            ),
            diagnostics=tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
        )

    def _analyze_file(self, discovered: DiscoveredFile) -> _ParsedFile:
        record = discovered.record
        content = discovered.content
        if content is None:
            return _ParsedFile(
                file=replace(record, parse_status="missing_content"),
                module=None,
                symbols=(),
                diagnostics=(self._diagnostic(record, "PY_CONTENT_MISSING", "decode_error"),),
            )
        try:
            text = _decode_python(content)
        except (SyntaxError, UnicodeDecodeError, LookupError):
            return _ParsedFile(
                file=replace(record, parse_status="decode_error"),
                module=None,
                symbols=(),
                diagnostics=(self._diagnostic(record, "PY_DECODE_ERROR", "decode_error"),),
            )
        try:
            tree = ast.parse(text, filename=record.relative_path, mode="exec", type_comments=True)
        except SyntaxError as exc:
            return _ParsedFile(
                file=replace(record, parse_status="syntax_error"),
                module=None,
                symbols=(),
                diagnostics=(
                    self._diagnostic(
                        record,
                        "PY_PARSE_ERROR",
                        "parse_error",
                        line=exc.lineno,
                        column=max((exc.offset or 1) - 1, 0),
                    ),
                ),
            )

        module_name = _module_name(record.relative_path)
        imports = tuple(sorted(_extract_imports(tree), key=_import_sort_key))
        exports = tuple(sorted(_extract_public_exports(tree)))
        module = ModuleRecord(
            module_id=stable_digest(
                "repository-review-module",
                {
                    "path": record.relative_path,
                    "file_hash": record.content_hash,
                    "module_name": module_name,
                    "exports": list(exports),
                    "imports": [
                        {
                            "module": item.module,
                            "name": item.imported_name,
                            "alias": item.alias,
                            "level": item.level,
                        }
                        for item in imports
                    ],
                },
            ),
            module_name=module_name,
            package=module_name.rpartition(".")[0],
            file_id=record.file_id,
            relative_path=record.relative_path,
            public_exports=exports,
            imports=imports,
        )
        visitor = _SymbolVisitor(
            module_name=module_name,
            file_id=record.file_id,
            relative_path=record.relative_path,
        )
        visitor.visit(tree)
        return _ParsedFile(
            file=replace(record, parse_status="parsed"),
            module=module,
            symbols=tuple(visitor.symbols),
            diagnostics=(),
        )

    @staticmethod
    def _diagnostic(
        record: FileRecord,
        code: str,
        category: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> DiagnosticRecord:
        message = (
            "Python source could not be decoded."
            if category == "decode_error"
            else "Python syntax could not be parsed."
        )
        payload = {
            "code": code,
            "path": record.relative_path,
            "line": line,
            "column": column,
            "category": category,
        }
        return DiagnosticRecord(
            diagnostic_id=stable_digest("repository-review-diagnostic", payload),
            code=code,
            severity="warning",
            message=message,
            relative_path=record.relative_path,
            line=line,
            column=column,
            category=category,
        )


@dataclass(frozen=True, slots=True)
class _ParsedFile:
    file: FileRecord
    module: ModuleRecord | None
    symbols: tuple[SymbolRecord, ...]
    diagnostics: tuple[DiagnosticRecord, ...]


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, *, module_name: str, file_id: str, relative_path: str) -> None:
        self.module_name = module_name
        self.file_id = file_id
        self.relative_path = relative_path
        self.symbols: list[SymbolRecord] = []
        self._stack: list[SymbolRecord] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802 - ast visitor contract
        bases = tuple(_safe_unparse(item) for item in node.bases)
        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"
        symbol = self._build_symbol(
            node,
            kind="class",
            signature=signature,
            annotations=(),
            async_flag=False,
            bases=bases,
        )
        self._visit_scope(node, symbol)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 - ast visitor contract
        self._visit_function(node, async_flag=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node, async_flag=True)

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        async_flag: bool,
    ) -> None:
        kind = "method" if self._stack and self._stack[-1].kind == "class" else "function"
        signature, annotations = _function_signature(node)
        symbol = self._build_symbol(
            node,
            kind=kind,
            signature=signature,
            annotations=annotations,
            async_flag=async_flag,
            bases=(),
        )
        self._visit_scope(node, symbol)

    def _visit_scope(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        symbol: SymbolRecord,
    ) -> None:
        self.symbols.append(symbol)
        self._stack.append(symbol)
        self.generic_visit(node)
        self._stack.pop()

    def _build_symbol(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        kind: str,
        signature: str,
        annotations: tuple[str, ...],
        async_flag: bool,
        bases: tuple[str, ...],
    ) -> SymbolRecord:
        names = [item.display_name for item in self._stack]
        names.append(node.name)
        qualified_name = ".".join((self.module_name, *names)) if self.module_name else ".".join(names)
        content_fingerprint = stable_digest(
            "repository-review-symbol-content",
            ast.dump(node, annotate_fields=True, include_attributes=False),
        )
        end_line = int(getattr(node, "end_lineno", None) or node.lineno)
        end_column = int(getattr(node, "end_col_offset", None) or node.col_offset)
        symbol_id = stable_digest(
            "repository-review-symbol",
            {
                "path": self.relative_path,
                "kind": kind,
                "qualified_name": qualified_name,
                "start_line": node.lineno,
                "start_column": node.col_offset,
                "end_line": end_line,
                "end_column": end_column,
                "content_fingerprint": content_fingerprint,
            },
        )
        return SymbolRecord(
            symbol_id=symbol_id,
            language="python",
            kind=kind,
            qualified_name=qualified_name,
            display_name=node.name,
            module_name=self.module_name,
            file_id=self.file_id,
            relative_path=self.relative_path,
            start_line=node.lineno,
            start_column=node.col_offset,
            end_line=end_line,
            end_column=end_column,
            parent_symbol_id=self._stack[-1].symbol_id if self._stack else None,
            visibility=_visibility(node.name),
            signature=signature,
            annotations=annotations,
            decorators=tuple(_safe_metadata_unparse(item) for item in node.decorator_list),
            docstring_present=ast.get_docstring(node, clean=False) is not None,
            async_flag=async_flag,
            content_fingerprint=content_fingerprint,
            bases=bases,
        )


def _decode_python(content: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(content).readline)
    return content.decode(encoding)


def _module_name(relative_path: str) -> str:
    path = PurePosixPath(relative_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"src", "lib"}:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _extract_imports(tree: ast.Module) -> list[ImportRecord]:
    imports: list[ImportRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportRecord(
                        module=alias.name,
                        imported_name=None,
                        alias=alias.asname,
                        level=0,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.append(
                    ImportRecord(
                        module=node.module,
                        imported_name=alias.name,
                        alias=alias.asname,
                        level=node.level,
                    )
                )
    return imports


def _extract_public_exports(tree: ast.Module) -> set[str]:
    exports: set[str] = set()
    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "__all__":
                value = node.value
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            for element in value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    exports.add(element.value)
    return exports


def _function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[str, tuple[str, ...]]:
    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(arguments.defaults))
    defaults.extend(arguments.defaults)
    annotations: list[str] = []
    rendered: list[str] = []
    for index, (argument, default) in enumerate(zip(positional, defaults, strict=True)):
        rendered_argument = _render_argument(argument, default, annotations)
        rendered.append(rendered_argument)
        if arguments.posonlyargs and index + 1 == len(arguments.posonlyargs):
            rendered.append("/")
    if arguments.vararg is not None:
        rendered.append(f"*{_render_argument(arguments.vararg, None, annotations)}")
    elif arguments.kwonlyargs:
        rendered.append("*")
    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
        rendered.append(_render_argument(argument, default, annotations))
    if arguments.kwarg is not None:
        rendered.append(f"**{_render_argument(arguments.kwarg, None, annotations)}")
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    signature = f"{prefix} {node.name}({', '.join(rendered)})"
    if node.returns is not None:
        return_annotation = _safe_unparse(node.returns)
        annotations.append(f"return: {return_annotation}")
        signature += f" -> {return_annotation}"
    return signature, tuple(annotations)


def _render_argument(
    argument: ast.arg,
    default: ast.expr | None,
    annotations: list[str],
) -> str:
    rendered = argument.arg
    if argument.annotation is not None:
        annotation = _safe_unparse(argument.annotation)
        annotations.append(f"{argument.arg}: {annotation}")
        rendered += f": {annotation}"
    if default is not None:
        rendered += f" = {_safe_metadata_unparse(default)}"
    return rendered


def _safe_metadata_unparse(node: ast.AST) -> str:
    """Render metadata while replacing source string and byte literal values."""

    scrubbed = _LiteralScrubber().visit(copy.deepcopy(node))
    return _safe_unparse(scrubbed)


class _LiteralScrubber(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.AST:  # noqa: N802 - ast visitor contract
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value="<string>"), node)
        if isinstance(node.value, bytes):
            return ast.copy_location(ast.Constant(value=b"<bytes>"), node)
        return node


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node).replace("\r\n", "\n").replace("\r", "\n")
    except (AttributeError, ValueError):
        return ast.dump(node, annotate_fields=True, include_attributes=False)


def _visibility(name: str) -> str:
    if name.startswith("__") and name.endswith("__"):
        return "dunder"
    if name.startswith("_"):
        return "private"
    return "public"


def _import_sort_key(record: ImportRecord) -> tuple[str, str, str, int]:
    return (
        record.module or "",
        record.imported_name or "",
        record.alias or "",
        record.level,
    )


__all__ = ["PythonAnalysisResult", "PythonAnalyzer"]
