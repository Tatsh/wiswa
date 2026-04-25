"""FastMCP server for Wiswa settings."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
import importlib.resources
import json
import re

from fastmcp import FastMCP
import niquests

from .utils.jsonnet import resolve_defaults_only

__all__ = ('clear_resolved_defaults_cache', 'main')

mcp = FastMCP('wiswa')

_resolved_defaults: dict[str, Any] | None = None
_IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


async def _get_defaults() -> dict[str, Any]:
    global _resolved_defaults  # noqa: PLW0603
    if _resolved_defaults is None:
        marker = importlib.resources.files('wiswa-jsonnet') / 'defaults.libsonnet'
        with importlib.resources.as_file(marker) as defaults_file:
            lib_path = Path(defaults_file).parent
            async with niquests.AsyncSession() as session:
                _resolved_defaults = await resolve_defaults_only([str(lib_path)], lib_path, session)
    return _resolved_defaults


def clear_resolved_defaults_cache() -> None:
    """Forget lazily loaded Jsonnet defaults (for tests and development server reload)."""
    global _resolved_defaults  # noqa: PLW0603
    _resolved_defaults = None


def _navigate(data: Any, parts: list[str]) -> Any:
    for part in parts:
        if not isinstance(data, dict) or part not in data:
            msg = f'Key not found: {part}'
            raise KeyError(msg)
        data = data[part]
    return data


def _format_key(key: str, *, merge: bool = False) -> str:
    quoted = key if _IDENT_RE.match(key) else f"'{key}'"
    return f'{quoted}+' if merge else quoted


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


def _json_value_to_jsonnet(value: Any, indent: int = 0) -> str:
    prefix = '  ' * indent
    inner = '  ' * (indent + 1)
    match value:
        case None:
            return 'null'
        case bool():
            return 'true' if value else 'false'
        case int() | float():
            return str(value)
        case str():
            return json.dumps(value)
        case Sequence() if not isinstance(value, str | bytes | bytearray):
            if not value:
                return '[]'
            items = [f'{inner}{_json_value_to_jsonnet(v, indent + 1)}' for v in value]
            return '[\n' + ',\n'.join(items) + ',\n' + prefix + ']'
        case Mapping():
            if not value:
                return '{}'
            lines = []
            for k, v in value.items():
                formatted_key = _format_key(k)
                formatted_val = _json_value_to_jsonnet(v, indent + 1)
                lines.append(f'{inner}{formatted_key}: {formatted_val}')
            return '{\n' + ',\n'.join(lines) + ',\n' + prefix + '}'
    return repr(value)


async def _generate_override_snippet(key_path: str, value: Any) -> str:
    parts = key_path.split('.')
    defaults = await _get_defaults()
    lines: list[str] = []
    indent = 0
    current = defaults
    for i, part in enumerate(parts):
        prefix = '  ' * indent
        is_leaf = i == len(parts) - 1
        if is_leaf:
            formatted_val = _json_value_to_jsonnet(value, indent)
            lines.append(f'{prefix}{_format_key(part)}: {formatted_val},')
        else:
            child = current.get(part) if isinstance(current, dict) else None
            merge = isinstance(child, dict)
            lines.append(f'{prefix}{_format_key(part, merge=merge)}: {{')
            if isinstance(current, dict):  # pragma: no branch
                current = current.get(part, {})
            indent += 1
    lines.extend(f'{"  " * i}}},' for i in range(indent - 1, -1, -1))
    return '\n'.join(lines)


def _type_name(value: Any) -> str:
    match value:
        case bool():
            return 'boolean'
        case int() | float():
            return 'number'
        case str():
            return 'string'
        case list():
            return 'array'
        case dict():
            return 'object'
        case _:
            return type(value).__name__


def _collect_paths(data: Any, prefix: str = '') -> list[str]:
    paths: list[str] = []
    if isinstance(data, dict):
        for key, val in data.items():
            full = f'{prefix}.{key}' if prefix else key
            paths.append(full)
            paths.extend(_collect_paths(val, full))
    return paths


@mcp.tool()
async def get_defaults(key_path: str | None = None) -> str:
    """
    Get resolved default settings, optionally narrowed to a dot-separated key path.

    Parameters
    ----------
    key_path : str | None
        Dot-separated path into the defaults tree, or ``None`` for the full document.

    Returns
    -------
    str
        JSON text for the resolved value or an error object.

    Notes
    -----
    Examples: ``get_defaults("pyproject.tool.ruff")``, ``get_defaults()`` for all defaults.
    """
    defaults = await _get_defaults()
    if key_path is None:
        return _json_dumps(defaults)
    try:
        result = _navigate(defaults, key_path.split('.'))
    except KeyError:
        return _json_dumps({'error': f'Key path not found: {key_path}'})
    return _json_dumps(result)


@mcp.tool()
async def lookup_setting(key_path: str) -> str:
    """
    Look up a setting by dot-separated key path and get its default value plus override snippet.

    Parameters
    ----------
    key_path : str
        Dot-separated path to the setting.

    Returns
    -------
    str
        JSON text with default value, type, override snippet, and notes.

    Notes
    -----
    Example: ``lookup_setting("pyproject.tool.ruff.line-length")``
    """
    defaults = await _get_defaults()
    try:
        value = _navigate(defaults, key_path.split('.'))
    except KeyError:
        return _json_dumps({'error': f'Key path not found: {key_path}'})
    value_type = _type_name(value)
    snippet = await _generate_override_snippet(key_path, value)
    notes: list[str] = []
    match value_type:
        case 'object':
            notes.extend(
                ('Use +: (merge operator) at each nesting level to deep-merge with defaults.',
                 'Use : (without +) to replace the entire object.'))
        case 'array':
            notes.append('Use +: to append to the default array, or : to replace it entirely.')
    return _json_dumps({
        'key_path': key_path,
        'default_value': value,
        'type': value_type,
        'override_snippet': snippet,
        'notes': notes
    })


@mcp.tool()
async def list_settings(key_path: str | None = None, depth: int = 1) -> str:
    """
    List setting keys at a given path and depth.

    Parameters
    ----------
    key_path : str | None
        Dot-separated path prefix, or ``None`` for the root.
    depth : int
        How many object levels to expand.

    Returns
    -------
    str
        JSON list of key metadata entries or an error object.

    Notes
    -----
    Examples: ``list_settings()`` for top-level keys,
    ``list_settings("pyproject.tool", depth=2)``.
    """
    defaults = await _get_defaults()
    try:
        data = _navigate(defaults, key_path.split('.')) if key_path else defaults
    except KeyError:
        return _json_dumps({'error': f'Key path not found: {key_path}'})
    if not isinstance(data, dict):
        return _json_dumps({
            'error': f'{key_path} is a {_type_name(data)}, not an object. Use get_defaults instead.'
        })
    entries: list[dict[str, Any]] = []

    def _walk(obj: Any, current_depth: int, prefix: str = '') -> None:
        if not isinstance(obj, dict) or current_depth > depth:
            return
        for key, val in obj.items():
            full = f'{prefix}.{key}' if prefix else key
            entry: dict[str, Any] = {'key': full, 'type': _type_name(val)}
            if not isinstance(val, dict | list):
                entry['value'] = val
            elif isinstance(val, dict):
                entry['child_keys'] = len(val)
            else:
                entry['length'] = len(val)
            entries.append(entry)
            if isinstance(val, dict) and current_depth < depth:
                _walk(val, current_depth + 1, full)

    _walk(data, 1)
    return _json_dumps(entries)


@mcp.tool()
async def search_settings(query: str) -> str:
    """
    Search for settings by substring match on their fully-qualified key path.

    Parameters
    ----------
    query : str
        Substring matched against fully-qualified key paths.

    Returns
    -------
    str
        JSON list of matching settings with types and scalar defaults.

    Notes
    -----
    Example: ``search_settings("want_")`` to find all boolean feature flags.
    """
    defaults = await _get_defaults()
    all_paths = _collect_paths(defaults)
    matches: list[dict[str, Any]] = []
    for path in all_paths:
        if query in path:
            try:
                val = _navigate(defaults, path.split('.'))
            except KeyError:  # pragma: no cover
                continue
            entry: dict[str, Any] = {'key_path': path, 'type': _type_name(val)}
            if not isinstance(val, dict | list):
                entry['default_value'] = val
            matches.append(entry)
    return _json_dumps(matches)


def main() -> None:  # pragma: no cover
    """Entry point for the Wiswa MCP server."""
    mcp.run()
