from contextlib import contextmanager
from dataclasses import dataclass
import errno
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any


_SHA256_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_DIRECTORY_FLAGS = os.O_RDONLY | _O_CLOEXEC | _O_DIRECTORY | _O_NOFOLLOW
_READ_FLAGS = os.O_RDONLY | _O_CLOEXEC | _O_NOFOLLOW | _O_NONBLOCK
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_CLOEXEC | _O_NOFOLLOW
_LOCK_FLAGS = os.O_RDWR | os.O_CREAT | _O_CLOEXEC | _O_NOFOLLOW
_SYMLINK_ERRORS = {errno.ELOOP, errno.ENOTDIR}
_REQUIRED_DIR_FD_FUNCTIONS = (os.open, os.mkdir, os.unlink, os.rename, os.stat)


class EvidenceIntegrityError(OSError):
    """Raised when stored evidence does not match its content hash."""


class _EvidenceContainmentChangedError(ValueError):
    """Raised when descriptor checks prove the configured path changed."""


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
    """POSIX evidence store rooted in caller-protected directories.

    The configured root and its ancestors are a trust boundary: callers must
    prevent same-identity processes from renaming them. Opened store directories
    must be owned by the effective user and not group- or world-writable. Each
    write also verifies directory identity before and after replacement so a
    detected relocation is cleaned through the retained descriptor and fails.
    Cooperating writers serialize each digest with a POSIX advisory file lock.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        dir_fd_support = all(
            function in os.supports_dir_fd
            for function in _REQUIRED_DIR_FD_FUNCTIONS
        )
        if (
            os.name != "posix"
            or not hasattr(os, "geteuid")
            or not _O_DIRECTORY
            or not _O_NOFOLLOW
            or not _O_NONBLOCK
            or not dir_fd_support
        ):
            raise RuntimeError(
                "EvidenceStore requires POSIX no-follow descriptor-relative I/O"
            )
        self.root = Path(root).resolve(strict=False)

    def put_bytes(self, content: bytes) -> EvidenceRef:
        digest = sha256(content).hexdigest()
        reference = EvidenceRef(algorithm="sha256", digest=digest)
        with self._artifact_directory(reference, create=True) as directory_chain:
            root_fd, algorithm_fd, directory_fd = directory_chain
            with self._digest_lock(directory_fd, digest):
                self._put_locked(
                    content,
                    reference,
                    root_fd,
                    algorithm_fd,
                    directory_fd,
                )
        return reference

    def _put_locked(
        self,
        content: bytes,
        reference: EvidenceRef,
        root_fd: int,
        algorithm_fd: int,
        directory_fd: int,
    ) -> None:
        digest = reference.digest
        if self._existing_artifact_matches(directory_fd, digest):
            self._assert_directory_chain(
                reference,
                root_fd,
                algorithm_fd,
                directory_fd,
            )
            return

        descriptor, temporary_name = self._create_temporary_file(
            directory_fd,
            digest,
        )
        try:
            with os.fdopen(descriptor, "wb") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                metadata = os.fstat(temporary.fileno())
                installed_identity = (metadata.st_dev, metadata.st_ino)
        except BaseException:
            self._cleanup_name(directory_fd, temporary_name)
            raise

        try:
            self._assert_directory_chain(
                reference,
                root_fd,
                algorithm_fd,
                directory_fd,
            )
            os.replace(
                temporary_name,
                digest,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
        except BaseException:
            self._cleanup_name(directory_fd, temporary_name)
            raise

        # The leaf is fully written and file-fsynced. A directory-fsync error
        # means durability is uncertain, so preserve the valid committed leaf.
        os.fsync(directory_fd)

        try:
            self._assert_directory_chain(
                reference,
                root_fd,
                algorithm_fd,
                directory_fd,
            )
        except _EvidenceContainmentChangedError:
            self._cleanup_installed_inode(
                directory_fd,
                digest,
                installed_identity,
            )
            raise

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
        with self._artifact_directory(reference, create=False) as directory_chain:
            _, _, directory_fd = directory_chain
            try:
                descriptor = os.open(
                    reference.digest,
                    _READ_FLAGS,
                    dir_fd=directory_fd,
                )
            except FileNotFoundError:
                raise
            except OSError as error:
                raise EvidenceIntegrityError(
                    "evidence artifact must be a regular file with exactly one link"
                ) from error
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise EvidenceIntegrityError(
                        "evidence artifact must be a regular file with exactly one link"
                    )
                evidence = os.fdopen(descriptor, "rb")
            except BaseException:
                os.close(descriptor)
                raise
            with evidence:
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
            yield root_fd, algorithm_fd, prefix_fd
        finally:
            if prefix_fd is not None:
                os.close(prefix_fd)
            if algorithm_fd is not None:
                os.close(algorithm_fd)
            os.close(root_fd)

    def _open_root(self, *, create: bool) -> int:
        if create:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.root, _DIRECTORY_FLAGS)
        except OSError as error:
            self._raise_for_unsafe_path(error)
            raise
        try:
            self._validate_trusted_directory(descriptor)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    def _open_child_directory(self, parent_fd: int, name: str, *, create: bool) -> int:
        if create:
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            else:
                os.fsync(parent_fd)
        try:
            descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
        except OSError as error:
            self._raise_for_unsafe_path(error)
            raise
        try:
            self._validate_trusted_directory(descriptor)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    def _assert_directory_chain(
        self,
        reference: EvidenceRef,
        root_fd: int,
        algorithm_fd: int,
        prefix_fd: int,
    ) -> None:
        reopened_root = self._open_root(create=False)
        try:
            self._require_same_directory(root_fd, reopened_root)
        finally:
            os.close(reopened_root)

        reopened_algorithm = self._open_child_directory(
            root_fd,
            reference.algorithm,
            create=False,
        )
        try:
            self._require_same_directory(algorithm_fd, reopened_algorithm)
        finally:
            os.close(reopened_algorithm)

        reopened_prefix = self._open_child_directory(
            algorithm_fd,
            reference.digest[:2],
            create=False,
        )
        try:
            self._require_same_directory(prefix_fd, reopened_prefix)
        finally:
            os.close(reopened_prefix)

    @staticmethod
    def _require_same_directory(expected_fd: int, actual_fd: int) -> None:
        expected = os.fstat(expected_fd)
        actual = os.fstat(actual_fd)
        if (expected.st_dev, expected.st_ino) != (actual.st_dev, actual.st_ino):
            raise _EvidenceContainmentChangedError(
                "evidence directory containment changed during operation"
            )

    @staticmethod
    def _validate_trusted_directory(descriptor: int) -> None:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("evidence path component must be a directory")
        if metadata.st_uid != os.geteuid():
            raise PermissionError("evidence directories must be owned by the effective user")
        if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise PermissionError(
                "evidence directories must not be group- or world-writable"
            )

    @staticmethod
    def _cleanup_name(directory_fd: int, name: str) -> None:
        try:
            os.unlink(name, dir_fd=directory_fd)
        except FileNotFoundError:
            return
        os.fsync(directory_fd)

    @staticmethod
    def _cleanup_installed_inode(
        directory_fd: int,
        name: str,
        installed_identity: tuple[int, int],
    ) -> None:
        try:
            metadata = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        if (metadata.st_dev, metadata.st_ino) != installed_identity:
            return
        os.unlink(name, dir_fd=directory_fd)
        os.fsync(directory_fd)

    @staticmethod
    def _existing_artifact_matches(directory_fd: int, digest: str) -> bool:
        try:
            descriptor = os.open(
                digest,
                _READ_FLAGS,
                dir_fd=directory_fd,
            )
        except FileNotFoundError:
            return False
        except OSError as error:
            if error.errno in _SYMLINK_ERRORS:
                return False
            raise EvidenceIntegrityError(
                "existing evidence artifact could not be inspected safely"
            ) from error
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                return False
            with os.fdopen(descriptor, "rb", closefd=False) as artifact:
                actual_digest = sha256(artifact.read()).hexdigest()
        finally:
            os.close(descriptor)
        return actual_digest == digest

    @contextmanager
    def _digest_lock(self, directory_fd: int, digest: str):
        name = f".{digest}.lock"
        try:
            descriptor = os.open(
                name,
                _LOCK_FLAGS,
                mode=0o600,
                dir_fd=directory_fd,
            )
        except OSError as error:
            raise EvidenceIntegrityError("evidence digest lock is unsafe") from error
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid()
                or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            ):
                raise EvidenceIntegrityError("evidence digest lock is unsafe")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)

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
            raise _EvidenceContainmentChangedError(
                "evidence path resolves outside evidence root"
            ) from error

    @staticmethod
    def _validated_reference(reference: EvidenceRef) -> EvidenceRef:
        if not isinstance(reference, EvidenceRef):
            raise TypeError("reference must be an EvidenceRef")
        return EvidenceRef(algorithm=reference.algorithm, digest=reference.digest)
