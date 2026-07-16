import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable

from claw_gauntlet.sponsorship import SponsorCampaign, SponsorResearchReport


class ResearchAgentError(RuntimeError):
    """A bounded sponsor research subprocess failure with redacted output."""


def _report_schema() -> dict[str, Any]:
    prospect = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "public_url": {"type": "string", "format": "uri", "maxLength": 2048},
            "lane": {
                "type": "string",
                "enum": ["community-sponsor", "company-pilot", "feedback"],
            },
            "fit_reason": {"type": "string", "minLength": 1, "maxLength": 500},
            "evidence_urls": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {"type": "string", "format": "uri", "maxLength": 2048},
            },
            "subject": {"type": "string", "minLength": 1, "maxLength": 160},
            "body": {"type": "string", "minLength": 1, "maxLength": 2000},
            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": [
            "name",
            "public_url",
            "lane",
            "fit_reason",
            "evidence_urls",
            "subject",
            "body",
            "confidence",
        ],
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
            "prospects": {"type": "array", "maxItems": 5, "items": prospect},
        },
        "required": ["summary", "prospects"],
    }


def _prompt(campaign: SponsorCampaign) -> str:
    campaign_json = json.dumps(
        campaign.to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"""You are the read-only SponsorClaw researcher for an open-source project.

Research current public web and GitHub evidence for the campaign below. Learn
from the named repositories' public sponsorship and project-positioning
patterns. Identify at most {campaign.max_drafts} high-fit prospects across the
requested categories. Prefer a small, defensible list over weak matches.

Rules:
- Use public HTTPS sources only.
- Never send, post, message, follow, star, open an issue, or mutate anything.
- Never collect or output email addresses, private contact details, secrets,
  credentials, private repositories, cookies, or personal data.
- A star, follow, or repository contribution is not permission to contact.
- Do not claim a prospect uses, endorses, or depends on the project unless a
  cited source explicitly proves that claim.
- `community-sponsor` is for a relevant open-source community supporter.
- `company-pilot` is for a company with a publicly evidenced workflow fit.
- `feedback` asks for expertise, not money.
- Drafts must be short, truthful, individualized, and easy to decline.
- Return only the JSON object required by the output schema.

CAMPAIGN_JSON:
{campaign_json}
"""


class CodexSponsorResearcher:
    def __init__(
        self,
        state_root: str | Path,
        *,
        working_directory: str | Path,
        executable: str = "codex",
        runner: Callable[..., Any] = subprocess.run,
        timeout_seconds: int = 600,
    ) -> None:
        if type(timeout_seconds) is not int or not 30 <= timeout_seconds <= 1_800:
            raise ValueError("timeout_seconds must be an integer from 30 to 1800")
        self.state_root = Path(state_root)
        self.working_directory = Path(working_directory)
        self.executable = executable
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    def research(self, campaign: SponsorCampaign) -> SponsorResearchReport:
        if not isinstance(campaign, SponsorCampaign):
            raise TypeError("campaign must be a SponsorCampaign")
        temporary_root = self.state_root / "research-tmp"
        temporary_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary_root.chmod(0o700)
        run_directory = Path(tempfile.mkdtemp(prefix="cycle-", dir=temporary_root))
        run_directory.chmod(0o700)
        schema_path = run_directory / "report.schema.json"
        output_path = run_directory / "report.json"
        schema_path.write_text(
            json.dumps(_report_schema(), sort_keys=True),
            encoding="utf-8",
        )
        schema_path.chmod(0o600)
        command = [
            self.executable,
            "exec",
            "--ephemeral",
            "--search",
            "--ignore-user-config",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--cd",
            str(self.working_directory),
            "-",
        ]
        try:
            try:
                result = self.runner(
                    command,
                    input=_prompt(campaign),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as error:
                raise ResearchAgentError(
                    f"Codex sponsor research timed out after {self.timeout_seconds} seconds"
                ) from error
            except OSError as error:
                raise ResearchAgentError("Codex sponsor research could not start") from error
            if result.returncode != 0:
                raise ResearchAgentError(
                    f"Codex sponsor research failed (exit {result.returncode}); "
                    "stdout and stderr redacted"
                )
            if not output_path.is_file():
                raise ResearchAgentError("Codex sponsor research produced no report")
            output_path.chmod(0o600)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            return SponsorResearchReport.from_dict(payload)
        finally:
            shutil.rmtree(run_directory, ignore_errors=True)
