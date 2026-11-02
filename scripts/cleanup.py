"""Optional external scheduler entrypoint; credentials come from DATABASE_URL."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.database import cleanup_old_data

if __name__ == "__main__":
    result=cleanup_old_data()
    print("Cleanup completed" if result is True else "Cleanup skipped" if result is None else "Cleanup failed; see logs")
    raise SystemExit(1 if result is False else 0)
