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
Texproject is installed under the command line tool `tpr`.
To create a new project, run
```
tpr new <template> <projectname>
```
This command will create a new project using the template with name `<template>` in the `<projectname>` directory.
To get a list of available templates, run
```
tpr info --list T
```
If you are currently in a project file, run
```
tpr export
```
to create an exported version of your project, with frozen (unlinked) packages.
Read about other features by running
```
tpr info --help
```

### Usage Example
Here, we demonstrate the construction of a basic project.
First, create a project with the name `example` using the `empty` template, and change into the directory.
```
tpr new empty example
cd example
```
The relevant project files in this directory are `example.tex` and `project-macros.sty`.
The file `example.tex` file is the main document file which you can edit to produce your document.
The `project-macros.sty` file is an empty package in which you can input custom project-dependent preamble.
These packages are always loaded after any specified project files.

The project also contains the specification file `.tpr_link_info`, which contains descriptions of the linked citation and macro files (as specified during project creation or in the template).
Suppose we want to include the macro set `general` with our project.
Add the line
```
    - general
```
beneath the line starting with `macros:` in `.tpr_link_info`, and run
```
tpr refresh
```
to regenerate the links.
To include this package, simply add
```
\usepackage{macros-general}
```
to your preamble.
(TODO: this will probably change to auto-generate this update).
If you want to share this project with someone else, simply run
```
tpr export
```
which will generate the file `example.zip` within the project directory.
This zipfile contains all the important project files, as well as frozen versions of the dynamic macro files.

##
