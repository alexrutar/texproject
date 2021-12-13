tpr = python3 -m texproject

upload:
	-pandoc --from=markdown --to=rst --output=README.rst README.md
	-/Users/alexrutar/.pyenv/shims/python3 setup.py sdist bdist_wheel
	-twine upload dist/*

.PHONY: upload test git
test:
	-trash test
	mkdir test
	$(tpr) init preprint -C test --no-git
	echo "- tikz" >> test/.texproject/tpr_info.yaml
	$(tpr) config --no-edit -C test
	$(tpr) export -C test --compression zip
	-unzip test/test.zip -d test/post

test-latex: test
	-cd test && latexmk -pdf main.tex > /dev/null

git:
	-trash test
	mkdir test
	$(tpr) init preprint -C test
	cd test && git add main.tex && git commit -m "first commit" && git status

