import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.command_file_processor import process_command_file


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python -m app.cli <command_file_path>")
        sys.exit(1)
    cmd_path = Path(argv[0])
    if not cmd_path.is_file():
        print(f"Command file not found: {cmd_path}")
        sys.exit(1)
    # Open a DB session
    db = SessionLocal()
    try:
        results = process_command_file(db, cmd_path)
        for entry in results:
            print(entry)
    finally:
        db.close()

if __name__ == "__main__":
    main()
