# TexProject: An automatic LaTeX project manager.
TexProject is a LaTeX template and project manager written in Python.

## Installation
On UNIX-like systems, typically one can install the command-line tool with the following commands:
```
pip install texproject
git clone https://github.com/alexrutar/texproject-templates ~/.local/share/texproject
cp ~/.local/share/texproject/config/tpr_config.yaml ~/.config/texproject/tpr_config.yaml
```
Texproject complies with the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html); replace `~/.local/share` or `~/.config` with your configured directories.
Currently, there is no installation script or package manager support, but I hope to implement this eventually.

## Basic Usage

