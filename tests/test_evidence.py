from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from hashlib import sha256
import os
from pathlib import Path
import signal
import socket
import stat
import tempfile
import time

import pytest

from claw_gauntlet import evidence as evidence_module
from claw_gauntlet.evidence import EvidenceRef, EvidenceStore


def _artifact_target(root, reference):
    return root / "sha256" / reference.digest[:2] / reference.digest


@contextmanager
def _one_second_deadline():
    def deadline_expired(signum, frame):
        raise TimeoutError("evidence operation exceeded one second")

    previous_handler = signal.signal(signal.SIGALRM, deadline_expired)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 1.0)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def test_put_is_content_addressed_idempotent_and_verified(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    first = store.put_json({"source": "public", "items": [1, 2]})
    second = store.put_json({"items": [1, 2], "source": "public"})

    assert first == second
    assert first.uri.startswith("evidence://sha256/")
    assert store.get_json(first) == {"items": [1, 2], "source": "public"}
    assert store.verify(first)


def test_put_json_uses_compact_sorted_utf8_canonical_bytes(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    canonical = '{"a":1,"b":2,"é":"☃"}'.encode("utf-8")

    reference = store.put_json({"é": "☃", "b": 2, "a": 1})

    assert reference.digest == sha256(canonical).hexdigest()
    assert store.get_bytes(reference) == canonical


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_put_json_rejects_nonfinite_floats_without_artifacts(tmp_path, value):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)

    with pytest.raises(ValueError, match="JSON compliant"):
        store.put_json({"value": value})

    assert not [path for path in root.rglob("*") if path.is_file()]


def test_put_bytes_replaces_from_a_temporary_file_in_the_target_directory(
    tmp_path, monkeypatch
):
    store = EvidenceStore(tmp_path / "evidence")
    replacements = []
    real_replace = evidence_module.os.replace

    def record_replace(source, destination, **kwargs):
        source_path = Path(source)
        destination_path = Path(destination)
        assert kwargs["src_dir_fd"] == kwargs["dst_dir_fd"]
        assert os.stat(source, dir_fd=kwargs["src_dir_fd"])
        replacements.append((source_path, destination_path, kwargs))
        real_replace(source, destination, **kwargs)

    monkeypatch.setattr(evidence_module.os, "replace", record_replace)

    reference = store.put_bytes(b"atomic evidence")

    expected = (
        tmp_path
        / "evidence"
        / "sha256"
        / reference.digest[:2]
        / reference.digest
    )
    assert len(replacements) == 1
    assert replacements[0][1] == Path(reference.digest)
    assert expected.read_bytes() == b"atomic evidence"
    assert expected in expected.parent.iterdir()
    assert not [
        path for path in expected.parent.iterdir() if path.name.endswith(".tmp")
    ]


def test_put_bytes_fsyncs_artifact_and_parent_directory(tmp_path, monkeypatch):
    store = EvidenceStore(tmp_path / "evidence")
    fsynced_types = []
    real_fsync = evidence_module.os.fsync

    def record_fsync(descriptor):
        fsynced_types.append(stat.S_IFMT(os.fstat(descriptor).st_mode))
        real_fsync(descriptor)

    monkeypatch.setattr(evidence_module.os, "fsync", record_fsync)

    store.put_bytes(b"durable evidence")

    assert stat.S_IFREG in fsynced_types
    assert stat.S_IFDIR in fsynced_types


def test_failed_atomic_replace_removes_the_temporary_file(tmp_path, monkeypatch):
    store = EvidenceStore(tmp_path / "evidence")

    def fail_replace(source, destination, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(evidence_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        store.put_bytes(b"will not be stored")

    assert not [
        path
        for path in (tmp_path / "evidence").rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    ]


def test_directory_fsync_failure_preserves_preexisting_valid_artifact(
    tmp_path, monkeypatch
):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)
    content = b"stable"
    reference = store.put_bytes(content)
    target = _artifact_target(root, reference)
    real_fsync = evidence_module.os.fsync

    def fail_directory_fsync(descriptor):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError("directory fsync failed")
        real_fsync(descriptor)

    monkeypatch.setattr(evidence_module.os, "fsync", fail_directory_fsync)

    with pytest.raises(OSError, match="directory fsync failed"):
        store.put_bytes(content)

    assert target.read_bytes() == content
    assert store.verify(reference)


def test_failing_writer_does_not_delete_concurrent_same_digest_replacement(
    tmp_path, monkeypatch
):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)
    content = b"same digest"
    reference = store.put_bytes(content)
    target = _artifact_target(root, reference)
    real_fsync = evidence_module.os.fsync
    real_replace = evidence_module.os.replace
    concurrent_identity = None
    injected = False

    def install_concurrent_replacement_then_fail(descriptor):
        nonlocal concurrent_identity, injected
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode) or injected:
            real_fsync(descriptor)
            return
        injected = True
        concurrent_name = f".{reference.digest}.concurrent"
        concurrent_fd = os.open(
            concurrent_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode=0o600,
            dir_fd=descriptor,
        )
        try:
            os.write(concurrent_fd, content)
            real_fsync(concurrent_fd)
        finally:
            os.close(concurrent_fd)
        real_replace(
            concurrent_name,
            reference.digest,
            src_dir_fd=descriptor,
            dst_dir_fd=descriptor,
        )
        metadata = os.stat(
            reference.digest,
            dir_fd=descriptor,
            follow_symlinks=False,
        )
        concurrent_identity = (metadata.st_dev, metadata.st_ino)
        raise OSError("directory fsync failed after concurrent replace")

    monkeypatch.setattr(
        evidence_module.os,
        "fsync",
        install_concurrent_replacement_then_fail,
    )

    with pytest.raises(OSError, match="concurrent replace"):
        store.put_bytes(content)

    metadata = target.stat()
    assert (metadata.st_dev, metadata.st_ino) == concurrent_identity
    assert target.read_bytes() == content
    assert store.verify(reference)


