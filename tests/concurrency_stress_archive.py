"""Empirical Concurrency and Stress Harness for SessionArchive.

Tests:
1. Fresh DB Cold-Start Race: 20 threads connecting to a non-existent DB.
2. Idempotent Save Race: 20 threads saving the exact same session.
3. Multi-Threaded Deletion Race: 20 threads racing to delete the same session.
4. Survey Upsert Race: 20 threads upserting surveys for the same session.
5. High-Contention Mixed Load: 30 threads performing 600 mixed operations.
6. Multi-Instance Load: 20 separate SessionArchive instances on one DB file.
7. Concurrent Orphan Survey vs Trajectory Race: racing writes and deletes.
8. Rapid Delete-While-Reading Stress: readers polling under rapid churn.
"""

from __future__ import annotations

import concurrent.futures
import random
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from services.api.archive import SessionArchive
from services.effects.engine import CommitReason
from services.effects.events import Event, EventType


def make_mock_session(session_id: str, effect_id: str = "card_prediction") -> Any:
    return SimpleNamespace(
        session_id=session_id,
        effect=SimpleNamespace(id=effect_id),
        turn=3,
        prediction=SimpleNamespace(hypothesis_id="AS", label="Ace of Spades", confidence=0.95),
        last_outcome_correct=True,
        committed_because=CommitReason.ENTROPY_THRESHOLD,
        history=[
            Event(
                session_id=session_id,
                type=EventType.SESSION_STARTED,
                ts="2026-10-04T12:00:00Z",
                payload={"session_id": session_id},
            )
        ],
    )


