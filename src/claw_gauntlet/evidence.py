from contextlib import contextmanager
from dataclasses import dataclass
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any


_SHA256_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY_FLAGS = os.O_RDONLY | _O_CLOEXEC | _O_DIRECTORY | _O_NOFOLLOW
_READ_FLAGS = os.O_RDONLY | _O_CLOEXEC | _O_NOFOLLOW
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_CLOEXEC | _O_NOFOLLOW
_SYMLINK_ERRORS = {errno.ELOOP, errno.ENOTDIR}


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
        if not _O_DIRECTORY or not _O_NOFOLLOW or os.open not in os.supports_dir_fd:
            raise RuntimeError("EvidenceStore requires no-follow descriptor-relative I/O")
        self.root = Path(root).resolve(strict=False)

    def put_bytes(self, content: bytes) -> EvidenceRef:
        digest = sha256(content).hexdigest()
        reference = EvidenceRef(algorithm="sha256", digest=digest)
        with self._artifact_directory(reference, create=True) as directory_fd:
            descriptor, temporary_name = self._create_temporary_file(
                directory_fd,
                digest,
            )
            try:
                with os.fdopen(descriptor, "wb") as temporary:
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.replace(
                    temporary_name,
                    digest,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                )
                os.fsync(directory_fd)
            except BaseException:
                try:
                    os.unlink(temporary_name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                raise
        return reference

    def put_json(self, value: Any) -> EvidenceRef:
        canonical = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.put_bytes(canonical)

    def get_bytes(self, reference: EvidenceRef) -> bytes:
        reference = self._validated_reference(reference)
        with self._artifact_directory(reference, create=False) as directory_fd:
            try:
                descriptor = os.open(
                    reference.digest,
                    _READ_FLAGS,
                    dir_fd=directory_fd,
                )
            except OSError as error:
                self._raise_for_unsafe_path(error)
                raise
            with os.fdopen(descriptor, "rb") as evidence:
                content = evidence.read()
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

    @contextmanager
    def _artifact_directory(self, reference: EvidenceRef, *, create: bool):
        reference = self._validated_reference(reference)
        root_fd = self._open_root(create=create)
        algorithm_fd = None
        prefix_fd = None
        try:
            algorithm_fd = self._open_child_directory(
                root_fd,
                reference.algorithm,
                create=create,
            )
            prefix_fd = self._open_child_directory(
                algorithm_fd,
                reference.digest[:2],
                create=create,
            )
            yield prefix_fd
        finally:
            if prefix_fd is not None:
                os.close(prefix_fd)
            if algorithm_fd is not None:
                os.close(algorithm_fd)
            os.close(root_fd)

    def _open_root(self, *, create: bool) -> int:
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        try:
            return os.open(self.root, _DIRECTORY_FLAGS)
        except OSError as error:
            self._raise_for_unsafe_path(error)
            raise

    def _open_child_directory(self, parent_fd: int, name: str, *, create: bool) -> int:
        if create:
            try:
                os.mkdir(name, mode=0o755, dir_fd=parent_fd)
            except FileExistsError:
                pass
            else:
                os.fsync(parent_fd)
        try:
            return os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
        except OSError as error:
            self._raise_for_unsafe_path(error)
            raise

    @staticmethod
    def _create_temporary_file(directory_fd: int, digest: str) -> tuple[int, str]:
        for _ in range(100):
            name = f".{digest}.{secrets.token_hex(8)}.tmp"
            try:
                descriptor = os.open(
                    name,
                    _WRITE_FLAGS,
                    mode=0o600,
                    dir_fd=directory_fd,
                )
            except FileExistsError:
                continue
            return descriptor, name
        raise FileExistsError("could not allocate a unique evidence temporary file")

    @staticmethod
    def _raise_for_unsafe_path(error: OSError) -> None:
        if error.errno in _SYMLINK_ERRORS:
            raise ValueError("evidence path resolves outside evidence root") from error

    @staticmethod
    def _validated_reference(reference: EvidenceRef) -> EvidenceRef:
        if not isinstance(reference, EvidenceRef):
            raise TypeError("reference must be an EvidenceRef")
        return EvidenceRef(algorithm=reference.algorithm, digest=reference.digest)
