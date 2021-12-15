# TexProject: An automatic LaTeX project manager.
TexPRoject is a command-line LaTeX template and project manager written in Python.

# Introduction
## Installation
On UNIX-like systems, typically one can install the command-line tool with the following commands:
```
pip install texproject
git clone https://github.com/alexrutar/texproject-templates ~/.local/share/texproject
mkdir -p ~/.config/texproject
cp ~/.local/share/texproject/config/user_config_example.toml ~/.config/texproject/user.toml
cp ~/.local/share/texproject/config/system_config_example.toml ~/.config/texproject/system.toml
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
tpr list template
```
If you are currently in a project file, run
```
tpr archive <output.zip>
```
to create compressed source files for your project in the same directory.

If you want to edit parameters of your document (such as citation files, additional macro sets, or other features), run
```
tpr config
```
to open a project configuration file in your `$EDITOR`.
When the file is closed, the project is automatically updated.
For project backwards compatibility, this will not overwrite existing linked files.

If you want to overwrite existing files, the `tpr import` function may be useful.
For instance, to update the `tikz` macro file, you would run
```
tpr import --macro tikz
```
This subcommand can also be used to import files not in the template repository.
For example, if you have a citation file `/path/to/citation.bib`, run
```
tpr import --path --citation /path/to/new/file.bib
```
You can then include this file by adding `file` to the `citations` section of the project configuration file.

Read about more features by running
```
tpr --help
tpr <subcommand> --help
```
This is the canonical source of documentation for the program.

## Usage Example
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
Run `tpr config` to open the project configuration file, and replace the line `macros = []` with the line
```
macros = ['general']
```
Save and close the file: the new macros are automatically added to your project file.
If you want to share this project with someone else, simply run
```
tpr archive output.zip
```
which will generate the file `output.zip` within the project directory.
This zipfile contains all the source files requires to compile the document.

# Other Major Features
## Automatic Compilation
A number of subcommands used by Texproject use the [latexmk](https://personal.psu.edu/~jcc8/software/latexmk/) program for automatic compilation.
This is useful in order to programmatically verify compilation, as well as automatic creation of `.pdf` or `.bbl` files from source files when exporting.
For example, to create a compressed export with includes a `.pdf` of the current build, run
```
tpr archive output.zip --include build
```
Run `tpr validate --help` or `tpr archive --help` for more information on some subcommands which use automatic compilation.

## GitHub Repository Management
Texproject also has an automated tool that is useful for setting up a remote a repository on [GitHub](https://github.com) with convenient continuous integration features.
In order to use these features, [git](https://git-scm.com/), along with the [GitHub CLI](https://cli.github.com/), must be installed and properly authenticated.

> **_WARNING:_** The commands in this section will create and modify repositories and continuous integration on your GitHub account.

In a new project without an initialized `.git` repo, run the command
```
tpr git init
```
to begin an interactive session to set up a new git repo with a remote on GitHub.
This command does the following:

1. Initializes a new git repository in the working directory.
2. Adds the relevant files, and creates a first commit.
3. Creates a new GitHub remote, with parameters as specified during the interactive prompt.
4. Sets a repository secret `API_TOKEN_GITHUB`, which is used by some of the CI features.

In order to see the commands which will be run without executing them, use `tpr -n git init`.

### Automatic releases
This GitHub repository is initialized with a custom action (see `.github/workflows/build_latex.yml`) which automatically creates GitHub releases for tagged versions on your project.
For example, suppose you make some changes to your `.tex` file and commit them to your repository:
```
echo "% a comment" >> main.tex
git add main.tex
git commit -m "A nice commit message"
```
Then, create a tag and push the commit along with the tag:
```
git tag v1.0 -m "First release!"
git push --follow-tags
```
Now, after the action has finished running, the compiled files will be visible at the URL `https://github.com/username/reponame/releases`.

### Automatic commits to a centralized repository
The action can also be configured to automatically push the compiled `.pdf` releases to a centralized GitHub repository.
For example, you might want to automatically add release files to your personal website every time the files are updated.

In order to set this up, add a `[github]` table to your system configuration (`tpr config --system`).
The keys
```
[github]
username = "johnd"
email = "john@email.com"
```
specify the name and email used to sign the automated commits made on your behalf, and the keys
```
[github.archive]
repo = 'paper_archive'
folder = 'pdfs'
branch = 'main'
```
specify the target repository, folder, and branch where the commits will be pushed.

In order to correctly authenticate, the repository must have access to a valid API token.
This token must have, at least, (and preferably at most), repo privileges on your GitHub account.
This can be specified in one of two ways.
The first option is to use the [https://pypi.org/project/keyring/](keyring) package, which is automatically installed upon installation of Texproject.
Add your token to the keyring:
```
keyring set <github_cli_token> <name>
```
Then, add the table
```
[github.keyring]
username = '<name>'
entry = '<github_cli_token>'
```
to your Texproject system configuration.
Of course, `<name>` and `<github_cli_token>` can be whatever you want.
You can also set the `API_TOKEN_GITHUB` environment variable.

When these settings are in place, running `tpr git init` will automatically add this action, as well as the API token, to your GitHub repository.
In order to upgrade an existing project to include this feature, you can also run
```
tpr git set-archive
```

## Custom Configuration
There are three types of configuration files associated with the `tpr` command.
Variables within these configuration file are accessible from within templates: see below for more details.
All configuration files are formatted using [TOML](https://toml.io/en/).

### Local Configuration
This is the per-project configuration file: with an appropriate working directory, access with `tpr config` or `tpr config --local`.
This configuration file specifies the build settings for the current project.
Here are the keys relevant to local modification:

- `doctype`: the document class
- `class_options`: a list of options to pass to the document class
- `geometry`: a list of key-value options to pass to the geometry package
- `macros`: a list of macro files to import (order is preserved)
- `citations`: a list of citation files to import
- `format`: the format file (general appearance)

All variables are accessible using the `local` dictionary within templates.

### User Configuration
This configuration file specifies information about the user, and can be accessed with `tpr config --user`.
All variables are accessible using the `user` dictionary within templates.
See the [example user configuration file](https://github.com/alexrutar/texproject-templates/blob/master/config/system_config_example.toml) for more details.

### System Configuration
This configuration file controls many aspects of the behaviour of `tpr`, and can be accessed with `tpr config --system`.
All variables are accessible using the `config` dictionary within templates.
See the [example system configuration file](https://github.com/alexrutar/texproject-templates/blob/master/config/system_config_example.toml) for more details.
