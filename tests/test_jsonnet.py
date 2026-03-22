"""Tests for Jsonnet evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from wiswa.utils.jsonnet import (
    evaluate_jsonnet_file,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    resolve_defaults_only,
)
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_evaluate_jsonnet_file(mocker: MockerFixture) -> None:
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{"key": "value"}'
    result = evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    assert result == '{"key": "value"}'
    mock_jsonnet.evaluate_file.assert_called_once()


def test_evaluate_jsonnet_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                  mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'project.jsonnet').write_text('{}')
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file',
                 return_value='{"file.txt": "content"}')
    evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}')
    assert (tmp_path / 'file.txt').exists()


def test_evaluate_jsonnet_project_with_output_dir(tmp_path: Path, mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    output_dir = tmp_path / 'output'
    mocker.patch(
        'wiswa.utils.jsonnet.evaluate_jsonnet_file',
        return_value='{"sub/file.txt": "hello content"}',
    )
    evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}', output_dir=output_dir)
    assert output_dir.exists()
    assert (output_dir / 'sub/file.txt').exists()
    assert (output_dir / 'sub/file.txt').read_text().strip() == 'hello content'


def test_evaluate_jsonnet_project_with_custom_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    custom_file = tmp_path / 'custom.jsonnet'
    custom_file.write_text('{}')
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file', return_value='{"out.txt": "custom"}')
    evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}', file=custom_file)
    assert (tmp_path / 'out.txt').exists()


def test_evaluate_jsonnet_project_default_output_dir(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file',
                 return_value='{"generated.txt": "gen content"}')
    evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}')
    assert (tmp_path / 'generated.txt').exists()
    assert (tmp_path / 'generated.txt').read_text().strip() == 'gen content'


def test_evaluate_merged_settings(tmp_path: Path, mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libjsonnet').write_text('{ project_type: "python" }')
    mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                 return_value='{"project_type": "python"}')
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path',
                 return_value=tmp_path / 'config')
    result_str, result_dict = evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    assert result_str == '{"project_type": "python"}'
    assert result_dict['project_type'] == 'python'
    assert '_readme_existed' in result_dict


def test_evaluate_merged_settings_user_defaults(tmp_path: Path, mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libjsonnet').write_text('{ project_type: "python" }')
    config_path = tmp_path / 'config'
    config_path.mkdir()
    (config_path / 'defaults.jsonnet').write_text('{ extra: true }')
    mocker.patch(
        'wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
        return_value='{"project_type": "python", "extra": true}',
    )
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=config_path)
    _result_str, result_dict = evaluate_merged_settings([str(lib_path)],
                                                        lib_path,
                                                        '{}',
                                                        user_defaults=True)
    assert 'project_type' in result_dict


def test_evaluate_merged_settings_user_defaults_missing_raises(tmp_path: Path,
                                                               mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libjsonnet').write_text('{}')
    config_path = tmp_path / 'config'
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=config_path)
    with pytest.raises(FileNotFoundError, match='user_defaults=True'):
        evaluate_merged_settings([str(lib_path)], lib_path, '{}', user_defaults=True)


def test_resolve_defaults_only(tmp_path: Path, mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libjsonnet').write_text('{ project_type: "python" }')
    mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                 return_value='{"project_type": "python"}')
    result = resolve_defaults_only([str(lib_path)], lib_path)
    assert result == {'project_type': 'python'}


def test_resolve_defaults_only_passes_empty_overrides(tmp_path: Path,
                                                      mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libjsonnet').write_text('{ a: 1 }')
    mock_eval = mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                             return_value='{"a": 1}')
    resolve_defaults_only([str(lib_path)], lib_path)
    call_kwargs = mock_eval.call_args[1]
    assert call_kwargs['tla_codes']['settings'] == '{}'
    assert call_kwargs['tla_codes']['user_defaults'] == '{}'
