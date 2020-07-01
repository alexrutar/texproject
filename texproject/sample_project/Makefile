.PHONY: export citation

SOURCE?=main

export:
	zip sample_project.zip *.bib *.tex *.pdf *.sty

citation:
	rm citations.bib
	ln -s ~/.texproject/resources/citations/$(SOURCE).bib citations.bib