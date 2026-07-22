"""Tests for version utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
import math
import stat

from wiswa.tool.utils.versions import (
    clear_resolution_caches,
    download_yarn,
    download_yarn_plugins,
    get_github_release_latest_tag,
    get_latest_yarn_version,
    get_npm_latest_package_version,
    get_pypi_latest_package_version,
    resolve_npm_minimal_age_gate_minutes,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def clear_version_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_resolution_caches()
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'xdg-cache'))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / '.config'))
    monkeypatch.chdir(tmp_path)


def _make_response(text: str = '',
                   json_data: object = None,
                   ok: bool = True,
                   content: bytes = b'',
                   status_code: int | None = None) -> MagicMock:
    response = MagicMock()
    response.ok = ok
    if status_code is not None:
        response.status_code = status_code
    else:
        response.status_code = 200 if ok else 404
    response.text = text
    response.json = MagicMock(return_value=json_data)
    response.content = content
    response.raise_for_status = MagicMock(return_value=response)
    return response


async def test_download_yarn_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(text='  plugin content  '))
    await download_yarn_plugins(mock_session)
    plugin_file = tmp_path / '.yarn/plugins/plugin-prettier-after-all-installed.cjs'
    assert plugin_file.exists()
    assert plugin_file.read_text(encoding='utf-8') == 'plugin content\n'


async def test_download_yarn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(text='  yarn content  '))
    await download_yarn(mock_session, '4.0.0')
    target = tmp_path / '.yarn/releases/yarn-4.0.0.cjs'
    assert target.exists()
    assert target.read_text(encoding='utf-8') == 'yarn content\n'
    assert target.stat().st_mode & stat.S_IXUSR


async def test_download_yarn_removes_old_releases(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    releases_dir = tmp_path / '.yarn/releases'
    releases_dir.mkdir(parents=True)
    (releases_dir / 'yarn-3.0.0.cjs').write_text('old')
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(text='new yarn'))
    await download_yarn(mock_session, '4.0.0')
    assert not (releases_dir / 'yarn-3.0.0.cjs').exists()
    assert (releases_dir / 'yarn-4.0.0.cjs').exists()


async def test_get_latest_yarn_version_returns_stable() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={'latest': {
            'stable': '4.6.0'
        }}))
    result = await get_latest_yarn_version(mock_session)
    assert result == '4.6.0'
    mock_session.get.assert_called_once_with('https://repo.yarnpkg.com/tags', timeout=15)


async def test_get_latest_yarn_version_cache_hit() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={'latest': {
            'stable': '4.6.0'
        }}))
    result1 = await get_latest_yarn_version(mock_session)
    result2 = await get_latest_yarn_version(mock_session)
    assert result1 == result2 == '4.6.0'
    assert mock_session.get.call_count == 1


async def test_get_github_release_latest_tag_maps_yapf_to_require_v_prefix(
        mocker: MockerFixture) -> None:
    delegate = mocker.patch('wiswa.tool.utils.versions.latest_release_tag',
                            new_callable=AsyncMock,
                            return_value='v0.40.2')
    session = MagicMock()
    result = await get_github_release_latest_tag(session, 'google', 'yapf')
    assert result == 'v0.40.2'
    delegate.assert_awaited_once_with(session,
                                      'google',
                                      'yapf',
                                      skip_releases=False,
                                      allow_suffixes=True,
                                      require_v_prefix=True,
                                      min_release_age_minutes=None)


async def test_get_github_release_latest_tag_resolves_npm_age_when_minutes_omitted(
        mocker: MockerFixture) -> None:
    mocker.patch('wiswa.tool.utils.versions.resolve_npm_minimal_age_gate_minutes',
                 return_value=4321)
    delegate = mocker.patch('wiswa.tool.utils.versions.latest_release_tag',
                            new_callable=AsyncMock,
                            return_value='v1.0.0')
    session = MagicMock()
    await get_github_release_latest_tag(session, 'owner', 'repo', apply_npm_min_release_age=True)
    assert delegate.call_args.kwargs['min_release_age_minutes'] == 4321
    assert delegate.call_args.kwargs['require_v_prefix'] is False


async def test_get_pypi_latest_package_version_uv_toml_global_parses_timestamp(
        tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2025-01-15T12:00:00Z"\n', encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-06-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'toml-parse-pkg')
    assert result == '1.0.0'


@pytest.mark.parametrize(('toml_value', 'pkg', 'use_bare_int'), [('PT4H', 'dur-pt4h', False),
                                                                 ('P10D', 'dur-p10d', False),
                                                                 ('P2W', 'dur-p2w', False),
                                                                 ('P1DT2H', 'dur-p1dt2h', False),
                                                                 ('9 hours', 'dur-9h', False),
                                                                 ('8 days', 'dur-8d', False),
                                                                 ('2 weeks', 'dur-2w', False),
                                                                 ('30', 'dur-intdays', True)])
async def test_get_pypi_exclude_newer_duration_forms(
        tmp_path: Path,
        mocker: MockerFixture,
        toml_value: str,
        pkg: str,
        use_bare_int: bool  # ruff:ignore[boolean-type-hint-positional-argument]
) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    line = (f'exclude-newer = {toml_value}\n'
            if use_bare_int else f'exclude-newer = "{toml_value}"\n')
    (uv_dir / 'uv.toml').write_text(line, encoding='utf-8')
    fixed_now = datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    mocker.patch('wiswa.tool.utils.versions.datetime', wraps=datetime)
    mocker.patch('wiswa.tool.utils.versions.datetime.now', return_value=fixed_now)
    data = _make_pypi_json([('2.0.0', '2025-08-01T10:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, pkg)
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_uv_toml_duration_exclude_newer(
        tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "P7D"\n', encoding='utf-8')
    fixed_now = datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    mocker.patch('wiswa.tool.utils.versions.datetime', wraps=datetime)
    mocker.patch('wiswa.tool.utils.versions.datetime.now', return_value=fixed_now)
    data = _make_pypi_json([('1.0.0', '2025-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'duration-cutoff-pkg')
    assert result == '1.0.0'


async def test_get_pypi_per_package_uv_toml_skips_invalid_timestamp(tmp_path: Path,
                                                                    mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text(
        '[exclude-newer-package]\nkeep = "2025-02-01T00:00:00Z"\ndrop = "not-a-timestamp"\n',
        encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-03-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'keep')
    assert result == '1.0.0'


async def test_get_pypi_per_package_uv_toml_date_only_string(tmp_path: Path,
                                                             mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('[exclude-newer-package]\ndate-only-pkg = "2025-03-01"\n',
                                    encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-04-01T00:00:00Z'), ('1.0.0', '2025-01-15T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'date-only-pkg')
    assert result == '1.0.0'


async def test_get_pypi_uv_toml_empty_behaves_like_no_config(tmp_path: Path,
                                                             mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('', encoding='utf-8')
    data = _make_pypi_json([('1.0.0', '2025-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'empty-uv-pkg')
    assert result == '1.0.0'


async def test_get_pypi_uv_toml_read_os_error_falls_back_to_no_cutoff(
        tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('valid = true', encoding='utf-8')
    mocker.patch('pathlib.Path.read_text', side_effect=OSError('Permission denied'))
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'read-error-pkg')
    assert result == '2.0.0'


async def test_get_pypi_project_pyproject_overrides_user_uv_toml(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[tool.uv]\nexclude-newer = "2030-01-01T00:00:00Z"\n',
                                             encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'project-override-pkg')
    assert result == '2.0.0'


async def test_get_pypi_project_pyproject_per_package_false_bypasses_global(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[tool.uv.exclude-newer-package]\nfree-pass = false\n',
                                             encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'free-pass')
    assert result == '2.0.0'


async def test_get_pypi_per_package_true_is_ignored(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text(
        'exclude-newer = "2024-06-01T00:00:00Z"\n'
        '[exclude-newer-package]\nlocked = true\n',
        encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'locked')
    assert result == '1.0.0'


async def test_get_pypi_global_exclude_newer_invalid_string_ignored(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "not-a-timestamp"\n', encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'invalid-cutoff-pkg')
    assert result == '2.0.0'


async def test_get_pypi_project_pyproject_no_tool_uv_section(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "x"\n', encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'no-tool-uv-pkg')
    assert result == '1.0.0'


def test_resolve_npm_minimal_age_gate_minutes_prefers_merged_settings() -> None:
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': {
        'npmMinimalAgeGate': 42
    }}) == 42


def test_resolve_npm_minimal_age_gate_minutes_settings_over_snippet() -> None:
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': {
        'npmMinimalAgeGate': 55
    }},
                                                project_snippet='npmMinimalAgeGate: 99\n') == 55


def test_resolve_npm_minimal_age_gate_minutes_snippet_over_yarnrc_files(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 100\n', encoding='utf-8')
    snippet = 'npmMinimalAgeGate: 200\n'
    assert resolve_npm_minimal_age_gate_minutes(settings=None, project_snippet=snippet) == 200


def test_resolve_npm_minimal_age_gate_minutes_project_yarnrc_before_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 11\n', encoding='utf-8')
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 22\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 22


def test_resolve_npm_minimal_age_gate_minutes_npmrc_when_no_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('min-release-age=2\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 2 * 24 * 60


def test_resolve_npm_minimal_age_gate_minutes_default_when_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    assert resolve_npm_minimal_age_gate_minutes() == 10080


def test_resolve_npm_minimal_age_gate_minutes_settings_yarnrc_list_type(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 88\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': []}) == 88


def test_resolve_npm_minimal_age_gate_minutes_settings_gate_string() -> None:
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': {
        'npmMinimalAgeGate': '321'
    }}) == 321


def test_resolve_npm_minimal_age_gate_minutes_settings_non_numeric_skips_to_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 15\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': {
        'npmMinimalAgeGate': math.pi
    }}) == 15


def test_resolve_npm_minimal_age_gate_minutes_snippet_without_key_reads_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 77\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes(project_snippet='foo: 1\n') == 77


def test_resolve_npm_minimal_age_gate_minutes_project_yarnrc_missing_gate_then_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('# no gate\nplugins: []\n', encoding='utf-8')
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 9\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 9


def test_resolve_npm_minimal_age_gate_minutes_malformed_cwd_yarnrc_then_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: notint\n', encoding='utf-8')
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 33\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 33


def test_resolve_npm_minimal_age_gate_minutes_cwd_yarnrc_oserror_then_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    cwd_rc = tmp_path / '.yarnrc.yml'
    cwd_rc.write_text('npmMinimalAgeGate: 1\n', encoding='utf-8')
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 44\n', encoding='utf-8')
    real_read = Path.read_text

    def patched(self: Path, *a: Any, **kw: Any) -> str:
        if self.resolve() == cwd_rc.resolve():
            msg = 'simulated read failure'
            raise OSError(msg)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, 'read_text', patched)
    assert resolve_npm_minimal_age_gate_minutes() == 44


def test_resolve_npm_minimal_age_gate_minutes_npmrc_min_release_age_snake_key(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('# c\nmin_release_age=4\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 4 * 24 * 60


def test_resolve_npm_minimal_age_gate_minutes_npmrc_skips_line_without_equals(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('foo\nmin-release-age=2\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 2 * 24 * 60


def test_resolve_npm_minimal_age_gate_minutes_npmrc_invalid_days_then_default(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('min-release-age=notint\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 10080


def test_resolve_npm_minimal_age_gate_minutes_npmrc_oserror_then_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    npmrc = fake_home / '.npmrc'
    npmrc.write_text('min-release-age=1\n', encoding='utf-8')
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 12\n', encoding='utf-8')
    real_read = Path.read_text

    def patched(self: Path, *a: Any, **kw: Any) -> str:
        if self.resolve() == npmrc.resolve():
            msg = 'npmrc read failure'
            raise OSError(msg)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, 'read_text', patched)
    assert resolve_npm_minimal_age_gate_minutes() == 12


def test_resolve_npm_minimal_age_gate_minutes_npmrc_without_min_release_reads_default(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('registry=https://registry.npmjs.org/\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 10080


def test_resolve_npm_minimal_age_gate_minutes_npmrc_read_oserror_only(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    npmrc = fake_home / '.npmrc'
    npmrc.write_text('min-release-age=1\n', encoding='utf-8')
    real_read = Path.read_text

    def patched(self: Path, *a: Any, **kw: Any) -> str:
        if self.resolve() == npmrc.resolve():
            msg = 'npmrc read failure'
            raise OSError(msg)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, 'read_text', patched)
    assert resolve_npm_minimal_age_gate_minutes() == 10080


# get_npm_latest_package_version tests


async def test_get_npm_latest_package_version_picks_oldest_stable() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    new_date = (datetime.now(tz=timezone.utc) - timedelta(minutes=5)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0': {}
            },
            'time': {
                'created': '2020-01-01T00:00:00Z',
                'modified': '2025-01-01T00:00:00Z',
                '1.0.0': old_date,
                '2.0.0': new_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'test-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_all_too_new_falls_back_to_latest() -> None:
    new_date = (datetime.now(tz=timezone.utc) - timedelta(minutes=5)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '3.0.0'
            },
            'versions': {
                '3.0.0': {}
            },
            'time': {
                '3.0.0': new_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'new-only-pkg')
    assert result == '3.0.0'


async def test_get_npm_latest_package_version_skips_prerelease() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0-beta.1'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0-beta.1': {}
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0-beta.1': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'pre-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_skips_invalid_versions() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '1.0.0'
            },
            'versions': {
                'not-a-version': {},
                '1.0.0': {}
            },
            'time': {
                'not-a-version': old_date,
                '1.0.0': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'invalid-ver-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_skips_invalid_dates() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0': {}
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0': 'not-a-date'
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'bad-date-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_cache_hit() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '1.0.0'
            },
            'versions': {
                '1.0.0': {}
            },
            'time': {
                '1.0.0': old_date
            }
        }))
    result1 = await get_npm_latest_package_version(mock_session, 'cached-npm')
    result2 = await get_npm_latest_package_version(mock_session, 'cached-npm')
    assert result1 == result2 == '1.0.0'
    assert mock_session.get.call_count == 1


async def test_get_npm_latest_package_version_picks_highest_version() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '3.0.0'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0': {},
                '3.0.0': {}
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0': old_date,
                '3.0.0': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'multi-ver-pkg')
    assert result == '3.0.0'


async def test_get_npm_latest_package_version_skips_unpublished_versions() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0'
            },
            'versions': {
                '1.0.0': {}
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'unpublished-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_all_unpublished_falls_back_to_latest() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '3.0.0'
            },
            'versions': {},
            'time': {
                '1.0.0': old_date,
                '2.0.0': old_date,
                '3.0.0': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'all-unpublished-pkg')
    assert result == '3.0.0'


async def test_get_npm_latest_package_version_no_versions_key_falls_back_to_latest() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data={
        'dist-tags': {
            'latest': '1.0.0'
        },
        'time': {
            '1.0.0': old_date
        }
    }))
    result = await get_npm_latest_package_version(mock_session, 'no-versions-key-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_mixed_published_unpublished() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '4.0.0'
            },
            'versions': {
                '1.0.0': {},
                '3.0.0': {}
            },
            'time': {
                'created': '2020-01-01T00:00:00Z',
                'modified': '2025-01-01T00:00:00Z',
                '1.0.0': old_date,
                '2.0.0': old_date,
                '3.0.0': old_date,
                '4.0.0': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session, 'mixed-pub-pkg')
    assert result == '3.0.0'


async def test_get_npm_latest_package_version_respects_node_engine() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '10.0.0'
            },
            'versions': {
                '9.5.0': {
                    'engines': {
                        'node': '>=18'
                    }
                },
                '10.0.0': {
                    'engines': {
                        'node': '>=22'
                    }
                },
                '11.0.0': {
                    'engines': {}
                }
            },
            'time': {
                'created': '2025-01-01T00:00:00Z',
                'modified': '2025-01-01T00:00:00Z',
                '9.5.0': old_date,
                '10.0.0': old_date,
                '11.0.0': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session,
                                                  'engines-pkg',
                                                  node_constraint='>=20.0')
    assert result == '11.0.0'


async def test_get_npm_latest_package_version_node_engine_invalid_constraint() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0'
            },
            'versions': {
                '1.0.0': {
                    'engines': {
                        'node': '^nonsense'
                    }
                },
                '2.0.0': {
                    'engines': {
                        'node': ''
                    }
                }
            },
            'time': {
                'created': '2025-01-01T00:00:00Z',
                'modified': '2025-01-01T00:00:00Z',
                '1.0.0': old_date,
                '2.0.0': old_date
            }
        }))
    result = await get_npm_latest_package_version(mock_session,
                                                  'invalid-engines-pkg',
                                                  node_constraint='>=20')
    assert result == '2.0.0'


# get_pypi_latest_package_version tests


def _make_pypi_json(versions: list[tuple[str, str]]) -> dict[str, Any]:
    releases: dict[str, list[dict[str, str]]] = {}
    for ver, upload_time in versions:
        releases[ver] = [{'upload_time_iso_8601': upload_time}]
    return {'info': {'version': versions[0][0] if versions else ''}, 'releases': releases}


async def test_get_pypi_latest_package_version_no_cutoff() -> None:
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'no-cutoff-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_default_cutoff_without_config() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    new_date = (datetime.now(tz=timezone.utc) - timedelta(minutes=1)).isoformat()
    data = _make_pypi_json([('2.0.0', new_date), ('1.0.0', old_date)])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'default-cutoff-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_global_cutoff(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'global-cutoff-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_per_package_cutoff(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text(
        'exclude-newer = "2020-01-01T00:00:00Z"\n\n'
        '[exclude-newer-package]\nmy-pkg = "2024-06-01T00:00:00Z"\n',
        encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'my-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_all_filtered_fallback(tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2020-01-01T00:00:00Z"\n', encoding='utf-8')
    data = _make_pypi_json([('2.0.0', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'all-filtered-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_no_releases_raises() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data={
        'info': {},
        'releases': {}
    }))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'empty-pkg')


async def test_get_pypi_latest_package_version_skips_prerelease() -> None:
    data = _make_pypi_json([('2.0.0a1', '2025-01-01T00:00:00Z'), ('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'prerelease-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_skips_yanked() -> None:
    data = _make_pypi_json([('8.3.0', '2025-01-01T00:00:00Z'), ('8.2.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'sphinx')
    assert result == '8.2.0'


async def test_get_pypi_latest_package_version_cache_hit() -> None:
    data = _make_pypi_json([('1.0.0', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result1 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    result2 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    assert result1 == result2 == '1.0.0'
    assert mock_session.get.call_count == 1


async def test_get_pypi_latest_package_version_only_prerelease_raises() -> None:
    data = _make_pypi_json([('2.0.0a1', '2025-01-01T00:00:00Z'),
                            ('1.0.0rc1', '2024-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'only-pre-pkg')


async def test_get_pypi_latest_package_version_custom_host() -> None:
    data = _make_pypi_json([('3.0.0', '2025-01-01T00:00:00Z')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session,
                                                   'internal-pkg',
                                                   host='pypi.internal.example.com')
    assert result == '3.0.0'
    mock_session.get.assert_called_once_with(
        'https://pypi.internal.example.com/pypi/internal-pkg/json', timeout=15)


async def test_get_pypi_latest_package_version_filters_by_python() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '2.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z',
                'requires_python': '>=3.9'
            }],
            '2.0.0': [{
                'upload_time_iso_8601': '2025-01-01T00:00:00Z',
                'requires_python': '>=3.13'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'py-filter-pkg', python='3.10')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_python_empty_skips_filter() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '2.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z',
                'requires_python': '>=3.9'
            }],
            '2.0.0': [{
                'upload_time_iso_8601': '2025-01-01T00:00:00Z',
                'requires_python': '>=3.13'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'py-filter-off-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_python_no_compatible_raises() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z',
                'requires_python': '>=3.13'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'no-compat-pkg', python='3.10')


async def test_get_pypi_latest_package_version_python_missing_requires_passes() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'no-req-py-pkg', python='3.10')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_python_upper_bound() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '2.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z',
                'requires_python': '>=3.9,<3.11'
            }],
            '2.0.0': [{
                'upload_time_iso_8601': '2025-01-01T00:00:00Z',
                'requires_python': '<4.0,>=3.10'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'upper-bound-pkg', python='3.12')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_python_invalid_specifier_passes() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z',
                'requires_python': '>>>broken<<<'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'bad-spec-pkg', python='3.10')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_python_empty_requires_passes() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z',
                'requires_python': ''
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'empty-req-pkg', python='3.10')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_python_non_string_requires_passes() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z',
                'requires_python': None
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'none-req-pkg', python='3.10')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_empty_files_with_python_passes() -> None:
    data: dict[str, Any] = {'info': {'version': '1.0.0'}, 'releases': {'1.0.0': []}}
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'empty-files-pkg', python='3.10')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_skips_invalid_version_key() -> None:
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            'not!!a!!version': [{
                'upload_time_iso_8601': '2025-01-01T00:00:00Z'
            }],
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'invalid-ver-pypi-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_earliest_upload_multiple_files(
        tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z'
            }, {
                'upload_time_iso_8601': '2024-03-01T00:00:00Z'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'multi-file-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_upload_time_non_string_skipped(
        tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': 12345
            }],
            '2.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'non-str-time-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_upload_time_invalid_date_skipped(
        tmp_path: Path) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    data: dict[str, Any] = {
        'info': {
            'version': '1.0.0'
        },
        'releases': {
            '1.0.0': [{
                'upload_time_iso_8601': 'not-a-date'
            }],
            '2.0.0': [{
                'upload_time_iso_8601': '2024-01-01T00:00:00Z'
            }]
        }
    }
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data=data))
    result = await get_pypi_latest_package_version(mock_session, 'bad-time-pkg')
    assert result == '2.0.0'
