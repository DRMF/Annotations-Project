AnnotationsProject
==================

This project is meant to expedite the process of finding annotations
(i.e. constraints, substitutions, etc) in TeX source files.

##Usage

The program should be run as follows:

    python find_annotations.py sourcefile iofile

Where:

* `sourcefile` is a file containing the TeX source you wish to process
* `iofile` is a file that will be both read from and written to over
the course of the program, and can be blank/nonexistant the first
time the program is run
