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
    TypeReferenceCandidate,
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
    type_references: tuple[TypeReferenceCandidate, ...]


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
        type_references: list[TypeReferenceCandidate] = []
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
            type_references.extend(parsed.type_references)
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
            type_references=tuple(
                sorted(
                    type_references,
                    key=lambda item: (
                        item.relative_path,
                        item.line,
                        item.column,
                        item.candidate_id,
                    ),
                )
            ),
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
                type_references=(),
            )
        try:
            text = _decode_python(content)
        except (SyntaxError, UnicodeDecodeError, LookupError):
            return _ParsedFile(
                file=replace(record, parse_status="decode_error"),
                module=None,
                symbols=(),
                diagnostics=(self._diagnostic(record, "PY_DECODE_ERROR", "decode_error"),),
                type_references=(),
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
                type_references=(),
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
                            "line": item.line,
                            "column": item.column,
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
            type_references=tuple(visitor.type_references),
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
    type_references: tuple[TypeReferenceCandidate, ...]


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, *, module_name: str, file_id: str, relative_path: str) -> None:
        self.module_name = module_name
        self.file_id = file_id
        self.relative_path = relative_path
        self.symbols: list[SymbolRecord] = []
        self.type_references: list[TypeReferenceCandidate] = []
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
        self._record_type_references(node, symbol)
        self._stack.append(symbol)
        self.generic_visit(node)
        self._stack.pop()

    def _record_type_references(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        symbol: SymbolRecord,
    ) -> None:
        for reference_node, textual_name, candidate_kind, evidence in _scope_type_references(node):
            location_node = node if candidate_kind == "inheritance" else reference_node
            line = int(getattr(location_node, "lineno", node.lineno))
            column = int(getattr(location_node, "col_offset", node.col_offset))
            payload = {
                "source_symbol_id": symbol.symbol_id,
                "name": textual_name,
                "path": self.relative_path,
                "line": line,
                "column": column,
                "kind": candidate_kind,
                "evidence": evidence,
            }
            self.type_references.append(
                TypeReferenceCandidate(
                    candidate_id=stable_digest("repository-review-type-candidate", payload),
                    source_symbol_id=symbol.symbol_id,
                    module_name=self.module_name,
                    textual_name=textual_name,
                    relative_path=self.relative_path,
                    line=line,
                    column=column,
                    evidence=evidence,
                    candidate_kind=candidate_kind,
                )
            )

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
                        line=node.lineno,
                        column=node.col_offset,
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
                        line=node.lineno,
                        column=node.col_offset,
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


def _scope_type_references(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[ast.AST, str, str, str]]:
    references: list[tuple[ast.AST, str, str, str]] = []
    if isinstance(node, ast.ClassDef):
        for base in node.bases:
            name = _base_reference_name(base)
            if name:
                references.append((base, name, "inheritance", _bounded_unparse(base)))
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign):
                references.extend(_annotation_references(statement.annotation, "type"))
        return _deduplicate_references(references)

    arguments = node.args
    for argument in (
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
    ):
        if argument.annotation is not None:
            references.extend(_annotation_references(argument.annotation, "type"))
    if arguments.vararg is not None and arguments.vararg.annotation is not None:
        references.extend(_annotation_references(arguments.vararg.annotation, "type"))
    if arguments.kwarg is not None and arguments.kwarg.annotation is not None:
        references.extend(_annotation_references(arguments.kwarg.annotation, "type"))
    if node.returns is not None:
        references.extend(_annotation_references(node.returns, "type"))
    collector = _AttributeAnnotationCollector()
    for statement in node.body:
        collector.visit(statement)
    for annotation in collector.annotations:
        references.extend(_annotation_references(annotation, "type"))
    return _deduplicate_references(references)


class _AttributeAnnotationCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.annotations: list[ast.expr] = []

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802 - ast visitor contract
        if isinstance(node.target, ast.Attribute):
            self.annotations.append(node.annotation)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802 - nested scope
        return

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 - nested scope
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802 - nested scope
        return


