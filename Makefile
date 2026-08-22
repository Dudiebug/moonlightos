SHELL := /bin/bash
.DEFAULT_GOAL := help

ISO := build/out/moonlightos-0.1.4-amd64.iso

.PHONY: help fetch-apps configure build checksum test qemu-smoke clean

help:
	@printf '%s\n' \
	  'make fetch-apps  Download and verify pinned application images' \
	  'make configure   Prepare the live-build work tree' \
	  'sudo make build  Build the Debian 13 hybrid ISO and checksum' \
	  'make test         Run source/static tests' \
	  'make qemu-smoke   Boot the ISO and wait for the appliance marker' \
	  'sudo make clean   Remove generated build state'

fetch-apps:
	./scripts/fetch-apps.sh

configure: fetch-apps
	./build/configure.sh

build: configure
	./build/build.sh

checksum:
	test -f "$(ISO)"
	cd build/out && sha256sum "$$(basename "$(ISO)")" > "$$(basename "$(ISO)").sha256"

test:
	./tests/test-static.sh
	python3 -m unittest -v tests/test_host_address.py
	python3 -m unittest -v tests/test_support.py
	$(MAKE) -C launcher test


qemu-smoke:
	./tests/qemu-smoke.sh "$(ISO)"

clean:
	./build/clean.sh
