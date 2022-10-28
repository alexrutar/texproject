# Distribution Instructions
First, update the virtual environment:
```
pyenv virtualenv uninstall texproject-venv
pyenv virtualenv 3.10.7 texproject-venv
```
Next, install locally as editable:
```
pip install --upgrade pip
pip install -e .
```
Install build requirements:
```
pip install black flake8 twine build pytest
```
Run upload:
```
make upload
```
