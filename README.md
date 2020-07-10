# TexProject: An automatic LaTeX project manager.
TexProject is a LaTeX template and project manager written in Python.

## Installation
On UNIX-like systems, typically one can install the command-line tool with the following commands:
```
pip install texproject
git clone https://github.com/alexrutar/texproject-templates ~/.local/share/texproject
mkdir -p ~/.config/texproject
cp ~/.local/share/texproject/config/user_config_example.yaml ~/.config/texproject/config.yaml
```
Texproject complies with the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html); replace `~/.local/share` or `~/.config` with your configured directories.
Currently, there is no installation script or package manager support, but I hope to implement this eventually.

## Basic Usage
Texproject is installed under the command line tool `tpr`.
To create a new project, create an empty directory, change into it, and run
```
tpr init <template>
```
This command will create a new project using the template with name `<template>` in the current directory.
To specify a different directory, use the `-C <path>` flag.
This creates the files `main.tex` (for primary document contents) and `project-macros.sty` (for project-specific macros).
To get a list of available templates, run
```
tpr info --list T
```
If you are currently in a project file, run
```
tpr export
```
to create an exported version of your project, with frozen (unlinked) packages.

If you want to edit parameters of your document (such as citation files, additional macro sets, or other features), run
```
tpr config
```
to open a project configuration file in your `$EDITOR`.
Once you are finished, run `tpr refresh` to reflect the changes in the support files.

Read about more features by running
```
tpr info --help
```

### Usage Example
Here, we demonstrate the construction of a basic project.
First, create a project with the name `example` using the `empty` template, and change into the directory.
```
mkdir example; cd example
tpr init empty
```
The relevant project files in this directory are `main.tex` and `project-macros.sty`.
The file `main.tex` file is the main document file which you can edit to produce your document.
The `project-macros.sty` file is an empty package in which you can input custom project-dependent preamble.
These packages are always loaded after any specified project files.

Suppose we want to include the macro set `general` with our project.
Run `tpr config` to open the project configuration file, and add the line
```
- general
```
beneath the line starting with `macros:`.
Save the file, and run
```
tpr refresh
```
to regenerate the links and support files.
The new macros are automatically added to your project file.
If you want to share this project with someone else, simply run
```
tpr export
```
which will generate the file `example.zip` within the project directory.
This zipfile contains all the important project files, as well as frozen versions of the dynamic macro files.
