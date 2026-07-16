from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import plistlib
import secrets
import subprocess
import sys
from typing import Any


_LABEL = "io.github.anupamchugh.claw-gauntlet.sponsor-agent"


class LaunchAgentError(RuntimeError):
    """A redacted launchd or local-notification failure."""


def _absolute(path: str | Path, field: str) -> Path:
    value = Path(path)
    if not value.is_absolute():
        raise ValueError(f"{field} must be an absolute path")
    return value


@dataclass(frozen=True)
class SponsorSchedule:
    executable: Path
    state_dir: Path
    campaign_config: Path
    workspace: Path
    task_dir: Path
    weekday: int = 1
    hour: int = 10

    def __post_init__(self) -> None:
        for field in (
            "executable",
            "state_dir",
            "campaign_config",
            "workspace",
            "task_dir",
        ):
            object.__setattr__(self, field, _absolute(getattr(self, field), field))
        if type(self.weekday) is not int or not 1 <= self.weekday <= 7:
            raise ValueError("weekday must be an integer from 1 to 7")
        if type(self.hour) is not int or not 0 <= self.hour <= 23:
            raise ValueError("hour must be an integer from 0 to 23")

    def to_plist(self) -> dict[str, Any]:
        logs = self.state_dir / "logs"
        return {
            "Label": _LABEL,
            "ProgramArguments": [
                str(self.executable),
                "sponsor",
                "research",
                "--state-dir",
                str(self.state_dir),
                "--config",
                str(self.campaign_config),
                "--workspace",
                str(self.workspace),
                "--task-dir",
                str(self.task_dir),
                "--notify",
            ],
            "RunAtLoad": True,
            "StartCalendarInterval": {
                "Weekday": self.weekday,
                "Hour": self.hour,
                "Minute": 0,
            },
            "ProcessType": "Background",
            "StandardOutPath": str(logs / "sponsor-agent.log"),
            "StandardErrorPath": str(logs / "sponsor-agent.error.log"),
        }


class LaunchAgentManager:
    def __init__(
        self,
        *,
        home_directory: str | Path | None = None,
        platform: str = sys.platform,
        uid: int | None = None,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.home_directory = Path.home() if home_directory is None else Path(home_directory)
        self.platform = platform
        self.uid = os.getuid() if uid is None else uid
        self.runner = runner

    @property
    def plist_path(self) -> Path:
        return self.home_directory / "Library" / "LaunchAgents" / f"{_LABEL}.plist"

    @property
    def service_target(self) -> str:
        return f"gui/{self.uid}/{_LABEL}"

    def install(self, schedule: SponsorSchedule) -> Path:
        self._require_macos()
        if not isinstance(schedule, SponsorSchedule):
            raise TypeError("schedule must be a SponsorSchedule")
        schedule.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        schedule.state_dir.chmod(0o700)
        logs = schedule.state_dir / "logs"
        logs.mkdir(mode=0o700, exist_ok=True)
        logs.chmod(0o700)
        path = self.plist_path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode=0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                plistlib.dump(schedule.to_plist(), output, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            path.chmod(0o600)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        self._run(
            ["/bin/launchctl", "bootstrap", f"gui/{self.uid}", str(path)],
            "bootstrap Sponsor Agent",
        )
        self._run(
            ["/bin/launchctl", "kickstart", "-k", self.service_target],
            "kickstart Sponsor Agent",
        )
        return path

    def status(self) -> bool:
        self._require_macos()
        result = self._invoke(["/bin/launchctl", "print", self.service_target])
        return result.returncode == 0

    def uninstall(self) -> None:
        self._require_macos()
        path = self.plist_path
        self._invoke(
            ["/bin/launchctl", "bootout", f"gui/{self.uid}", str(path)]
        )
        path.unlink(missing_ok=True)

    def _require_macos(self) -> None:
        if self.platform != "darwin":
            raise LaunchAgentError("Sponsor Agent scheduling currently requires macOS launchd")

    def _invoke(self, command: list[str]):
        try:
            return self.runner(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            raise LaunchAgentError("launchctl could not be started") from error

    def _run(self, command: list[str], action: str) -> None:
        result = self._invoke(command)
        if result.returncode != 0:
            raise LaunchAgentError(
                f"Could not {action} (exit {result.returncode}); stderr redacted"
            )


def notify_owner(
    count: int,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> None:
    if type(count) is not int or count < 1:
        raise ValueError("notification count must be a positive integer")
    script = (
        f'display notification "{count} sponsor drafts await review. Run: '
        'clawgauntlet sponsor inbox" with title "Claw Gauntlet"'
    )
    try:
        result = runner(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise LaunchAgentError("macOS notification could not start") from error
    if result.returncode != 0:
        raise LaunchAgentError(
            f"macOS notification failed (exit {result.returncode}); stderr redacted"
        )
