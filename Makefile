.PHONY: upload

upload:
	-/Users/alexrutar/.pyenv/shims/python -m build
	-twine upload -u '__token__' -p $(keyring get pypi_texproject_token alexrutar) dist/*
