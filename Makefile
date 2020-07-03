upload:
	-pandoc --from=markdown --to=rst --output=README.rst README.md
	-/usr/local/opt/python@3.8/bin/python3 setup.py sdist bdist_wheel
	-twine upload dist/*
