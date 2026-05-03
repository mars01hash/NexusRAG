
import os
import sys
from pathlib import Path

def check_locks():
    index_files = [
        "data/faiss_index/index.faiss",
        "data/faiss_index/index.pkl"
    ]
    for f in index_files:
        path = Path(f)
        if not path.exists():
            print(f"{f} does not exist")
            continue
        try:
            # Try to open for writing
            with open(path, "a") as lock_test:
                print(f"{f} is NOT locked (opened for appending)")
        except PermissionError:
            print(f"{f} IS LOCKED (PermissionError)")
        except Exception as e:
            print(f"Error checking {f}: {e}")

if __name__ == "__main__":
    check_locks()
