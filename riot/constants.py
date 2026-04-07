import os
import subprocess
import sys
import typing as t

DEFAULT_RIOT_PATH = ".riot"
DEFAULT_RIOT_ENV_PREFIX = "venv_py"

SHELL = os.getenv("SHELL", "/bin/bash")
ENCODING = sys.getdefaultencoding()
SHELL_RCFILE = r"""
source {venv_path}/bin/activate
echo -e "\e[31;1m"
echo "                 )  "
echo " (   (        ( /(  "
echo " )(  )\   (   )\()) "
echo "(()\((_)  )\ (_))/  "
echo " ((_)(_) ((_)| |_   "
echo "| '_|| |/ _ \|  _|  "
echo "|_|  |_|\___/ \__|  "
echo -e "\e[0m"
echo -e "\e[33;1mInteractive shell\e[0m"
echo ""
echo -e "* Venv name   : \e[1m{name}\e[0m"
echo -e "* Venv path   : \e[1m{venv_path}\e[0m"
echo -e "* Interpreter : \e[1m$( python -V )\e[0m"
"""

if t.TYPE_CHECKING or sys.version_info[:2] >= (3, 9):
    _T_CompletedProcess = subprocess.CompletedProcess[str]
else:
    _T_CompletedProcess = subprocess.CompletedProcess

_K = t.TypeVar("_K")
_V = t.TypeVar("_V")

_T_stdio = t.Union[None, int, t.IO[t.Any]]
