#!/bin/sh
# Build a quickjs-ng wheel (QuickJS scripting engine, "scripting-engine": "quickjs") for a platform without PyPI wheels, as OpenWrt armv7.
# It builds in an Alpine container (musl, as OpenWrt); the wheel is abi3, so it works on every CPython >= 3.10.
# Needs docker and, for a foreign architecture, qemu user emulation (Arch Linux: pacman -S qemu-user-static qemu-user-static-binfmt,
# then systemctl restart systemd-binfmt). It takes a few minutes under emulation.
#
#   bin/build-quickjs-wheel.sh [output dir, default: ./dist]
#
# Environment: PLATFORM (default linux/arm/v7), ALPINE_VERSION (default 3.19: python 3.11, as OpenWrt 24.10), QUICKJS_NG_VERSION (default 0.18.0.2)
#
# Install the wheel on the node (it has no dependencies, and the node does not need a compiler):
#   pip3 install --no-deps quickjs_ng-*-linux_armv7l.whl

set -e
OUT_ARG=${1:-dist}
mkdir -p "$OUT_ARG"
OUT=$(CDPATH= cd -- "$OUT_ARG" && pwd)

docker run --rm --platform "${PLATFORM:-linux/arm/v7}" -v "$OUT:/out" -e QUICKJS_NG_VERSION="${QUICKJS_NG_VERSION:-0.18.0.2}" \
  "alpine:${ALPINE_VERSION:-3.19}" sh -ec '
  apk add -q python3 python3-dev py3-pip gcc musl-dev
  python3 -m venv /tmp/venv
  /tmp/venv/bin/pip install -q --upgrade pip setuptools wheel
  cd /tmp
  CFLAGS="-O2 -g0" LDFLAGS="-Wl,-s" /tmp/venv/bin/pip wheel -q --no-deps --no-build-isolation --no-binary quickjs-ng -w /tmp/wheel "quickjs-ng==$QUICKJS_NG_VERSION"
  /tmp/venv/bin/pip install -q --no-deps /tmp/wheel/*.whl
  /tmp/venv/bin/python -c "import quickjs; assert quickjs.Context().eval(\"[1, 2].map(x => x * 2).join()\") == \"2,4\""
  cp /tmp/wheel/*.whl /out/
  chown "$(stat -c %u:%g /out)" /out/quickjs_ng-*.whl
'
ls -l "$OUT"/quickjs_ng-*.whl
