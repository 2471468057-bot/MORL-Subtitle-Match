"""Fast 2ByteASR launcher: open the workbench first, then drop media into it."""

from __future__ import annotations

import os
import sys


PIPELINE_BUILD_ID = "2026.08.05-v7.14-strict-length-number-style"


def main() -> int:
    import moss_firered_pipeline
    import subtitle_core
    from twobyteasr.ui import run_desktop_app

    moss_firered_pipeline.verify_pipeline_contract(
        subtitle_core,
        os.path.realpath(__file__),
        PIPELINE_BUILD_ID,
    )
    return run_desktop_app(
        subtitle_core,
        moss_firered_pipeline,
        None,
        select_media=False,
        initial_paths=sys.argv[1:],
    )


if __name__ == "__main__":
    raise SystemExit(main())
