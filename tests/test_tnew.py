import pandas as pd

from solarde.splits.tnew import select_tnew


def test_select_tnew_test_split_only_and_not_in_previous():
    assign = pd.DataFrame({"area_id": [1, 2, 3, 4], "split": ["test", "test", "train", "test"]})
    out = select_tnew(assign, previous_ids={1, 3})
    assert out.area_id.tolist() == [2, 4]
