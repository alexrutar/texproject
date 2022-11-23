# TexProject: An automatic LaTeX project manager.
TexPRoject is a command-line LaTeX template and project manager written in Python.

# Introduction
## Installation
On UNIX-like systems, typically one can install the command-line tool with the following commands:
```sh
pip install texproject
git clone https://github.com/alexrutar/texproject-templates ~/.local/share/texproject
```
Texproject complies with the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html); replace `~/.local/share` or `~/.config` with your configured directories.
Currently, there is no installation script or package manager support, but I hope to implement this eventually.

To configure Texproject, you can generate a global configuration file in the directory `~/.config/texproject/` by running
```sh
mkdir -p ~/.config/texproject
tpr util show-config > ~/.config/texproject/config.toml
```

## Basic Usage
Texproject is installed under the command line tool `tpr`.
To create a new project, create an empty directory, change into it, and run
```sh
tpr init <template>
```
This command will create a new project using the template with name `<template>` in the current directory.
To specify a different directory, use the `-C <path>` flag.
This creates the files `main.tex` (for primary document contents) and `project-macros.sty` (for project-specific macros).
To get a list of available templates, run
```sh
tpr list template
```
If you are currently in a project file, run
```sh
tpr archive <output.zip>
```
to create compressed source files for your project in the same directory.

If you want to edit parameters of your document (such as citation files, additional macro sets, or other features), run
```sh
tpr template edit
```
to open the project template file in your `$EDITOR`.
When the file is closed, the project is automatically updated.
Note that this will not overwrite existing linked files.

If you want to overwrite existing files, the `tpr import` function may be useful.
For instance, to update the `tikz` macro file, you would run
```sh
tpr import --macro tikz
```
This subcommand can also be used to import files not in the template repository.
If you have a citation file `/path/to/citation.bib`, run
```sh
tpr import --citation-path path/to/new/file.bib
```
You can then include this file by adding `file` to the `citations` section of the project configuration file.
You can also programmatically add new imports as well: in the above example, run
```sh
tpr template add --macro tikz
```

Read about more features by running
```sh
tpr --help
tpr <subcommand> --help
```

# Other Major Features
## Automatic Compilation
A number of subcommands used by Texproject use the [latexmk](https://personal.psu.edu/~jcc8/software/latexmk/) program for automatic compilation.
This is useful in order to programmatically verify compilation, as well as automatic creation of `.pdf` or `.bbl` files from source files when exporting.
For example, to create a compressed export with includes a `.pdf` of the current build, run
```sh
tpr archive output.zip --mode build
```
Run `tpr validate --help` or `tpr archive --help` for more information on some subcommands which use automatic compilation.

## GitHub Repository Management
Texproject also has an automated tool that is useful for setting up a remote a repository on [GitHub](https://github.com) with convenient continuous integration features.
In order to use these features, [git](https://git-scm.com/), along with the [GitHub CLI](https://cli.github.com/), must be installed and properly authenticated.

> **_WARNING:_** The commands in this section will create and modify repositories and continuous integration on your GitHub account.

In a new project without an initialized `.git` repo, run the command
```sh
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
```sh
echo "% a comment" >> main.tex
git commit --a m "A nice commit message"
```
Then, create a tag and push the commit along with the tag:
```sh
git tag v1.0 -m "First release!"
git push --follow-tags
```
Now, after the action has finished running, the compiled files will be visible at the URL `https://github.com/username/reponame/releases`.

### Automatic commits to a centralized repository
The action can also be configured to automatically push the compiled `.pdf` releases to a centralized GitHub repository.
For example, you might want to automatically add release files to your personal website every time the files are updated.

In order to set this up, add a `[github]` table to your system configuration (`tpr config --global`).
The keys
```toml
[github]
username = "johndoe"
email = "jdoe@email.com"
```
specify the name and email used to sign the automated commits made on your behalf, and the keys
```toml
[github.archive]
repo = 'johndoe/paper_archive'
folder = 'pdfs'
branch = 'main'
```
specify the target repository, folder, and branch where the commits will be pushed.

If you want to specify the archive on a per-repository basis, instead run `tpr config --local` and add the `[github.archive]` file there.

In order to correctly authenticate, the repository must have access to a [valid API token](https://github.com/settings/tokens).
This token must have, at least, (and preferably at most), repo privileges on your GitHub account.
This can be specified in one of two ways.
The first option is to use the [https://pypi.org/project/keyring/](keyring) package, which is automatically installed upon installation of Texproject.
Add your token to the keyring:
```sh
keyring set <github_cli_token> <name>
```
Then, add the table
```toml
[github.keyring]
username = '<name>'
entry = '<github_cli_token>'
```
to your configuration.

You can also set the `API_TOKEN_GITHUB` environment variable; this has priority over the keyring option.

When these settings are in place, running `tpr git init` will automatically add this action, as well as the API token, to your GitHub repository.
In order to upgrade an existing project to include this feature, you can also run
```sh
tpr git init-archive
```

# Usage Examples
## Basic project initialization
Here, we demonstrate the construction of a basic project.
First, create a project with the name `example` using the `empty` template, and change into the directory.
```sh
mkdir example && cd example
tpr init empty
```
The relevant project files in this directory are `main.tex` and `project-macros.sty`.
The file `main.tex` file is the main document file which you can edit to produce your document.
The `project-macros.sty` file is an empty package in which you can input custom project-dependent preamble.
These packages are always loaded after any specified project files.

Suppose we want to include the macro set `general` with our project: to do this, run
```sh
tpr template add --macro general
```
If you want to share this project with someone else, simply run
```sh
tpr archive output.zip
```
which will generate the file `output.zip` within the project directory.
This zipfile contains all the source files required to compile the document.
