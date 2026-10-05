from __future__ import annotations

import pytest

from jarvis_show.lock import AlreadyRunning, InstanceLock


def test_lock_can_be_taken_writes_the_pid_and_blocks_a_second_instance(tmp_path):
    path = tmp_path / "x.lock"
    with InstanceLock(path):
        assert path.read_text().strip().isdigit()
        with pytest.raises(AlreadyRunning):
            with InstanceLock(path):
                pass
    with InstanceLock(path):  # released after the first one exits
        pass
