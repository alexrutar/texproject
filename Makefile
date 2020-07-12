upload:
	-pandoc --from=markdown --to=rst --output=README.rst README.md
	-/usr/local/opt/python@3.8/bin/python3 setup.py sdist bdist_wheel
	-twine upload dist/*

.PHONY: upload test git
test:
	-trash test
	mkdir test
	tpr init preprint -C test --no-git
	echo "- tikz" >> test/.texproject/tpr_info.yaml
	tpr refresh -C test
	tpr export -C test --compression xztar

git:
	-trash test
	mkdir test
	tpr init preprint -C test
	cd test && git add main.tex && git commit -m "first commit" && git status
