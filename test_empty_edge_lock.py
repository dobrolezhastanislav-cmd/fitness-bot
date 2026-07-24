"""Unit tests for the empty-edge registration lock (get_locked_empty_edge_class_ids).

Run: python -m pytest test_empty_edge_lock.py -v   (or: python test_empty_edge_lock.py)
No Google Sheets access needed — get_today_planned_classes and 'now' are monkeypatched.
"""
import os
from datetime import datetime, date

os.environ.setdefault("BOT_TOKEN", "x")  # avoid config import side effects if any

import sheets


TODAY = date.today()


def _cls(cid, start, registered, status="Planned", cdate=None):
    """Build a minimal class record like a 2_1_Classes row."""
    return {
        "ClassID": cid,
        "ClassName": f"Class {cid}",
        "ClassDate": (cdate or TODAY).strftime("%d.%m.%Y"),
        "ClassStart": start,
        "ClassStatus": status,
        "AttendeeRegistered": registered,
        "SlotsRemaining": 10,
    }


class _FrozenDateTime(datetime):
    _now = None

    @classmethod
    def now(cls, tz=None):
        return cls._now


def _run(classes, now_hhmm, lock_minutes=15):
    """Return the set of locked ClassIDs given a class list + wall-clock time."""
    h, m = map(int, now_hhmm.split(":"))
    frozen = _FrozenDateTime(TODAY.year, TODAY.month, TODAY.day, h, m)
    _FrozenDateTime._now = frozen

    orig_dt = sheets.datetime
    orig_getter = sheets.get_today_planned_classes
    orig_env = os.environ.get("EMPTY_CLASS_LOCK_MINUTES")
    try:
        sheets.datetime = _FrozenDateTime
        sheets.get_today_planned_classes = lambda: sorted(
            classes, key=lambda c: str(c.get("ClassStart", "")) or ""
        )
        os.environ["EMPTY_CLASS_LOCK_MINUTES"] = str(lock_minutes)
        return sheets.get_locked_empty_edge_class_ids()
    finally:
        sheets.datetime = orig_dt
        sheets.get_today_planned_classes = orig_getter
        if orig_env is None:
            os.environ.pop("EMPTY_CLASS_LOCK_MINUTES", None)
        else:
            os.environ["EMPTY_CLASS_LOCK_MINUTES"] = orig_env


def test_first_empty_locked():
    c = [_cls("A", "17:00", 0), _cls("B", "18:00", 0), _cls("C", "19:00", 0)]
    # 16:50 → first (17:00) empty & <15min → locked. Others still >15min away.
    assert _run(c, "16:50") == {"A"}


def test_domino_next_becomes_first():
    # 17:50, 17:00 passed with 0, 18:00 & 19:00 empty → 18:00 is new first, locked.
    c = [_cls("A", "17:00", 0), _cls("B", "18:00", 0), _cls("C", "19:00", 0)]
    assert _run(c, "17:50") == {"A", "B"}


def test_middle_not_locked_when_edges_anchored():
    # 17:50: 17:00 has 1, 19:00 has 1, 18:00 empty → middle stays OPEN.
    c = [_cls("A", "17:00", 1), _cls("B", "18:00", 0), _cls("C", "19:00", 1)]
    assert _run(c, "17:50") == set()


def test_both_edges_empty_middle_anchored():
    # 16:50: 17:00 empty (locked, first), 18:00 has 2 (anchor), 19:00 empty.
    # 19:00 is >15min away at 16:50 → NOT locked yet.
    c = [_cls("A", "17:00", 0), _cls("B", "18:00", 2), _cls("C", "19:00", 0)]
    assert _run(c, "16:50") == {"A"}


def test_last_empty_locked_near_end():
    # 18:50: 19:00 empty & <15min → last locked. 17:00/18:00 passed but anchored by count.
    c = [_cls("A", "17:00", 3), _cls("B", "18:00", 2), _cls("C", "19:00", 0)]
    assert _run(c, "18:50") == {"C"}


def test_has_registration_not_locked():
    # 16:50, 17:00 has 1 registration → not locked even though <15min.
    c = [_cls("A", "17:00", 1), _cls("B", "18:00", 0), _cls("C", "19:00", 0)]
    assert _run(c, "16:50") == set()


def test_too_early_not_locked():
    # 16:30, 17:00 empty but 30min away (>15) → not locked.
    c = [_cls("A", "17:00", 0)]
    assert _run(c, "16:30") == set()


def test_single_class_is_both_edges():
    # One empty class, <15min → locked (first == last).
    c = [_cls("A", "17:00", 0)]
    assert _run(c, "16:50") == {"A"}


def test_whole_day_collapses():
    # All empty, late enough that peeling from both ends covers everything.
    c = [_cls("A", "17:00", 0), _cls("B", "18:00", 0), _cls("C", "19:00", 0)]
    # 18:55: 17:00 & 18:00 passed, 19:00 <15min. Front-peel A,B; back-peel C.
    assert _run(c, "18:55") == {"A", "B", "C"}


def test_winter_30min_window():
    # lock_minutes=30: at 16:35, 17:00 is 25min away → within 30 → locked.
    c = [_cls("A", "17:00", 0)]
    assert _run(c, "16:35", lock_minutes=30) == {"A"}
    # same time, summer 15min window → 25min away is outside → not locked.
    assert _run(c, "16:35", lock_minutes=15) == set()


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
