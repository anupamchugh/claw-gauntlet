from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


_SHA256_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")


class EvidenceIntegrityError(OSError):
    """Raised when stored evidence does not match its content hash."""


@dataclass(frozen=True)
class EvidenceRef:
    algorithm: str
    digest: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("unsupported evidence algorithm: expected sha256")
        if type(self.digest) is not str or _SHA256_DIGEST.fullmatch(self.digest) is None:
            raise ValueError("evidence digest must be exactly 64 hexadecimal characters")
        object.__setattr__(self, "digest", self.digest.lower())

    @property
    def uri(self) -> str:
        return f"evidence://{self.algorithm}/{self.digest}"


class EvidenceStore:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).resolve(strict=False)

    def put_bytes(self, content: bytes) -> EvidenceRef:
        digest = sha256(content).hexdigest()
        reference = EvidenceRef(algorithm="sha256", digest=digest)
        target = self._path_for(reference)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{digest}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, target)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
        return reference

    def put_json(self, value: Any) -> EvidenceRef:
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.put_bytes(canonical)

    def get_bytes(self, reference: EvidenceRef) -> bytes:
        reference = self._validated_reference(reference)
        content = self._path_for(reference).read_bytes()
        actual_digest = sha256(content).hexdigest()
        if actual_digest != reference.digest:
            raise EvidenceIntegrityError(
                f"evidence digest mismatch: expected {reference.digest}, got {actual_digest}"
            )
        return content

    def get_json(self, reference: EvidenceRef) -> Any:
        return json.loads(self.get_bytes(reference).decode("utf-8"))

    def verify(self, reference: EvidenceRef) -> bool:
        try:
            self.get_bytes(reference)
        except (FileNotFoundError, EvidenceIntegrityError):
            return False
        return True

    def _path_for(self, reference: EvidenceRef) -> Path:
        reference = self._validated_reference(reference)
        candidate = self.root / reference.algorithm / reference.digest[:2] / reference.digest
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise ValueError("evidence path resolves outside evidence root")
        return resolved

    @staticmethod
    def _validated_reference(reference: EvidenceRef) -> EvidenceRef:
        if not isinstance(reference, EvidenceRef):
            raise TypeError("reference must be an EvidenceRef")
        return EvidenceRef(algorithm=reference.algorithm, digest=reference.digest)
