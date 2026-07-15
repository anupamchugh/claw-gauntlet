from dataclasses import asdict, dataclass
import re
from typing import Any


_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_STATUSES = {"planned", "experimental", "stable", "deprecated"}


def parse_semver(value: str) -> tuple[int, int, int]:
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid semantic version: {value}")
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class CapabilityManifest:
    name: str
    version: str
    protocol_version: str
    status: str
    kind: str
    capabilities: tuple[str, ...]
    permissions: tuple[str, ...]

    def __post_init__(self) -> None:
        parse_semver(self.version)
        parse_semver(self.protocol_version)
        if self.status not in _STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        if not self.name or not self.capabilities:
            raise ValueError("name and capabilities are required")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["permissions"] = list(self.permissions)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityManifest":
        return cls(
            name=str(payload["name"]),
            version=str(payload["version"]),
            protocol_version=str(payload["protocol_version"]),
            status=str(payload["status"]),
            kind=str(payload["kind"]),
            capabilities=tuple(str(item) for item in payload["capabilities"]),
            permissions=tuple(str(item) for item in payload["permissions"]),
        )
