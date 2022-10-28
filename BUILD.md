# Building, Testing, and Distributing
## Initial setup
First, update the virtual environment with the appropriate version:
```
pyenv virtualenv uninstall texproject-venv
pyenv virtualenv 3.10.7 texproject-venv
```
Next, install locally as editable:
```
pip install --upgrade pip
pip install -e .
```
Install some convenient requirements:
```
pip install black flake8 pyright pytest
```
Note that `pyright` is only required by linting for your editor.

## Testing and formatting
All testing is run by the [Makefile](Makefile).
- Run quick testing with `pytest`
- Run slow testing with `make test`
- Reformat using black with `make format`

## Distribution
Install build requirements:
```
pip install twine build
```
Run upload:
```
make upload
```
