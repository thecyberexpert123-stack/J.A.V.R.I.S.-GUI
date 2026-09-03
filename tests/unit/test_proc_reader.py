"""Tests for ProcReader.

Every parser is exercised three ways: against realistic fixtures, against
malformed input, and against a missing tree. The reader must never raise, and
must never invent a value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from javris.telemetry.models import CpuTimes, NetworkCounters
from javris.telemetry.proc_reader import ProcReader

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def reader() -> ProcReader:
    return ProcReader(proc_root=FIXTURES / "proc", sys_root=FIXTURES / "sys")


@pytest.fixture
def malformed() -> ProcReader:
    return ProcReader(proc_root=FIXTURES / "malformed", sys_root=FIXTURES / "malformed")


@pytest.fixture
def missing(tmp_path: Path) -> ProcReader:
    return ProcReader(proc_root=tmp_path / "nope", sys_root=tmp_path / "nope")


# -- CPU -------------------------------------------------------------------


def test_cpu_times_parses_aggregate_and_cores(reader: ProcReader) -> None:
    aggregate, cores = reader.cpu_times()
    assert aggregate is not None
    assert aggregate.name == "cpu"
    # idle (900000) + iowait (3000)
    assert aggregate.idle_all == 903_000
    assert aggregate.total == 120_000 + 500 + 40_000 + 900_000 + 3_000 + 0 + 800
    assert [core.name for core in cores] == ["cpu0", "cpu1"]


def test_cpu_times_on_malformed_input_yields_nothing(malformed: ProcReader) -> None:
    aggregate, cores = malformed.cpu_times()
    assert aggregate is None
    # "cpu0 1 2" has too few fields to be a valid sample.
    assert cores == ()


def test_cpu_times_on_missing_file(missing: ProcReader) -> None:
    assert missing.cpu_times() == (None, ())


def test_utilisation_computes_busy_fraction() -> None:
    before = CpuTimes("cpu", idle_all=100, total=200)
    after = CpuTimes("cpu", idle_all=150, total=300)
    # 100 jiffies elapsed, 50 idle -> 50% busy
    assert ProcReader.utilisation(before, after) == pytest.approx(0.5)


def test_utilisation_fully_busy_and_fully_idle() -> None:
    assert ProcReader.utilisation(CpuTimes("cpu", 0, 0), CpuTimes("cpu", 0, 100)) == 1.0
    assert ProcReader.utilisation(CpuTimes("cpu", 0, 0), CpuTimes("cpu", 100, 100)) == 0.0


@pytest.mark.parametrize(
    ("before", "after"),
    [
        # No elapsed time.
        (CpuTimes("cpu", 100, 200), CpuTimes("cpu", 100, 200)),
        # Counters moved backwards (suspend/resume, hotplug).
        (CpuTimes("cpu", 100, 200), CpuTimes("cpu", 50, 100)),
        # Idle grew more than total: incoherent sample.
        (CpuTimes("cpu", 100, 200), CpuTimes("cpu", 400, 250)),
        # Mismatched CPUs must never be compared.
        (CpuTimes("cpu0", 100, 200), CpuTimes("cpu1", 150, 300)),
    ],
)
def test_utilisation_rejects_incoherent_samples(before: CpuTimes, after: CpuTimes) -> None:
    assert ProcReader.utilisation(before, after) is None


# -- memory ----------------------------------------------------------------


def test_memory_converts_kb_to_bytes(reader: ProcReader) -> None:
    memory = reader.memory()
    assert memory is not None
    assert memory.total == 8_039_484 * 1024
    assert memory.available == 4_019_742 * 1024
    assert memory.used == memory.total - memory.available
    assert memory.used_fraction == pytest.approx(0.5, abs=0.01)
    assert memory.swap_total == 2_097_148 * 1024
    assert memory.swap_used == 0
    assert memory.swap_used_fraction == 0.0


def test_memory_requires_mandatory_fields(malformed: ProcReader) -> None:
    # MemTotal is unparseable and MemAvailable is absent.
    assert malformed.memory() is None


def test_memory_on_missing_file(missing: ProcReader) -> None:
    assert missing.memory() is None


# -- load and uptime -------------------------------------------------------


def test_load_average(reader: ProcReader) -> None:
    load = reader.load_average()
    assert load is not None
    assert (load.one, load.five, load.fifteen) == (0.52, 0.61, 0.58)


def test_load_average_malformed_and_missing(malformed: ProcReader, missing: ProcReader) -> None:
    assert malformed.load_average() is None
    assert missing.load_average() is None


def test_uptime(reader: ProcReader) -> None:
    assert reader.uptime_seconds() == pytest.approx(186_234.55)


def test_uptime_malformed_and_missing(malformed: ProcReader, missing: ProcReader) -> None:
    assert malformed.uptime_seconds() is None
    assert missing.uptime_seconds() is None


# -- network ---------------------------------------------------------------


def test_network_counters_sum_excludes_loopback(reader: ProcReader) -> None:
    counters = reader.network_counters()
    assert counters is not None
    assert counters.rx_bytes == 1_048_576 + 524_288
    assert counters.tx_bytes == 524_288 + 262_144


def test_network_counters_malformed_yields_zeroes(malformed: ProcReader) -> None:
    # The file exists but holds no usable interface lines: zero is the truth.
    counters = malformed.network_counters()
    assert counters == NetworkCounters(rx_bytes=0, tx_bytes=0)


def test_network_counters_missing(missing: ProcReader) -> None:
    assert missing.network_counters() is None


def test_throughput() -> None:
    before = NetworkCounters(1_000, 2_000)
    after = NetworkCounters(3_000, 4_500)
    result = ProcReader.throughput(before, after, elapsed=2.0)
    assert result == (1_000.0, 1_250.0)


@pytest.mark.parametrize(
    ("before", "after", "elapsed"),
    [
        (NetworkCounters(1_000, 1_000), NetworkCounters(2_000, 2_000), 0.0),
        (NetworkCounters(1_000, 1_000), NetworkCounters(2_000, 2_000), -1.0),
        # Counter wrap or interface removal.
        (NetworkCounters(5_000, 5_000), NetworkCounters(10, 10), 1.0),
    ],
)
def test_throughput_rejects_impossible_intervals(
    before: NetworkCounters, after: NetworkCounters, elapsed: float
) -> None:
    assert ProcReader.throughput(before, after, elapsed) is None


# -- thermals --------------------------------------------------------------


def test_temperature_converts_millidegrees(reader: ProcReader) -> None:
    assert reader.temperature_celsius() == pytest.approx(45.0)


def test_temperature_absent_when_no_thermal_zones(missing: ProcReader) -> None:
    assert missing.temperature_celsius() is None


def test_temperature_rejects_implausible_readings(tmp_path: Path) -> None:
    zone = tmp_path / "class" / "thermal" / "thermal_zone0"
    zone.mkdir(parents=True)
    (zone / "temp").write_text("999000\n")  # 999 C is not a real reading
    (zone / "type").write_text("acpitz\n")
    assert ProcReader(sys_root=tmp_path).temperature_celsius() is None


def test_temperature_prefers_package_sensor(tmp_path: Path) -> None:
    thermal = tmp_path / "class" / "thermal"
    for index, (zone_type, milli) in enumerate([("acpitz", "30000"), ("x86_pkg_temp", "55000")]):
        zone = thermal / f"thermal_zone{index}"
        zone.mkdir(parents=True)
        (zone / "temp").write_text(milli)
        (zone / "type").write_text(zone_type)
    assert ProcReader(sys_root=tmp_path).temperature_celsius() == pytest.approx(55.0)


# -- storage ---------------------------------------------------------------


def test_disks_skips_pseudo_filesystems(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "mounts").write_text(
        f"proc /proc proc rw 0 0\ntmpfs /dev/shm tmpfs rw 0 0\n/dev/sda1 {tmp_path} ext4 rw 0 0\n"
    )
    disks = ProcReader(proc_root=proc).disks()
    assert [disk.mount_point for disk in disks] == [str(tmp_path)]
    assert disks[0].total > 0
    assert 0.0 <= disks[0].used_fraction <= 1.0


def test_disks_ignores_unstattable_mounts(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "mounts").write_text("/dev/sdb1 /definitely/not/here ext4 rw 0 0\n")
    assert ProcReader(proc_root=proc).disks() == ()


def test_disks_missing_mounts_file(missing: ProcReader) -> None:
    assert missing.disks() == ()


def test_disks_respects_limit(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    points = []
    for index in range(3):
        mount = tmp_path / f"m{index}"
        mount.mkdir()
        points.append(f"/dev/sd{index} {mount} ext4 rw 0 0")
    (proc / "mounts").write_text("\n".join(points) + "\n")
    assert len(ProcReader(proc_root=proc).disks(limit=2)) == 2