def test_directory_swap_to_symlink_cannot_redirect_write_outside_root(
    tmp_path, monkeypatch
):
    content = b"escaped write"
    digest = sha256(content).hexdigest()
    root = tmp_path / "evidence"
    algorithm_directory = root / "sha256"
    displaced_directory = root / "sha256-before-swap"
    outside = tmp_path / "outside"
    algorithm_directory.mkdir(parents=True)
    (outside / digest[:2]).mkdir(parents=True)
    store = EvidenceStore(root)
    real_open = evidence_module.os.open
    swapped = False

    def swap_before_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        path_value = os.fspath(path)
        opening_algorithm_relative_to_root = (
            dir_fd is not None and path_value == "sha256"
        )
        opening_old_temporary_path = (
            dir_fd is None
            and path_value.startswith(str(algorithm_directory / digest[:2]))
            and path_value.endswith(".tmp")
        )
        if not swapped and (
            opening_algorithm_relative_to_root or opening_old_temporary_path
        ):
            algorithm_directory.rename(displaced_directory)
            algorithm_directory.symlink_to(outside, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(evidence_module.os, "open", swap_before_open)

    with pytest.raises(ValueError, match="outside evidence root"):
        store.put_bytes(content)

    assert swapped
    assert not [path for path in outside.rglob("*") if path.is_file()]


def test_post_open_directory_relocation_is_cleaned_and_fails_closed(
    tmp_path, monkeypatch
):
    content = b"late escaped write"
    digest = sha256(content).hexdigest()
    root = tmp_path / "evidence"
    outside = tmp_path / "outside"
    moved_algorithm_directory = outside / "moved-sha256"
    outside.mkdir()
    store = EvidenceStore(root)
    real_replace = evidence_module.os.replace
    relocated = False

    def relocate_before_replace(source, destination, **kwargs):
        nonlocal relocated
        algorithm_directory = root / "sha256"
        algorithm_directory.rename(moved_algorithm_directory)
        algorithm_directory.symlink_to(
            moved_algorithm_directory,
            target_is_directory=True,
        )
        relocated = True
        real_replace(source, destination, **kwargs)

    monkeypatch.setattr(evidence_module.os, "replace", relocate_before_replace)

    with pytest.raises(ValueError):
        store.put_bytes(content)

    assert relocated
    assert not (moved_algorithm_directory / digest[:2] / digest).exists()


def test_store_rejects_group_or_world_writable_root(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir(mode=0o777)
    root.chmod(0o777)
    store = EvidenceStore(root)

    with pytest.raises(PermissionError, match="writable"):
        store.put_bytes(b"untrusted root")


def test_store_creates_root_mode_0700_under_permissive_umask(tmp_path):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)
    previous_umask = os.umask(0)
    try:
        reference = store.put_bytes(b"restrictive root")
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert store.verify(reference)


def test_corruption_fails_verification_and_verified_read(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    reference = store.put_bytes(b"trusted")
    target = (
        tmp_path
        / "evidence"
        / "sha256"
        / reference.digest[:2]
        / reference.digest
    )
    target.write_bytes(b"tampered")

    assert store.verify(reference) is False
    with pytest.raises(evidence_module.EvidenceIntegrityError, match="digest mismatch"):
        store.get_bytes(reference)


def test_repeated_put_repairs_corrupt_content_at_the_same_reference(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    reference = store.put_bytes(b"stable")
    target = (
        tmp_path
        / "evidence"
        / "sha256"
        / reference.digest[:2]
        / reference.digest
    )
    target.write_bytes(b"corrupt")

    repeated = store.put_bytes(b"stable")

    assert repeated == reference
    assert store.get_bytes(reference) == b"stable"


def test_valid_missing_reference_raises_file_not_found(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    missing = EvidenceRef(algorithm="sha256", digest="0" * 64)

    with pytest.raises(FileNotFoundError):
        store.get_bytes(missing)
    assert store.verify(missing) is False


def test_directory_leaf_fails_integrity_without_unrelated_error(tmp_path):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)
    reference = EvidenceRef(algorithm="sha256", digest="1" * 64)
    target = _artifact_target(root, reference)
    target.mkdir(parents=True)

    with _one_second_deadline():
        assert store.verify(reference) is False
    with pytest.raises(evidence_module.EvidenceIntegrityError, match="regular file"):
        store.get_bytes(reference)


def test_fifo_leaf_fails_integrity_without_blocking(tmp_path):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)
    reference = EvidenceRef(algorithm="sha256", digest="2" * 64)
    target = _artifact_target(root, reference)
    target.parent.mkdir(parents=True)
    os.mkfifo(target)

    started = time.monotonic()
    with _one_second_deadline():
        assert store.verify(reference) is False
    assert time.monotonic() - started < 0.5
    with _one_second_deadline():
        with pytest.raises(evidence_module.EvidenceIntegrityError, match="regular file"):
            store.get_bytes(reference)


def test_unix_socket_leaf_fails_integrity_without_unrelated_error():
    with tempfile.TemporaryDirectory(prefix="cg-", dir="/tmp") as directory:
        root = Path(directory) / "evidence"
        store = EvidenceStore(root)
        reference = EvidenceRef(algorithm="sha256", digest="3" * 64)
        target = _artifact_target(root, reference)
        target.parent.mkdir(parents=True)
        server = socket.socket(socket.AF_UNIX)
        server.bind(str(target))
        try:
            with _one_second_deadline():
                assert store.verify(reference) is False
            with pytest.raises(
                evidence_module.EvidenceIntegrityError,
                match="regular file",
            ):
                store.get_bytes(reference)
        finally:
            server.close()


def test_leaf_symlink_fails_integrity_without_following_target(tmp_path):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)
    reference = EvidenceRef(algorithm="sha256", digest="4" * 64)
    target = _artifact_target(root, reference)
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    target.symlink_to(outside)

    with _one_second_deadline():
        assert store.verify(reference) is False
    with pytest.raises(evidence_module.EvidenceIntegrityError, match="regular file"):
        store.get_bytes(reference)


def test_multi_link_leaf_fails_integrity(tmp_path):
    root = tmp_path / "evidence"
    store = EvidenceStore(root)
    content = b"linked content"
    reference = EvidenceRef(algorithm="sha256", digest=sha256(content).hexdigest())
    target = _artifact_target(root, reference)
    target.parent.mkdir(parents=True)
    outside = tmp_path / "outside-link"
    outside.write_bytes(content)
    os.link(outside, target)

    with _one_second_deadline():
        assert store.verify(reference) is False
    with pytest.raises(evidence_module.EvidenceIntegrityError, match="one link"):
        store.get_bytes(reference)


def test_evidence_ref_is_immutable_and_normalizes_sha256_hex_to_lowercase():
    reference = EvidenceRef(algorithm="sha256", digest="A" * 64)

    assert reference.digest == "a" * 64
    assert reference.uri == f"evidence://sha256/{'a' * 64}"
    with pytest.raises(FrozenInstanceError):
        reference.digest = "0" * 64


@pytest.mark.parametrize(
    ("algorithm", "digest"),
    [
        ("sha1", "0" * 64),
        ("../sha256", "0" * 64),
        ("sha256", "../" + "0" * 61),
        ("sha256", "g" * 64),
        ("sha256", "0" * 63),
    ],
)
def test_evidence_ref_rejects_unsupported_or_malformed_values(algorithm, digest):
    with pytest.raises(ValueError):
        EvidenceRef(algorithm=algorithm, digest=digest)


def test_store_rejects_symlink_escape_from_root(tmp_path):
    root = tmp_path / "evidence"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "sha256").symlink_to(outside, target_is_directory=True)
    reference = EvidenceRef(algorithm="sha256", digest="0" * 64)
    escaped_target = outside / "00" / reference.digest
    escaped_target.parent.mkdir()
    escaped_target.write_bytes(b"outside the evidence root")

    store = EvidenceStore(root)

    with pytest.raises(ValueError, match="outside evidence root"):
        store.get_bytes(reference)
