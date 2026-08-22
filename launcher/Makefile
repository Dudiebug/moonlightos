.PHONY: test
test:
	python3 -m py_compile moonlightos-launcher.py moonlightos_display.py moonlightos_support.py gamepad-nav.py escape-guard.py
	python3 -m unittest -v test_launcher.py test_display.py test_gamepad_nav.py test_escape_guard.py
