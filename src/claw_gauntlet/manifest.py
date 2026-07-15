from dataclasses import asdict, dataclass
import re
from typing import Any


_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_STATUSES = {"planned", "experimental", "stable", "deprecated"}


def _nonempty_string(value: Any, field: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _string_tuple(value: Any, field: str, *, required: bool = False) -> tuple[str, ...]:
    if type(value) not in (list, tuple):
        raise ValueError(f"{field} must be a list or tuple of nonempty strings")
    items = tuple(value)
    if required and not items:
        raise ValueError(f"{field} must contain at least one item")
    if any(type(item) is not str or not item for item in items):
        raise ValueError(f"{field} must contain only nonempty strings")
    return items


def _payload_string_list(value: Any, field: str, *, required: bool = False) -> tuple[str, ...]:
    if type(value) is not list:
        raise ValueError(f"{field} must be a list of nonempty strings")
    return _string_tuple(value, field, required=required)


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
        _nonempty_string(self.name, "name")
        _nonempty_string(self.version, "version")
        _nonempty_string(self.protocol_version, "protocol_version")
        _nonempty_string(self.status, "status")
        _nonempty_string(self.kind, "kind")
        object.__setattr__(
            self,
            "capabilities",
            _string_tuple(self.capabilities, "capabilities", required=True),
        )
        object.__setattr__(self, "permissions", _string_tuple(self.permissions, "permissions"))
        parse_semver(self.version)
        parse_semver(self.protocol_version)
        if self.status not in _STATUSES:
            raise ValueError(f"invalid status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["permissions"] = list(self.permissions)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityManifest":
        return cls(
            name=_nonempty_string(payload["name"], "name"),
            version=_nonempty_string(payload["version"], "version"),
            protocol_version=_nonempty_string(payload["protocol_version"], "protocol_version"),
            status=_nonempty_string(payload["status"], "status"),
            kind=_nonempty_string(payload["kind"], "kind"),
            capabilities=_payload_string_list(
                payload["capabilities"],
                "capabilities",
                required=True,
            ),
            permissions=_payload_string_list(payload["permissions"], "permissions"),
        )
