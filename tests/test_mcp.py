"""Tests for the MCP server."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
import json

from wiswa.mcp import (
    collect_paths,
    format_key,
    generate_override_snippet,
    get_defaults,
    json_value_to_jsonnet,
    list_settings,
    lookup_setting,
    navigate,
    search_settings,
    type_name,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

MOCK_DEFAULTS: dict[str, Any] = {
    'project_name': 'test',
    'line_width': 100,
    'want_main': False,
    'keywords': ['python'],
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
def _mock_defaults(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.mcp._get_defaults', return_value=MOCK_DEFAULTS)


class TestNavigate:
    @staticmethod
    def test_simple_key() -> None:
        assert navigate(MOCK_DEFAULTS, ['project_name']) == 'test'

    @staticmethod
    def test_nested_key() -> None:
        assert navigate(MOCK_DEFAULTS, ['pyproject', 'tool', 'ruff', 'line-length']) == 100

    @staticmethod
    def test_empty_parts() -> None:
        assert navigate(MOCK_DEFAULTS, []) == MOCK_DEFAULTS

    @staticmethod
    def test_missing_key() -> None:
        with pytest.raises(KeyError):
            navigate(MOCK_DEFAULTS, ['nonexistent'])

    @staticmethod
    def test_missing_nested_key() -> None:
        with pytest.raises(KeyError):
            navigate(MOCK_DEFAULTS, ['pyproject', 'tool', 'nonexistent'])


class TestFormatKey:
    @staticmethod
    def test_simple_identifier() -> None:
        assert format_key('project_name') == 'project_name'

    @staticmethod
    def test_hyphenated_key() -> None:
        assert format_key('line-length') == "'line-length'"

    @staticmethod
    def test_merge_operator() -> None:
        assert format_key('tool', merge=True) == 'tool+'

    @staticmethod
    def test_hyphenated_merge() -> None:
        assert format_key('line-length', merge=True) == "'line-length'+"


class TestJsonValueToJsonnet:
    @staticmethod
    def test_null() -> None:
        assert json_value_to_jsonnet(None) == 'null'

    @staticmethod
    def test_bool_true() -> None:
        assert json_value_to_jsonnet(value=True) == 'true'

    @staticmethod
    def test_bool_false() -> None:
        assert json_value_to_jsonnet(value=False) == 'false'

    @staticmethod
    def test_int() -> None:
        assert json_value_to_jsonnet(42) == '42'

    @staticmethod
    def test_string() -> None:
        assert json_value_to_jsonnet('hello') == '"hello"'

    @staticmethod
    def test_empty_list() -> None:
        assert json_value_to_jsonnet([]) == '[]'

    @staticmethod
    def test_empty_dict() -> None:
        assert json_value_to_jsonnet({}) == '{}'

    @staticmethod
    def test_list() -> None:
        result = json_value_to_jsonnet(['a', 'b'])
        assert '"a"' in result
        assert '"b"' in result

    @staticmethod
    def test_dict() -> None:
        result = json_value_to_jsonnet({'key': 'val'})
        assert 'key: "val"' in result


class TestTypeName:
    @staticmethod
    def test_boolean() -> None:
        assert type_name(value=True) == 'boolean'

    @staticmethod
    def test_int() -> None:
        assert type_name(42) == 'number'

    @staticmethod
    def test_string() -> None:
        assert type_name('x') == 'string'

    @staticmethod
    def test_list() -> None:
        assert type_name([]) == 'array'

    @staticmethod
    def test_dict() -> None:
        assert type_name({}) == 'object'


class TestCollectPaths:
    @staticmethod
    def test_flat() -> None:
        paths = collect_paths({'a': 1, 'b': 2})
        assert 'a' in paths
        assert 'b' in paths

    @staticmethod
    def test_nested() -> None:
        paths = collect_paths({'a': {'b': {'c': 1}}})
        assert 'a' in paths
        assert 'a.b' in paths
        assert 'a.b.c' in paths

    @staticmethod
    def test_non_dict() -> None:
        assert collect_paths('string') == []


class TestGenerateOverrideSnippet:
    @staticmethod
    def test_top_level_scalar() -> None:
        result = generate_override_snippet('line_width', 120)
        assert 'line_width: 120,' in result

    @staticmethod
    def test_nested_with_merge() -> None:
        result = generate_override_snippet('pyproject.tool.ruff.line-length', 120)
        assert 'pyproject+:' in result
        assert 'tool+:' in result
        assert 'ruff+:' in result
        assert "'line-length': 120," in result


class TestGetDefaults:
    @staticmethod
    def test_all() -> None:
        result = json.loads(get_defaults())
        assert result['project_name'] == 'test'

    @staticmethod
    def test_key_path() -> None:
        result = json.loads(get_defaults('pyproject.tool.ruff'))
        assert result['line-length'] == 100

    @staticmethod
    def test_scalar() -> None:
        result = json.loads(get_defaults('line_width'))
        assert result == 100

    @staticmethod
    def test_missing() -> None:
        result = json.loads(get_defaults('nonexistent'))
        assert 'error' in result


class TestLookupSetting:
    @staticmethod
    def test_scalar() -> None:
        result = json.loads(lookup_setting('line_width'))
        assert result['default_value'] == 100
        assert result['type'] == 'number'
        assert 'override_snippet' in result

    @staticmethod
    def test_nested() -> None:
        result = json.loads(lookup_setting('pyproject.tool.ruff.line-length'))
        assert result['default_value'] == 100
        assert 'pyproject+:' in result['override_snippet']

    @staticmethod
    def test_object_notes() -> None:
        result = json.loads(lookup_setting('social'))
        assert result['type'] == 'object'
        assert any('merge' in n.lower() for n in result['notes'])

    @staticmethod
    def test_array_notes() -> None:
        result = json.loads(lookup_setting('keywords'))
        assert result['type'] == 'array'
        assert any('append' in n.lower() for n in result['notes'])

    @staticmethod
    def test_missing() -> None:
        result = json.loads(lookup_setting('nonexistent'))
        assert 'error' in result


class TestListSettings:
    @staticmethod
    def test_top_level() -> None:
        result = json.loads(list_settings())
        keys = [e['key'] for e in result]
        assert 'project_name' in keys
        assert 'line_width' in keys

    @staticmethod
    def test_nested() -> None:
        result = json.loads(list_settings('pyproject.tool'))
        keys = [e['key'] for e in result]
        assert 'ruff' in keys

    @staticmethod
    def test_depth() -> None:
        result = json.loads(list_settings('pyproject', depth=2))
        keys = [e['key'] for e in result]
        assert 'tool.ruff' in keys

    @staticmethod
    def test_non_object() -> None:
        result = json.loads(list_settings('line_width'))
        assert 'error' in result

    @staticmethod
    def test_missing() -> None:
        result = json.loads(list_settings('nonexistent'))
        assert 'error' in result


class TestSearchSettings:
    @staticmethod
    def test_substring() -> None:
        result = json.loads(search_settings('want_'))
        paths = [e['key_path'] for e in result]
        assert 'want_main' in paths

    @staticmethod
    def test_nested_match() -> None:
        result = json.loads(search_settings('line-length'))
        paths = [e['key_path'] for e in result]
        assert 'pyproject.tool.ruff.line-length' in paths

    @staticmethod
    def test_no_match() -> None:
        result = json.loads(search_settings('zzz_nonexistent_zzz'))
        assert result == []

    @staticmethod
    def test_match_dict_value() -> None:
        result = json.loads(search_settings('mastodon'))
        entries = {e['key_path']: e for e in result}
        assert 'social.mastodon' in entries
        assert entries['social.mastodon']['type'] == 'object'
        assert 'default_value' not in entries['social.mastodon']

    @staticmethod
    def test_match_list_value() -> None:
        result = json.loads(search_settings('keywords'))
        entries = {e['key_path']: e for e in result}
        assert 'keywords' in entries
        assert entries['keywords']['type'] == 'array'
        assert 'default_value' not in entries['keywords']


class TestNavigateNonDict:
    @staticmethod
    def test_navigate_through_non_dict() -> None:
        with pytest.raises(KeyError, match='child'):
            navigate({'parent': [1, 2]}, ['parent', 'child'])


class TestJsonValueToJsonnetExtended:
    @staticmethod
    def test_float() -> None:
        assert json_value_to_jsonnet(2.5) == '2.5'

    @staticmethod
    def test_nested_dict_with_hyphenated_key() -> None:
        result = json_value_to_jsonnet({'line-length': 100})
        assert "'line-length': 100" in result

    @staticmethod
    def test_unknown_type() -> None:
        result = json_value_to_jsonnet(object())
        assert 'object' in result

    @staticmethod
    def test_nested_list() -> None:
        result = json_value_to_jsonnet([1, 'a', True])
        assert '1' in result
        assert '"a"' in result
        assert 'true' in result


class TestTypeNameExtended:
    @staticmethod
    def test_float() -> None:
        assert type_name(2.5) == 'number'

    @staticmethod
    def test_unknown_type() -> None:
        assert type_name(object()) == 'object'


class TestGetDefaultsExtended:
    @staticmethod
    def test_key_path_to_list() -> None:
        result = json.loads(get_defaults('keywords'))
        assert result == ['python']


class TestLookupSettingExtended:
    @staticmethod
    def test_string_no_notes() -> None:
        result = json.loads(lookup_setting('project_name'))
        assert result['type'] == 'string'
        assert result['notes'] == []

    @staticmethod
    def test_boolean_no_notes() -> None:
        result = json.loads(lookup_setting('want_main'))
        assert result['type'] == 'boolean'
        assert result['notes'] == []


class TestGenerateOverrideSnippetExtended:
    @staticmethod
    def test_non_dict_intermediate() -> None:
        result = generate_override_snippet('keywords.item', 'val')
        assert 'keywords:' in result
        assert 'item:' in result