def _annotation_references(
    annotation: ast.expr,
    candidate_kind: str,
) -> list[tuple[ast.AST, str, str, str]]:
    evidence = _bounded_unparse(annotation)
    return [
        (reference_node, name, candidate_kind, evidence)
        for reference_node, name in _bounded_type_names(annotation)
    ]


def _bounded_type_names(node: ast.AST) -> list[tuple[ast.AST, str]]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value.strip()
        if not value or len(value) > 256:
            return []
        try:
            parsed = ast.parse(value, mode="eval")
        except SyntaxError:
            return [(node, value)] if _is_dotted_name(value) else []
        return [(node, name) for _, name in _bounded_type_names(parsed.body)]
    dotted = _dotted_name(node)
    if dotted is not None:
        return [(node, dotted)]
    if isinstance(node, ast.Subscript):
        outer = _dotted_name(node.value)
        if outer in _LITERAL_SPECIAL_FORMS:
            return []
        if outer in _ANNOTATED_SPECIAL_FORMS:
            annotated_type = node.slice.elts[0] if isinstance(node.slice, ast.Tuple) else node.slice
            return _bounded_type_names(annotated_type)
        results: list[tuple[ast.AST, str]] = []
        if outer and outer not in _GENERIC_CONTAINER_NAMES:
            results.append((node.value, outer))
        results.extend(_bounded_type_names(node.slice))
        return results
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return [*_bounded_type_names(node.left), *_bounded_type_names(node.right)]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [item for element in node.elts for item in _bounded_type_names(element)]
    return []


def _base_reference_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Subscript):
        return _dotted_name(node.value)
    return _dotted_name(node)


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _is_dotted_name(value: str) -> bool:
    return all(part.isidentifier() for part in value.split("."))


def _bounded_unparse(node: ast.AST) -> str:
    return _safe_unparse(node)[:256]


def _deduplicate_references(
    references: list[tuple[ast.AST, str, str, str]],
) -> list[tuple[ast.AST, str, str, str]]:
    result: list[tuple[ast.AST, str, str, str]] = []
    seen: set[tuple[int, int, str, str]] = set()
    for reference in references:
        node, name, kind, _ = reference
        key = (
            int(getattr(node, "lineno", 0)),
            int(getattr(node, "col_offset", 0)),
            name,
            kind,
        )
        if key not in seen:
            seen.add(key)
            result.append(reference)
    return result


_LITERAL_SPECIAL_FORMS = {
    "Literal",
    "typing.Literal",
    "typing_extensions.Literal",
}

_ANNOTATED_SPECIAL_FORMS = {
    "Annotated",
    "typing.Annotated",
    "typing_extensions.Annotated",
}

_GENERIC_CONTAINER_NAMES = {
    "Annotated",
    "Callable",
    "ClassVar",
    "Final",
    "Iterable",
    "Literal",
    "Mapping",
    "Optional",
    "Sequence",
    "Type",
    "Union",
    "dict",
    "frozenset",
    "list",
    "set",
    "tuple",
    "typing.Annotated",
    "typing.Callable",
    "typing.ClassVar",
    "typing.Final",
    "typing.Iterable",
    "typing.Literal",
    "typing.Mapping",
    "typing.Optional",
    "typing.Sequence",
    "typing.Type",
    "typing.Union",
    "typing_extensions.Annotated",
    "typing_extensions.Literal",
}


def _visibility(name: str) -> str:
    if name.startswith("__") and name.endswith("__"):
        return "dunder"
    if name.startswith("_"):
        return "private"
    return "public"


def _import_sort_key(record: ImportRecord) -> tuple[str, str, str, int, int, int]:
    return (
        record.module or "",
        record.imported_name or "",
        record.alias or "",
        record.level,
        record.line,
        record.column,
    )


__all__ = ["PythonAnalysisResult", "PythonAnalyzer"]
