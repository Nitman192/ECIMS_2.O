.PHONY: test test-current test-legacy test-security

test: test-current

test-current:
	PYTHONPATH=server pytest -q server/tests -m "current"

test-legacy:
	PYTHONPATH=server pytest -q server/tests -m "legacy"

test-security:
	PYTHONPATH=server pytest -q server/tests -m "security_posture"
