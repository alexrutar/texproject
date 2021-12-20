SHELL := /usr/local/bin/fish

.PHONY: upload test

upload:
	-/Users/alexrutar/.pyenv/shims/python -m build
	-TWINE_USERNAME="__token__" TWINE_PASSWORD=(keyring get pypi_texproject_token alexrutar) twine upload dist/*

test:
	pyright
	pytest
