#!/usr/bin/env python3
import shutil

from country_levels_lib.config import export_dir
from country_levels_lib.export import export_0


def main():
    shutil.rmtree(export_dir, ignore_errors=True)
    export_dir.mkdir()

    export_0()


if __name__ == "__main__":
    main()