"""Allow `python -m epp file.epp`."""

try:
    from .main import main
except ImportError:
    from epp.main import main

main()
