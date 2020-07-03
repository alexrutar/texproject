#  def check_errors(self):
#  pass
# TODO errors to check:
#  - template yaml file has all required components
#  - all the macro files exist
#  - all the formatting files exist

#  - tpr update: pull new source files from github
# info file: macros, citations, template
# issue note to add new lines to tex file / remove lines?
# could regen file (and put old file in archive)?



# TODO: argument parsing, script creation, and packaging on pypi
# TODO: bibliography management
# - argument in .yaml file specifying bibliography style
#   - if this argument exists
#     - generate bibliography code within the latex automatically at the end
#     - always create a citations.bib file (see bib source below)
#     - create Makefile citation management argument
#   - if this argument does not exist, do not create any of the above
# - command line argument specifying the bibliography source
#   - if this argument exists, link the citation source
#   - if this argument does not exist, create an empty citations.bib file
#   - if the argument exists but does yield something correct, warn and create an empty citations.bib file

# TODO: maybe include a python script to do project management? (instead of makefile)
#   - this would have to be a global script that can detect local params ... or a local copy of the script
#   - or maybe generate some .tpr_project_info file? that lets you specify the values directly
#     - then can run some global script to rebuild the corresponding pieces
# - see Path.unlink and shutil.make_archive

# TODO: migrate other template files to new templater

# installation script?

