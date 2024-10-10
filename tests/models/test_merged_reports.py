from copy import deepcopy

from lsst.cmservice import models


def test_merged_product_set() -> None:
    """Tests MergedProductSet pydantic model"""

    set_1_alice = models.MergedProductSet(
        name="alice",
        n_expected=10,
        n_failed=1,
        n_failed_upstream=2,
        n_missing=3,
        n_done=4,
    )
    set_2_alice = models.MergedProductSet(
        name="alice",
        n_expected=6,
        n_failed=0,
        n_failed_upstream=0,
        n_missing=1,
        n_done=5,
    )
    set_1_bob = models.MergedProductSet(
        name="bob",
        n_expected=10,
        n_failed=1,
        n_failed_upstream=2,
        n_missing=3,
        n_done=4,
    )
    set_2_bob = models.MergedProductSet(
        name="bob",
        n_expected=6,
        n_failed=1,
        n_failed_upstream=0,
        n_missing=0,
        n_done=5,
    )

    set_1_merge = models.MergedProductSetDict(
        reports=dict(
            alice=deepcopy(set_1_alice),
            bob=deepcopy(set_1_bob),
        ),
    )

    set_1_iadd = models.MergedProductSetDict(
        reports=dict(
            alice=deepcopy(set_1_alice),
            bob=deepcopy(set_1_bob),
        ),
    )

    set_2 = models.MergedProductSetDict(
        reports=dict(
            alice=deepcopy(set_2_alice),
            bob=deepcopy(set_2_bob),
        ),
    )

    assert set_1_merge.reports["alice"].n_failed == 1
    assert set_1_merge.reports["alice"].n_failed_upstream == 2
    assert set_1_merge.reports["alice"].n_missing == 3
    assert set_1_merge.reports["alice"].n_done == 4
    assert set_1_merge.reports["alice"].n_expected == 10

    set_1_merge.merge(set_2)
    set_1_iadd += set_2

    assert set_1_merge.reports["alice"].n_failed == 0
    assert set_1_merge.reports["alice"].n_failed_upstream == 0
    assert set_1_merge.reports["alice"].n_missing == 1
    assert set_1_merge.reports["alice"].n_done == 9
    assert set_1_merge.reports["alice"].n_expected == 10

    assert set_1_iadd.reports["alice"].n_failed == 1
    assert set_1_iadd.reports["alice"].n_failed_upstream == 2
    assert set_1_iadd.reports["alice"].n_missing == 4
    assert set_1_iadd.reports["alice"].n_done == 9
    assert set_1_iadd.reports["alice"].n_expected == 16

    assert set_1_merge.reports["bob"].n_failed == 1
    assert set_1_merge.reports["bob"].n_failed_upstream == 0
    assert set_1_merge.reports["bob"].n_missing == 0
    assert set_1_merge.reports["bob"].n_done == 9
    assert set_1_merge.reports["bob"].n_expected == 10

    assert set_1_iadd.reports["bob"].n_failed == 2
    assert set_1_iadd.reports["bob"].n_failed_upstream == 2
    assert set_1_iadd.reports["bob"].n_missing == 3
    assert set_1_iadd.reports["bob"].n_done == 9
    assert set_1_iadd.reports["bob"].n_expected == 16


