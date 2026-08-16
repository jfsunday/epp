"""CLI entry point for E++."""

import argparse
import sys
from .errors import EppError
from . import run_file


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="epp",
        description="E++ interpreter — a programming language made of English words"
    )
    parser.add_argument("file", help="path to an .epp source file")
    args = parser.parse_args()

    try:
        run_file(args.file)
    except FileNotFoundError:
        print(f"Problem: could not find the file '{args.file}'", file=sys.stderr)
        sys.exit(1)
    except EppError as e:
        print(e.message, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except EOFError:
        # User closed the terminal or input stream ended
        sys.exit(0)
    except Exception as e:
        # Catch TclError etc. from closing a Tkinter window mid-operation
        if "application has been destroyed" in str(e) or "invalid command" in str(e):
            sys.exit(0)
        raise


if __name__ == "__main__":
    main()
