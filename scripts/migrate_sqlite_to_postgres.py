"""Operator-only migration: use a reviewed backup and a fresh target database."""

import argparse
import os

from course2career.data_migration import copy_sqlite_to_postgres


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_sqlite")
    parser.add_argument("--acknowledge-source-data", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_source_data:
        parser.error("先确认源快照的数据权利、备份与目标环境。")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("缺少 DATABASE_URL。")
    counts = copy_sqlite_to_postgres(args.source_sqlite, database_url)
    print("迁移完成；各表行数：", counts)


if __name__ == "__main__":
    main()
