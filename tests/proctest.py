import dataclasses
import os
import subprocess
import sys
import tempfile
import typing as t


if t.TYPE_CHECKING or sys.version_info[:2] >= (3, 9):
    _T_CompletedProcess = subprocess.CompletedProcess[str]
else:
    _T_CompletedProcess = subprocess.CompletedProcess

_T_Path = t.Union[str, "os.PathLike[t.Any]"]


@dataclasses.dataclass(frozen=True)
class ProcResult:
    proc: _T_CompletedProcess = dataclasses.field(repr=False)

    @property
    def stdout(self) -> str:
        return self.proc.stdout

    @property
    def stderr(self) -> str:
        return self.proc.stderr

    @property
    def returncode(self) -> int:
        return self.proc.returncode


class TestDir:
    def __init__(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.cwd = self._tmpdir.name

    def __fspath__(self):
        """Implement Pathlike interface."""
        return self.cwd

    def cd(self, path: _T_Path) -> None:
        res_path = path if os.path.isabs(path) else os.path.join(self.cwd, path)
        self.cwd = res_path

    def mkdir(self, path: _T_Path) -> None:
        res_path = path if os.path.isabs(path) else os.path.join(self.cwd, path)
        os.mkdir(res_path)

    def mkfile(self, path: _T_Path, contents: str) -> None:
        res_path = path if os.path.isabs(path) else os.path.join(self.cwd, path)
        with open(res_path, "w") as f:
            f.write(contents)

    def run(
        self,
        args: t.Union[str, t.Sequence[str]],
        env: t.Optional[t.Dict[str, str]] = None,
        cwd: t.Optional[_T_Path] = None,
    ) -> ProcResult:
        if isinstance(args, str):
            args = args.split(" ")

        p = subprocess.run(
            args,
            env=env,
            encoding=sys.getdefaultencoding(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
        )
        return ProcResult(p)
