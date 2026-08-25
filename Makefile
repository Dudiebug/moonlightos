SHELL := /bin/bash
.DEFAULT_GOAL := help

ISO := build/out/moonlightos-0.1.9-amd64.iso

.PHONY: help fetch-apps configure build test qemu-smoke qemu-persistence-smoke qemu-install-smoke release-gauntlet clean

help:
	@printf '%s\n' \
	  'make fetch-apps  Download pinned application images' \
	  'make configure   Prepare the live-build work tree' \
	  'sudo make build  Build the Debian 13 hybrid ISO' \
	  'make test         Run source/static tests' \
	  'make qemu-smoke   Boot the ISO and wait for the appliance marker' \
	  'make qemu-persistence-smoke  Verify live persistence and recovery boot' \
	  'make qemu-install-smoke  Install to a VM disk and boot it independently' \
	  'make release-gauntlet  Run the final source and real-ISO release gate' \
	  'sudo make clean   Remove generated build state'

fetch-apps:
	./scripts/fetch-apps.sh

configure: fetch-apps
	./build/configure.sh

build: configure
	./build/build.sh

test:
	./tests/test-static.sh
	python3 -m unittest -v tests/test_host_address.py
	python3 -m unittest -v tests/test_support.py
	python3 -m unittest -v tests/test_tailscale_enrollment.py
	python3 -m unittest -v tests/test_bluetooth_service.py
	python3 -m unittest -v tests/test_qemu_iso_boot.py
	$(MAKE) -C launcher test


qemu-smoke:
	./tests/qemu-smoke.sh "$(ISO)"

qemu-persistence-smoke:
	./tests/qemu-persistence-smoke.sh "$(ISO)"

qemu-install-smoke:
	./tests/qemu-install-smoke.sh "$(ISO)"

release-gauntlet:
	./tools/release-gauntlet.sh "$(ISO)"

clean:
	./build/clean.sh
