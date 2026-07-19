"""Compile-time build flavor. The prod build ships DEV_BUILD = False; the dev
build (build-dev.bat) flips it to True and freezes it into the binary. It is NOT
read from env/argv, so a prod exe can't be switched into dev mode at runtime."""

DEV_BUILD = False
