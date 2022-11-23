# Building, Testing, and Distributing
## Initial setup
First, update the virtual environment with the appropriate version:
```sh
pyenv virtualenv uninstall texproject-venv
pyenv virtualenv 3.11.0 texproject-venv
```
Next, install locally as editable:
```sh
pip install --upgrade pip
pip install -e .
```
Install some convenient requirements:
```sh
pip install black flake8 pyright pytest mypy
```

## Testing and formatting
All testing is run by the [Makefile](Makefile).
- Run quick testing with `pytest`
- Run slow testing with `make test`
- Reformat using black with `make format`

## Distribution
Install build requirements:
```sh
pip install twine build
```
Run upload:
```sh
make upload
```