def test_merged_task_set() -> None:
    """Tests MergedTaskSet pydantic model"""

    set_1_alice = models.MergedTaskSet(
        name="alice",
        n_expected=10,
        n_failed=1,
        n_failed_upstream=2,
        n_done=7,
    )
    set_2_alice = models.MergedTaskSet(
        name="alice",
        n_expected=3,
        n_failed=1,
        n_failed_upstream=0,
        n_done=2,
    )
    set_1_bob = models.MergedTaskSet(
        name="bob",
        n_expected=10,
        n_failed=1,
        n_failed_upstream=2,
        n_done=7,
    )
    set_2_bob = models.MergedTaskSet(
        name="bob",
        n_expected=3,
        n_failed=0,
        n_failed_upstream=1,
        n_done=2,
    )

    set_1 = models.MergedTaskSetDict(
        reports=dict(
            alice=deepcopy(set_1_alice),
            bob=deepcopy(set_1_bob),
        ),
    )

    set_1_merge = models.MergedTaskSetDict(
        reports=dict(),
    )
    set_1_merge.merge(set_1)

    set_1_iadd = models.MergedTaskSetDict(
        reports=dict(),
    )
    set_1_iadd += set_1

    set_2 = models.MergedTaskSetDict(
        reports=dict(
            alice=deepcopy(set_2_alice),
            bob=deepcopy(set_2_bob),
        ),
    )

    assert set_1_merge.reports["alice"].n_failed == 1
    assert set_1_merge.reports["alice"].n_failed_upstream == 2
    assert set_1_merge.reports["alice"].n_done == 7
    assert set_1_merge.reports["alice"].n_expected == 10

    set_1_merge.merge(set_2)
    set_1_iadd += set_2

    assert set_1_merge.reports["alice"].n_failed == 1
    assert set_1_merge.reports["alice"].n_failed_upstream == 0
    assert set_1_merge.reports["alice"].n_done == 9
    assert set_1_merge.reports["alice"].n_expected == 10

    assert set_1_iadd.reports["alice"].n_failed == 2
    assert set_1_iadd.reports["alice"].n_failed_upstream == 2
    assert set_1_iadd.reports["alice"].n_done == 9
    assert set_1_iadd.reports["alice"].n_expected == 13

    assert set_1_merge.reports["bob"].n_failed == 0
    assert set_1_merge.reports["bob"].n_failed_upstream == 1
    assert set_1_merge.reports["bob"].n_done == 9
    assert set_1_merge.reports["bob"].n_expected == 10

    assert set_1_iadd.reports["bob"].n_failed == 1
    assert set_1_iadd.reports["bob"].n_failed_upstream == 3
    assert set_1_iadd.reports["bob"].n_done == 9
    assert set_1_iadd.reports["bob"].n_expected == 13


def test_merged_wms_task_report() -> None:
    """Tests MergedWmsTaskReport pydantic model"""

    set_1_alice = models.MergedWmsTaskReport(
        name="alice",
        n_expected=10,
        n_failed=3,
        n_succeeded=7,
    )
    set_2_alice = models.MergedWmsTaskReport(
        name="alice",
        n_expected=3,
        n_failed=1,
        n_succeeded=2,
    )
    set_1_bob = models.MergedWmsTaskReport(
        name="bob",
        n_expected=10,
        n_failed=3,
        n_succeeded=7,
    )
    set_2_bob = models.MergedWmsTaskReport(
        name="bob",
        n_expected=3,
        n_failed=2,
        n_succeeded=1,
    )

    set_1_iadd = models.MergedWmsTaskReportDict(
        reports=dict(
            alice=deepcopy(set_1_alice),
            bob=deepcopy(set_1_bob),
        ),
    )

    set_2 = models.MergedWmsTaskReportDict(
        reports=dict(
            alice=deepcopy(set_2_alice),
            bob=deepcopy(set_2_bob),
        ),
    )

    assert set_1_iadd.reports["alice"].n_failed == 3
    assert set_1_iadd.reports["alice"].n_succeeded == 7
    assert set_1_iadd.reports["alice"].n_expected == 10

    set_1_iadd += set_2

    assert set_1_iadd.reports["alice"].n_failed == 4
    assert set_1_iadd.reports["alice"].n_succeeded == 9
    assert set_1_iadd.reports["alice"].n_expected == 13

    assert set_1_iadd.reports["bob"].n_failed == 5
    assert set_1_iadd.reports["bob"].n_succeeded == 8
    assert set_1_iadd.reports["bob"].n_expected == 13
