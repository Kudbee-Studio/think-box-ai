"""Allow running the package as a module: python3 -m thinkbox

Delegates to the KUDBEECLI entrypoint so the invocations documented in the
README (``python3 -m thinkbox swarm status``, ``ledger verify``, ``env status``,
``cli health``, ...) work as written.
"""

from thinkbox.cli import main

if __name__ == "__main__":
    main()
