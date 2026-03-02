from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CmdResult:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined(self) -> str:
        if self.stdout and self.stderr:
            return self.stdout.rstrip() + "\n" + self.stderr.rstrip()
        return self.stdout or self.stderr


def has_cmd(binary: str) -> bool:
    return shutil.which(binary) is not None


def run_cmd(command: str, timeout: int = 30) -> CmdResult:
    proc = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return CmdResult(
        command=command,
        returncode=proc.returncode,
        stdout=proc.stdout.strip(),
        stderr=proc.stderr.strip(),
    )


def maybe_run(command: str, timeout: int = 30, required_binary: Optional[str] = None) -> str:
    if required_binary and not has_cmd(required_binary):
        return f"[SKIPPED] binary not found: {required_binary}\ncommand: {command}"
    try:
        result = run_cmd(command, timeout=timeout)
        body = result.combined
        if result.returncode != 0:
            return f"[WARN] exit={result.returncode}\n$ {command}\n{body}"
        return body
    except Exception as exc:
        return f"[ERROR] $ {command}\n{exc}"
