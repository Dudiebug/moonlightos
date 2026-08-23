.PHONY: test
test:
	python3 -m py_compile moonlightos-launcher.py moonlightos_bluetooth.py moonlightos_display.py moonlightos_support.py gamepad-nav.py
	python3 -m unittest -v test_launcher.py test_bluetooth.py test_display.py test_gamepad_nav.py
