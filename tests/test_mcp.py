"""Tests for the MCP server."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock
import json

from wiswa.mcp import (
    clear_resolved_defaults_cache,
    get_defaults,
    list_settings,
    lookup_setting,
    search_settings,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_mock import MockerFixture

MOCK_DEFAULTS: dict[str, Any] = {
    'project_name': 'test',
    'line_width': 100,
    'want_main': False,
    'keywords': ['python'],
    'ratio': 1.5,
    'nullable_opt': None,
    'complex_num': 1 + 2j,
    'opaque_tuple': ('t',),
    'empty_list': [],
    'empty_dict': {},
    'pyproject': {
        'tool': {
            'ruff': {
                'line-length': 100,
                'target-version': 'py310',
            },
        },
        'project': {
            'name': 'test',
        },
    },
    'social': {
        'bsky': '',
        'mastodon': {
            'id': '',
            'domain': 'hostux.social',
        },
    },
}


@pytest.fixture(autouse=True)
def mock_defaults(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.mcp.resolve_defaults_only',
                 new_callable=AsyncMock,
                 return_value=MOCK_DEFAULTS)


@pytest.fixture(autouse=True)
def clear_mcp_cache() -> Iterator[None]:
    yield
    clear_resolved_defaults_cache()


class TestGetDefaultsReal:
    @staticmethod
    async def test_resolves_and_caches(mocker: MockerFixture) -> None:
        mocker.stopall()
        clear_resolved_defaults_cache()
        mock_session = AsyncMock()
        mock_session_cls = mocker.patch('wiswa.mcp.niquests.AsyncSession',
                                        return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_resolve = mocker.patch('wiswa.mcp.resolve_defaults_only',
                                    new_callable=AsyncMock,
                                    return_value={'a': 1})
        result_json = await get_defaults()
        assert json.loads(result_json) == {'a': 1}
        mock_session_cls.assert_called_once()
        mock_resolve.assert_called_once()
        call_kwargs = mock_resolve.call_args
        assert call_kwargs[1].get('session', call_kwargs[0][2]) is mock_session
        result2_json = await get_defaults()
        assert json.loads(result2_json) == {'a': 1}
        assert mock_resolve.call_count == 1
        assert mock_session_cls.call_count == 1


class TestGetDefaults:
    @staticmethod
    async def test_all() -> None:
        result = json.loads(await get_defaults())
        assert result['project_name'] == 'test'

    @staticmethod
    async def test_key_path() -> None:
        result = json.loads(await get_defaults('pyproject.tool.ruff'))
        assert result['line-length'] == 100

    @staticmethod
    async def test_scalar() -> None:
        result = json.loads(await get_defaults('line_width'))
        assert result == 100

    @staticmethod
    async def test_missing() -> None:
        result = json.loads(await get_defaults('nonexistent'))
        assert 'error' in result


class TestLookupSetting:
    @staticmethod
    async def test_scalar() -> None:
        result = json.loads(await lookup_setting('line_width'))
        assert result['default_value'] == 100
        assert result['type'] == 'number'
        assert 'override_snippet' in result

    @staticmethod
    async def test_nested() -> None:
        result = json.loads(await lookup_setting('pyproject.tool.ruff.line-length'))
        assert result['default_value'] == 100
        assert 'pyproject+:' in result['override_snippet']

    @staticmethod
    async def test_object_notes() -> None:
        result = json.loads(await lookup_setting('social'))
        assert result['type'] == 'object'
        assert any('merge' in n.lower() for n in result['notes'])

    @staticmethod
    async def test_array_notes() -> None:
        result = json.loads(await lookup_setting('keywords'))
        assert result['type'] == 'array'
        assert any('append' in n.lower() for n in result['notes'])

    @staticmethod
    async def test_missing() -> None:
        result = json.loads(await lookup_setting('nonexistent'))
        assert 'error' in result


class TestListSettings:
    @staticmethod
    async def test_top_level() -> None:
        result = json.loads(await list_settings())
        keys = [e['key'] for e in result]
        assert 'project_name' in keys
        assert 'line_width' in keys

    @staticmethod
    async def test_nested() -> None:
        result = json.loads(await list_settings('pyproject.tool'))
        keys = [e['key'] for e in result]
        assert 'ruff' in keys

    @staticmethod
    async def test_depth() -> None:
        result = json.loads(await list_settings('pyproject', depth=2))
        keys = [e['key'] for e in result]
        assert 'tool.ruff' in keys

    @staticmethod
    async def test_non_object() -> None:
        result = json.loads(await list_settings('line_width'))
        assert 'error' in result

    @staticmethod
    async def test_missing() -> None:
        result = json.loads(await list_settings('nonexistent'))
        assert 'error' in result


class TestSearchSettings:
    @staticmethod
    async def test_substring() -> None:
        result = json.loads(await search_settings('want_'))
        paths = [e['key_path'] for e in result]
        assert 'want_main' in paths

    @staticmethod
    async def test_nested_match() -> None:
        result = json.loads(await search_settings('line-length'))
        paths = [e['key_path'] for e in result]
        assert 'pyproject.tool.ruff.line-length' in paths

    @staticmethod
    async def test_no_match() -> None:
        result = json.loads(await search_settings('zzz_nonexistent_zzz'))
        assert result == []

    @staticmethod
    async def test_match_dict_value() -> None:
        result = json.loads(await search_settings('mastodon'))
        entries = {e['key_path']: e for e in result}
        assert 'social.mastodon' in entries
        assert entries['social.mastodon']['type'] == 'object'
        assert 'default_value' not in entries['social.mastodon']

    @staticmethod
    async def test_match_list_value() -> None:
        result = json.loads(await search_settings('keywords'))
        entries = {e['key_path']: e for e in result}
        assert 'keywords' in entries
        assert entries['keywords']['type'] == 'array'
        assert 'default_value' not in entries['keywords']


class TestGetDefaultsExtended:
    @staticmethod
    async def test_key_path_to_list() -> None:
        result = json.loads(await get_defaults('keywords'))
        assert result == ['python']


class TestLookupSettingExtended:
    @staticmethod
    async def test_string_no_notes() -> None:
        result = json.loads(await lookup_setting('project_name'))
        assert result['type'] == 'string'
        assert result['notes'] == []

    @staticmethod
    async def test_boolean_no_notes() -> None:
        result = json.loads(await lookup_setting('want_main'))
        assert result['type'] == 'boolean'
        assert result['notes'] == []
        assert 'false' in result['override_snippet']


class TestLookupSettingOverrideSnippetJsonnet:
    """Exercise _json_value_to_jsonnet via public lookup_setting only."""
    @staticmethod
    async def test_scalar_number_in_snippet() -> None:
        result = json.loads(await lookup_setting('line_width'))
        assert '100' in result['override_snippet']

    @staticmethod
    async def test_float_in_snippet() -> None:
        result = json.loads(await lookup_setting('ratio'))
        assert '1.5' in result['override_snippet']

    @staticmethod
    async def test_none_as_null() -> None:
        result = json.loads(await lookup_setting('nullable_opt'))
        assert 'null' in result['override_snippet']

    @staticmethod
    async def test_list_multiline() -> None:
        result = json.loads(await lookup_setting('keywords'))
        assert '"python"' in result['override_snippet']

    @staticmethod
    async def test_empty_list() -> None:
        result = json.loads(await lookup_setting('empty_list'))
        assert '[]' in result['override_snippet']

    @staticmethod
    async def test_empty_dict() -> None:
        result = json.loads(await lookup_setting('empty_dict'))
        snippet = result['override_snippet'].replace(' ', '')
        assert '{}' in snippet

    @staticmethod
    async def test_complex_repr_fallback() -> None:
        result = json.loads(await lookup_setting('complex_num'))
        snippet = result['override_snippet']
        assert 'j' in snippet

    @staticmethod
    async def test_tuple_serializes_as_jsonnet_list() -> None:
        result = json.loads(await lookup_setting('opaque_tuple'))
        assert '"t"' in result['override_snippet']
        snippet = result['override_snippet']
        assert '[' in snippet
        assert ']' in snippet


class TestListSettingsExtended:
    @staticmethod
    async def test_depth_zero() -> None:
        result = json.loads(await list_settings(depth=0))
        assert result == []

    @staticmethod
    async def test_depth_three_recurses_deep() -> None:
        result = json.loads(await list_settings('pyproject', depth=3))
        keys = [e['key'] for e in result]
        assert 'tool.ruff.line-length' in keys


class TestListSettingsNonJsonTypes:
    @staticmethod
    async def test_complex_type_name() -> None:
        result = json.loads(await list_settings())
        by_key = {e['key']: e for e in result}
        assert by_key['complex_num']['type'] == 'complex'

    @staticmethod
    async def test_tuple_type_name() -> None:
        result = json.loads(await list_settings())
        by_key = {e['key']: e for e in result}
        assert by_key['opaque_tuple']['type'] == 'tuple'


class TestSearchSettingsNonJsonTypes:
    @staticmethod
    async def test_complex_entry() -> None:
        result = json.loads(await search_settings('complex_num'))
        entry = next(e for e in result if e['key_path'] == 'complex_num')
        assert entry['type'] == 'complex'

    @staticmethod
    async def test_tuple_entry() -> None:
        result = json.loads(await search_settings('opaque'))
        entry = next(e for e in result if e['key_path'] == 'opaque_tuple')
        assert entry['type'] == 'tuple'