def test_cold_start_race() -> None:
    print("[1/8] Running Cold-Start Race Test (20 threads on brand new DB)...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "cold_start.db"
        num_threads = 20
        barrier = threading.Barrier(num_threads)
        errors: list[Exception] = []

        def worker(tid: int):
            try:
                archive = SessionArchive(db_path)
                barrier.wait(timeout=5)
                # Some save, some query
                if tid % 2 == 0:
                    archive.save(make_mock_session(f"cold_session_{tid}"))
                else:
                    archive.list_summaries()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Cold start race failed with errors: {errors}"
        archive = SessionArchive(db_path)
        summaries = archive.list_summaries()
        assert len(summaries) == 10, f"Expected 10 saved sessions, got {len(summaries)}"
    print("  -> PASSED: Cold start initialized schema cleanly without locking errors.")


def test_idempotent_save_race() -> None:
    print("[2/8] Running Idempotent Save Race Test (20 threads saving exact same session)...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "save_race.db"
        archive = SessionArchive(db_path)
        num_threads = 20
        barrier = threading.Barrier(num_threads)
        results: list[dict[str, Any]] = []
        errors: list[Exception] = []
        session = make_mock_session("racing_session_1")

        def worker():
            try:
                barrier.wait(timeout=5)
                summary = archive.save(session)
                results.append(summary)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Save race failed with errors: {errors}"
        assert len(results) == num_threads, f"Expected {num_threads} results, got {len(results)}"
        assert all(r["session_id"] == "racing_session_1" for r in results)
        summaries = archive.list_summaries()
        assert len(summaries) == 1, f"Expected 1 row in DB, got {len(summaries)}"
    print("  -> PASSED: All 20 threads completed save cleanly; exactly 1 record retained.")


def test_deletion_race_single_winner() -> None:
    print("[3/8] Running Deletion Race Test (Single-Winner Oracle across 10 sessions)...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "del_race.db"
        archive = SessionArchive(db_path)
        num_threads = 20

        for session_idx in range(10):
            sid = f"target_del_{session_idx}"
            archive.save(make_mock_session(sid))
            archive.save_survey(
                sid,
                condition="b",
                answers={"impossibility": 6, "freedom": 5, "naturalness": 7, "surprise": 4},
                created_at="2026-10-04T00:00:00Z",
            )

            barrier = threading.Barrier(num_threads)
            returns: list[bool] = []
            errors: list[Exception] = []

            def worker(b=barrier, s=sid, r=returns, e=errors):
                try:
                    b.wait(timeout=5)
                    ret = archive.delete(s)
                    r.append(ret)
                except Exception as ex:
                    e.append(ex)

            threads = [threading.Thread(target=worker) for _ in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert not errors, f"Deletion race failed with errors: {errors}"
            true_count = returns.count(True)
            false_count = returns.count(False)
            assert true_count == 1, (
                f"{sid}: Exactly 1 thread must return True, got {true_count}T, {false_count}F"
            )
            assert false_count == num_threads - 1

        assert archive.list_summaries() == []
        assert archive.survey_rows() == []
    print("  -> PASSED: Single-winner oracle verified (exactly 1 True, 19 False).")


def test_survey_upsert_race() -> None:
    print("[4/8] Running Survey Upsert Race Test (20 threads concurrently saving survey)...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "survey_race.db"
        archive = SessionArchive(db_path)
        sid = "survey_race_sid"
        num_threads = 20
        barrier = threading.Barrier(num_threads)
        errors: list[Exception] = []

        def worker(tid: int):
            try:
                barrier.wait(timeout=5)
                archive.save_survey(
                    sid,
                    condition="b" if tid % 2 == 0 else "a",
                    answers={
                        "impossibility": tid % 7 + 1,
                        "freedom": 5,
                        "naturalness": 6,
                        "surprise": 5,
                        "willing_repeat": bool(tid % 2),
                    },
                    created_at=f"2026-10-04T00:00:{tid:02d}Z",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Survey upsert race failed with errors: {errors}"
        surveys = archive.survey_rows()
        assert len(surveys) == 1, f"Expected exactly 1 survey row, got {len(surveys)}"
        assert surveys[0]["session_id"] == sid
    print("  -> PASSED: Concurrent survey upserts completed without duplicate key/locking errors.")


def test_high_contention_mixed_load() -> None:
    print("[5/8] Running High-Contention Mixed Load (30 threads, 600 operations)...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "mixed_load.db"
        archive = SessionArchive(db_path)
        num_threads = 30
        ops_per_thread = 20
        errors: list[Exception] = []

        def worker(tid: int):
            rng = random.Random(42 + tid)
            for _step in range(ops_per_thread):
                op = rng.choice(["save", "save_survey", "delete", "list", "survey_rows", "stats"])
                sid = f"session_{rng.randint(0, 15)}"
                try:
                    if op == "save":
                        archive.save(make_mock_session(sid))
                    elif op == "save_survey":
                        archive.save_survey(
                            sid,
                            condition=rng.choice(["a", "b"]),
                            answers={
                                "impossibility": rng.randint(1, 7),
                                "freedom": rng.randint(1, 7),
                                "naturalness": rng.randint(1, 7),
                                "surprise": rng.randint(1, 7),
                                "willing_repeat": rng.choice([True, False, None]),
                            },
                            created_at="2026-10-04T12:00:00Z",
                        )
                    elif op == "delete":
                        archive.delete(sid)
                    elif op == "list":
                        archive.list_summaries()
                    elif op == "survey_rows":
                        archive.survey_rows()
                    elif op == "stats":
                        archive.stats()
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"High-contention mixed load failed with errors: {errors}"
    print("  -> PASSED: 600 mixed concurrent operations executed with 0 errors or lock collisions.")


def test_multi_instance_concurrent_access() -> None:
    print("[6/8] Running Multi-Instance Concurrent Load (20 independent instances on 1 DB)...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "multi_instance.db"
        seed_archive = SessionArchive(db_path)
        seed_archive.save(make_mock_session("seed_session"))

        num_instances = 20
        errors: list[Exception] = []

        def worker(tid: int):
            local_archive = SessionArchive(db_path)
            sid = f"multi_inst_{tid}"
            try:
                local_archive.save(make_mock_session(sid))
                local_archive.save_survey(
                    sid,
                    condition="a",
                    answers={"impossibility": 5, "freedom": 4, "naturalness": 5, "surprise": 5},
                    created_at="2026-10-04T12:00:00Z",
                )
                local_archive.list_summaries()
                local_archive.stats()
                if tid % 2 == 0:
                    local_archive.delete(sid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_instances)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"Multi-instance test failed with errors: {errors}"
    print("  -> PASSED: Multi-instance concurrent writes and reads succeeded seamlessly.")


def test_concurrent_orphan_survey_race() -> None:
    print("[7/8] Running Concurrent Orphan Survey vs Trajectory Race...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "orphan_race.db"
        archive = SessionArchive(db_path)
        num_sessions = 15
        errors: list[Exception] = []

        def write_survey(sid: str):
            try:
                archive.save_survey(
                    sid,
                    condition="b",
                    answers={"impossibility": 6, "freedom": 6, "naturalness": 6, "surprise": 6},
                    created_at="2026-10-04T12:00:00Z",
                )
            except Exception as e:
                errors.append(e)

        def write_session(sid: str):
            try:
                archive.save(make_mock_session(sid))
            except Exception as e:
                errors.append(e)

        def delete_session(sid: str):
            try:
                archive.delete(sid)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            futures = []
            for i in range(num_sessions):
                sid = f"orphan_race_{i}"
                futures.append(pool.submit(write_survey, sid))
                futures.append(pool.submit(write_session, sid))
                futures.append(pool.submit(delete_session, sid))
            concurrent.futures.wait(futures)

        assert not errors, f"Orphan survey race failed with errors: {errors}"
    print("  -> PASSED: Orphan surveys and sessions handled concurrently with 0 errors.")


def test_rapid_delete_while_reading_stress() -> None:
    print("[8/8] Running Rapid Delete-While-Reading Stress Test...")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "read_delete_stress.db"
        archive = SessionArchive(db_path)
        stop_event = threading.Event()
        errors: list[Exception] = []

        def writer():
            counter = 0
            while not stop_event.is_set():
                sid = f"churn_{counter}"
                try:
                    archive.save(make_mock_session(sid))
                    archive.save_survey(
                        sid,
                        condition="b",
                        answers={"impossibility": 7, "freedom": 7, "naturalness": 7, "surprise": 7},
                        created_at="2026-10-04T12:00:00Z",
                    )
                    archive.delete(sid)
                    counter += 1
                except Exception as e:
                    errors.append(e)
                    break

        def reader():
            while not stop_event.is_set():
                try:
                    archive.list_summaries()
                    archive.survey_rows()
                    archive.stats()
                except Exception as e:
                    errors.append(e)
                    break

        writer_threads = [threading.Thread(target=writer) for _ in range(5)]
        reader_threads = [threading.Thread(target=reader) for _ in range(10)]

        for t in writer_threads + reader_threads:
            t.start()

        time.sleep(2.0)
        stop_event.set()

        for t in writer_threads + reader_threads:
            t.join(timeout=5)

        assert not errors, f"Rapid delete-while-reading failed with errors: {errors}"
    print("  -> PASSED: Continuous reader queries under high churn completed without error.")


def main():
    print("=" * 80)
    print("STARTING SESSIONARCHIVE CONCURRENCY & STRESS TEST HARNESS")
    print("=" * 80)
    t0 = time.time()

    test_cold_start_race()
    test_idempotent_save_race()
    test_deletion_race_single_winner()
    test_survey_upsert_race()
    test_high_contention_mixed_load()
    test_multi_instance_concurrent_access()
    test_concurrent_orphan_survey_race()
    test_rapid_delete_while_reading_stress()

    elapsed = time.time() - t0
    print("=" * 80)
    print(f"ALL 8 CONCURRENCY & STRESS SUITES PASSED EMPIRICALLY IN {elapsed:.2f}s")
    print("=" * 80)


if __name__ == "__main__":
    main()
