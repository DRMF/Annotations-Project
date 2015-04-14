# Annotations-Project

This project is meant to expedite the process of finding annotations
(i.e. constraints, substitutions, etc) in TeX source files.

##Usage

The program should be run as follows:

    python find_annotations.py inputfile ouputfile

Where:

* `inputfile` is a file containing the TeX source you wish to process
* `outputfile` is the file to write the processed TeX to

> **NOTE:**
>
> `outputfile` will only be written to if the entire input file is
> processed to completion. Otherwise, the output will be written to
> the `.save` file.
