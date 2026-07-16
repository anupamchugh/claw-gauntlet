import os
from pathlib import Path
import plistlib
from types import SimpleNamespace

import pytest

from claw_gauntlet.sponsor_scheduler import (
    LaunchAgentError,
    LaunchAgentManager,
    SponsorSchedule,
    managed_search_path,
    notify_owner,
)


def _schedule(tmp_path):
    return SponsorSchedule(
        executable=tmp_path / "bin" / "clawgauntlet",
        state_dir=tmp_path / "private-state",
        campaign_config=tmp_path / "campaign.json",
        workspace=tmp_path / "claw-gauntlet",
        task_dir=tmp_path / "claw-gauntlet-tasks",
    )


def test_schedule_payload_is_explicit_and_runs_monday_at_ten(tmp_path):
    schedule = _schedule(tmp_path)

    payload = schedule.to_plist()

    assert payload["Label"] == "io.github.anupamchugh.claw-gauntlet.sponsor-agent"
    assert payload["RunAtLoad"] is True
    assert payload["StartCalendarInterval"] == {"Weekday": 1, "Hour": 10, "Minute": 0}
    assert payload["ProgramArguments"] == [
        str(schedule.executable),
        "sponsor",
        "research",
        "--state-dir",
        str(schedule.state_dir),
        "--config",
        str(schedule.campaign_config),
        "--workspace",
        str(schedule.workspace),
        "--task-dir",
        str(schedule.task_dir),
        "--notify",
    ]
    assert payload["StandardOutPath"] == str(schedule.state_dir / "logs" / "sponsor-agent.log")
    assert payload["StandardErrorPath"] == str(schedule.state_dir / "logs" / "sponsor-agent.error.log")
    assert payload["EnvironmentVariables"]["PATH"].startswith("/usr/local/bin:")


def test_managed_search_path_includes_cli_codex_beads_and_system_bins(tmp_path):
    mapping = {
        "codex": "/Users/example/bin/codex",
        "bd": "/opt/homebrew/bin/bd",
        "git": "/usr/bin/git",
    }

    path = managed_search_path(
        tmp_path / "tools" / "clawgauntlet",
        which=mapping.get,
    )

    assert path.split(":") == [
        str(tmp_path / "tools"),
        "/Users/example/bin",
        "/opt/homebrew/bin",
        "/usr/bin",
        "/usr/local/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]


def test_manager_installs_private_plist_and_kickstarts(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    manager = LaunchAgentManager(
        home_directory=tmp_path / "home",
        platform="darwin",
        uid=501,
        runner=runner,
    )
    path = manager.install(_schedule(tmp_path))

    assert path == tmp_path / "home" / "Library" / "LaunchAgents" / (
        "io.github.anupamchugh.claw-gauntlet.sponsor-agent.plist"
    )
    assert os.stat(path).st_mode & 0o777 == 0o600
    with path.open("rb") as source:
        payload = plistlib.load(source)
    assert payload["RunAtLoad"] is True
    assert calls[-2][0] == ["/bin/launchctl", "bootstrap", "gui/501", str(path)]
    assert calls[-1][0] == [
        "/bin/launchctl",
        "kickstart",
        "-k",
        "gui/501/io.github.anupamchugh.claw-gauntlet.sponsor-agent",
    ]
    assert all(kwargs.get("shell") is not True for _, kwargs in calls)


def test_manager_boots_out_existing_plist_before_reinstall(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    manager = LaunchAgentManager(
        home_directory=tmp_path / "home",
        platform="darwin",
        uid=501,
        runner=runner,
    )
    manager.plist_path.parent.mkdir(parents=True)
    manager.plist_path.write_text("old", encoding="utf-8")

    manager.install(_schedule(tmp_path))

    assert calls[0] == [
        "/bin/launchctl",
        "bootout",
        "gui/501",
        str(manager.plist_path),
    ]
    assert calls[1] == [
        "/bin/launchctl",
        "bootstrap",
        "gui/501",
        str(manager.plist_path),
    ]


def test_manager_status_and_uninstall_use_user_domain(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="service", stderr="")

    manager = LaunchAgentManager(
        home_directory=tmp_path / "home",
        platform="darwin",
        uid=501,
        runner=runner,
    )
    assert manager.status() is True
    manager.uninstall()

    assert calls[0] == [
        "/bin/launchctl",
        "print",
        "gui/501/io.github.anupamchugh.claw-gauntlet.sponsor-agent",
    ]
    assert calls[1][0:3] == ["/bin/launchctl", "bootout", "gui/501"]


def test_manager_fails_closed_off_macos(tmp_path):
    manager = LaunchAgentManager(
        home_directory=tmp_path,
        platform="linux",
        uid=501,
    )

    with pytest.raises(LaunchAgentError, match="macOS"):
        manager.install(_schedule(tmp_path))


def test_notification_contains_only_count_and_safe_inbox_command():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    notify_owner(2, runner=runner)

    assert calls == [
        [
            "/usr/bin/osascript",
            "-e",
            (
                'display notification "2 sponsor drafts await review. Run: '
                'clawgauntlet sponsor inbox" with title "Claw Gauntlet"'
            ),
        ]
    ]
