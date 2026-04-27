"""Tests for Wiswa run metadata writer."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
import importlib.metadata
import json
import re

from wiswa.utils.run_metadata import get_wiswa_version_or_sha, write_wiswa_run_metadata
import wiswa

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    import pytest


def _make_async_proc(*, returncode: int = 0, stdout: bytes = b'') -> AsyncMock:
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, b''))
    proc.returncode = returncode
    return proc


def _mock_async_subprocess(mocker: MockerFixture,
                           *,
                           returncode: int = 0,
                           stdout: bytes = b'') -> AsyncMock:
    patched = mocker.patch('asyncio.create_subprocess_exec',
                           return_value=_make_async_proc(returncode=returncode, stdout=stdout))
    return cast('AsyncMock', patched)


def _setup_fake_wiswa_checkout(tmp_path: Path,
                               monkeypatch: pytest.MonkeyPatch,
                               mocker: MockerFixture,
                               *,
                               head: str | None,
                               name: str = 'wiswa',
                               dirty_stdout: bytes = b'',
                               git_returncode: int = 0,
                               git_raises: type[BaseException] | None = None) -> AsyncMock:
    tmp_path.mkdir(parents=True, exist_ok=True)
    pkg_dir = tmp_path / 'wiswa'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text(f'name = "{name}"\n', encoding='utf-8')
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    if head is not None:
        (git_dir / 'HEAD').write_text(f'{head}\n', encoding='utf-8')
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    if git_raises is not None:
        return cast('AsyncMock',
                    mocker.patch('asyncio.create_subprocess_exec', side_effect=git_raises))
    return _mock_async_subprocess(mocker, returncode=git_returncode, stdout=dirty_stdout)


async def test_get_wiswa_version_or_sha_uses_short_sha_from_source_checkout(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    full_sha = 'abcdef1234567890abcdef1234567890abcdef12'
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head=full_sha)
    assert await get_wiswa_version_or_sha() == full_sha[:7]


async def test_get_wiswa_version_or_sha_resolves_symbolic_ref(tmp_path: Path,
                                                              monkeypatch: pytest.MonkeyPatch,
                                                              mocker: MockerFixture) -> None:
    sha = 'fedcba9876543210fedcba9876543210fedcba98'
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head='ref: refs/heads/master')
    refs_dir = tmp_path / '.git' / 'refs' / 'heads'
    refs_dir.mkdir(parents=True)
    (refs_dir / 'master').write_text(f'{sha}\n', encoding='utf-8')
    assert await get_wiswa_version_or_sha() == sha[:7]


async def test_get_wiswa_version_or_sha_resolves_packed_ref(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            mocker: MockerFixture) -> None:
    sha = '1111111111111111111111111111111111111111'
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head='ref: refs/heads/master')
    (tmp_path / '.git' / 'packed-refs').write_text(f'{sha} refs/heads/master\n', encoding='utf-8')
    assert await get_wiswa_version_or_sha() == sha[:7]


async def test_get_wiswa_version_or_sha_handles_gitdir_pointer(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               mocker: MockerFixture) -> None:
    sha = '2222222222222222222222222222222222222222'
    pkg_dir = tmp_path / 'wiswa'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('name = "wiswa"\n', encoding='utf-8')
    actual_git = tmp_path / 'real-git'
    actual_git.mkdir()
    (actual_git / 'HEAD').write_text(f'{sha}\n', encoding='utf-8')
    (tmp_path / '.git').write_text(f'gitdir: {actual_git}\n', encoding='utf-8')
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    _mock_async_subprocess(mocker)
    assert await get_wiswa_version_or_sha() == sha[:7]


async def test_get_wiswa_version_or_sha_falls_back_when_repo_is_other_project(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    _setup_fake_wiswa_checkout(tmp_path,
                               monkeypatch,
                               mocker,
                               head='abcdef1234567890abcdef1234567890abcdef12',
                               name='other')
    mocker.patch.object(importlib.metadata, 'version', return_value='9.9.9')
    assert await get_wiswa_version_or_sha() == '9.9.9'


async def test_get_wiswa_version_or_sha_falls_back_when_no_git(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               mocker: MockerFixture) -> None:
    pkg_dir = tmp_path / 'wiswa'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    mocker.patch.object(importlib.metadata, 'version', return_value='1.2.3')
    assert await get_wiswa_version_or_sha() == '1.2.3'


async def test_get_wiswa_version_or_sha_falls_back_when_head_unreadable(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head=None)
    mocker.patch.object(importlib.metadata, 'version', return_value='5.5.5')
    assert await get_wiswa_version_or_sha() == '5.5.5'


async def test_get_wiswa_version_or_sha_falls_back_when_repo_missing_pyproject(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    pkg_dir = tmp_path / 'wiswa'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    (tmp_path / '.git').mkdir()
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    mocker.patch.object(importlib.metadata, 'version', return_value='4.4.4')
    assert await get_wiswa_version_or_sha() == '4.4.4'


async def test_get_wiswa_version_or_sha_falls_back_when_gitdir_pointer_invalid(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    pkg_dir = tmp_path / 'wiswa'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    (tmp_path / '.git').write_text('not a gitdir line\n', encoding='utf-8')
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    mocker.patch.object(importlib.metadata, 'version', return_value='3.3.3')
    assert await get_wiswa_version_or_sha() == '3.3.3'


async def test_get_wiswa_version_or_sha_falls_back_when_gitdir_target_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    pkg_dir = tmp_path / 'wiswa'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    (tmp_path / '.git').write_text('gitdir: nonexistent-target\n', encoding='utf-8')
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    mocker.patch.object(importlib.metadata, 'version', return_value='2.2.2')
    assert await get_wiswa_version_or_sha() == '2.2.2'


async def test_get_wiswa_version_or_sha_returns_none_for_empty_ref_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head='ref: refs/heads/master')
    refs_dir = tmp_path / '.git' / 'refs' / 'heads'
    refs_dir.mkdir(parents=True)
    (refs_dir / 'master').write_text('\n', encoding='utf-8')
    mocker.patch.object(importlib.metadata, 'version', return_value='8.8.8')
    assert await get_wiswa_version_or_sha() == '8.8.8'


async def test_get_wiswa_version_or_sha_falls_back_when_packed_refs_no_match(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head='ref: refs/heads/master')
    sha = '3333333333333333333333333333333333333333'
    (tmp_path / '.git' / 'packed-refs').write_text(f'{sha} refs/heads/other\n', encoding='utf-8')
    mocker.patch.object(importlib.metadata, 'version', return_value='6.6.6')
    assert await get_wiswa_version_or_sha() == '6.6.6'


async def test_get_wiswa_version_or_sha_falls_back_when_ref_missing_no_packed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head='ref: refs/heads/master')
    mocker.patch.object(importlib.metadata, 'version', return_value='7.7.7')
    assert await get_wiswa_version_or_sha() == '7.7.7'


async def test_get_wiswa_version_or_sha_appends_dirty_when_repo_dirty(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    full_sha = 'abcdef1234567890abcdef1234567890abcdef12'
    _setup_fake_wiswa_checkout(tmp_path,
                               monkeypatch,
                               mocker,
                               head=full_sha,
                               dirty_stdout=b' M file.py\n')
    assert await get_wiswa_version_or_sha() == f'{full_sha[:7]}-dirty'


async def test_get_wiswa_version_or_sha_no_dirty_when_repo_clean(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch,
                                                                 mocker: MockerFixture) -> None:
    full_sha = 'abcdef1234567890abcdef1234567890abcdef12'
    _setup_fake_wiswa_checkout(tmp_path, monkeypatch, mocker, head=full_sha)
    assert await get_wiswa_version_or_sha() == full_sha[:7]


async def test_get_wiswa_version_or_sha_no_dirty_when_status_fails(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch,
                                                                   mocker: MockerFixture) -> None:
    full_sha = 'abcdef1234567890abcdef1234567890abcdef12'
    _setup_fake_wiswa_checkout(tmp_path,
                               monkeypatch,
                               mocker,
                               head=full_sha,
                               git_returncode=128,
                               dirty_stdout=b'')
    assert await get_wiswa_version_or_sha() == full_sha[:7]


async def test_get_wiswa_version_or_sha_no_dirty_when_git_not_installed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    full_sha = 'abcdef1234567890abcdef1234567890abcdef12'
    _setup_fake_wiswa_checkout(tmp_path,
                               monkeypatch,
                               mocker,
                               head=full_sha,
                               git_raises=FileNotFoundError)
    assert await get_wiswa_version_or_sha() == full_sha[:7]


async def test_get_wiswa_version_or_sha_falls_back_to_module_version(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    pkg_dir = tmp_path / 'wiswa'
    pkg_dir.mkdir()
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    mocker.patch.object(importlib.metadata,
                        'version',
                        side_effect=importlib.metadata.PackageNotFoundError)
    assert await get_wiswa_version_or_sha() == wiswa.__version__


async def test_write_wiswa_run_metadata_appends_keys(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text(json.dumps({
        'name': 'demo',
        'scripts': {
            'build': 'echo'
        }
    }),
                                           encoding='utf-8')
    full_sha = 'abcdef1234567890abcdef1234567890abcdef12'
    _setup_fake_wiswa_checkout(tmp_path / 'src', monkeypatch, mocker, head=full_sha)
    monkeypatch.setattr('sys.argv', ['/usr/local/bin/wiswa', '--quiet'])
    await write_wiswa_run_metadata()
    text = (tmp_path / 'package.json').read_text(encoding='utf-8')
    data = json.loads(text)
    assert data['_wiswa']['version'] == full_sha[:7]
    assert data['_wiswa']['commandLine'] == 'wiswa --quiet'
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', data['_wiswa']['lastRun'])
    assert list(data.keys())[-1] == '_wiswa'
    assert list(data['_wiswa'].keys()) == ['commandLine', 'lastRun', 'version']
    assert text.rfind('"_wiswa"') > text.rfind('"name"')


async def test_write_wiswa_run_metadata_replaces_existing(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch,
                                                          mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text(json.dumps({
        '_wiswa': {
            'commandLine': 'old',
            'lastRun': '2000-01-01T00:00:00Z',
            'version': 'old',
        },
        'name': 'demo'
    }),
                                           encoding='utf-8')
    new_sha = '7777777777777777777777777777777777777777'
    _setup_fake_wiswa_checkout(tmp_path / 'src', monkeypatch, mocker, head=new_sha)
    monkeypatch.setattr('sys.argv', ['wiswa'])
    await write_wiswa_run_metadata()
    data = json.loads((tmp_path / 'package.json').read_text(encoding='utf-8'))
    assert data['_wiswa']['version'] == new_sha[:7]
    assert list(data.keys())[-1] == '_wiswa'


async def test_write_wiswa_run_metadata_invokes_prettier(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch,
                                                         mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{"name": "demo"}', encoding='utf-8')
    create = _setup_fake_wiswa_checkout(tmp_path / 'src',
                                        monkeypatch,
                                        mocker,
                                        head='1234567abcdef1234567abcdef1234567abcdef1')
    monkeypatch.setattr('sys.argv', ['wiswa'])
    on_command_calls: list[str] = []
    await write_wiswa_run_metadata(on_command=on_command_calls.append)
    invocations = [tuple(call.args) for call in create.call_args_list]
    assert any(args[:1] == ('yarn',) and 'prettier' in args and 'package.json' in args
               for args in invocations)
    assert any('prettier' in c and 'package.json' in c for c in on_command_calls)


async def test_write_wiswa_run_metadata_missing_package_json(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    create = mocker.patch('asyncio.create_subprocess_exec')
    await write_wiswa_run_metadata()
    create.assert_not_called()


async def test_write_wiswa_run_metadata_non_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('[]', encoding='utf-8')
    create = mocker.patch('asyncio.create_subprocess_exec')
    await write_wiswa_run_metadata()
    create.assert_not_called()


async def test_write_wiswa_run_metadata_quotes_command_line_with_spaces(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{"name": "demo"}', encoding='utf-8')
    _setup_fake_wiswa_checkout(tmp_path / 'src',
                               monkeypatch,
                               mocker,
                               head='1234567abcdef1234567abcdef1234567abcdef1')
    monkeypatch.setattr('sys.argv', ['/opt/wiswa', '--output-dir', 'my dir/with space'])
    await write_wiswa_run_metadata()
    data = json.loads((tmp_path / 'package.json').read_text(encoding='utf-8'))
    assert data['_wiswa']['commandLine'] == "wiswa --output-dir 'my dir/with space'"


async def test_write_wiswa_run_metadata_empty_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{"name": "demo"}', encoding='utf-8')
    _setup_fake_wiswa_checkout(tmp_path / 'src',
                               monkeypatch,
                               mocker,
                               head='1234567abcdef1234567abcdef1234567abcdef1')
    monkeypatch.setattr('sys.argv', [])
    await write_wiswa_run_metadata()
    data = json.loads((tmp_path / 'package.json').read_text(encoding='utf-8'))
    assert data['_wiswa']['commandLine'] == ''  # noqa: PLC1901


async def test_write_wiswa_run_metadata_logs_when_prettier_fails(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch,
                                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{"name": "demo"}', encoding='utf-8')
    pkg_dir = tmp_path / 'src' / 'wiswa'
    pkg_dir.mkdir(parents=True)
    (pkg_dir / '__init__.py').write_text('', encoding='utf-8')
    (tmp_path / 'src' / 'pyproject.toml').write_text('name = "wiswa"\n', encoding='utf-8')
    (tmp_path / 'src' / '.git').mkdir()
    (tmp_path / 'src' / '.git' / 'HEAD').write_text('1234567abcdef1234567abcdef1234567abcdef1\n',
                                                    encoding='utf-8')
    monkeypatch.setattr(wiswa, '__file__', str(pkg_dir / '__init__.py'))
    monkeypatch.setattr('sys.argv', ['wiswa'])
    mocker.patch('asyncio.create_subprocess_exec',
                 side_effect=[
                     _make_async_proc(returncode=0, stdout=b''),
                     _make_async_proc(returncode=2, stdout=b''),
                 ])
    await write_wiswa_run_metadata()
    data = json.loads((tmp_path / 'package.json').read_text(encoding='utf-8'))
    assert data['_wiswa']['version'] == '1234567'


async def test_write_wiswa_run_metadata_disabled_removes_existing_block(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text(json.dumps({
        '_wiswa': {
            'commandLine': 'wiswa',
            'lastRun': '2026-04-27T08:27:53Z',
            'version': '1234567',
        },
        'name': 'demo',
    }),
                                           encoding='utf-8')
    create = _mock_async_subprocess(mocker)
    await write_wiswa_run_metadata(enabled=False)
    data = json.loads((tmp_path / 'package.json').read_text(encoding='utf-8'))
    assert '_wiswa' not in data
    assert data['name'] == 'demo'
    invocations = [tuple(call.args) for call in create.call_args_list]
    assert any(args[:1] == ('yarn',) and 'prettier' in args for args in invocations)


async def test_write_wiswa_run_metadata_disabled_no_existing_block_skips(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text(json.dumps({'name': 'demo'}), encoding='utf-8')
    create = mocker.patch('asyncio.create_subprocess_exec')
    await write_wiswa_run_metadata(enabled=False)
    create.assert_not_called()


async def test_write_wiswa_run_metadata_records_short_sha(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch,
                                                          mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{"name": "demo"}', encoding='utf-8')
    _setup_fake_wiswa_checkout(tmp_path / 'src',
                               monkeypatch,
                               mocker,
                               head='0badbee0987654321ffedcba9876543210fedbeef')
    monkeypatch.setattr('sys.argv', ['wiswa'])
    await write_wiswa_run_metadata()
    data = json.loads((tmp_path / 'package.json').read_text(encoding='utf-8'))
    assert data['_wiswa']['version'] == '0badbee'
    assert len(data['_wiswa']['version']) == 7
