"""
Prints all lines in the file that contain words which
indicate that the line may contain an annotation.
"""

import re
import sys
import os
from collections import namedtuple, OrderedDict

from utilities import (readin, writeout, get_input, get_last_line)

#default name for the progress file
PROGRESS_FILE = ".bookmark"

#default name for the save file
SAVE_FILE = ".save"

#remap input and range functions for python 3
if int(sys.version[0]) >= 3:
    raw_input = input
    xrange = range

#class to represent the user's response to an annotation query
InputResponse = namedtuple("InputResponse", "type annotation equations")

def main():

    if len(sys.argv) != 3:

        print("Usage: {0} <inputfile> <outputfile>".format(sys.argv[0]))
        sys.exit(-1)

    else:

        fname = sys.argv[1]
        ofname = sys.argv[2]   

    options = {"resume": False, "append": False, "start": 0, "offset": 0}

    #if file does not exist, no endline
    try:
        endline = get_last_line(PROGRESS_FILE)
    except IOError:
        endline = "" 
    
    #if last line is a number, give user option to resume or start over
    try:

        start_line = int(endline.strip())

        print("Existing file ends at sentence #{0}".format(start_line))
        options = get_options()

        options["start"] = start_line

    except ValueError:
        pass

    #user wants to start over 
    if not options["resume"]:
        options["start"] = 0

    in_tex = readin(fname)

    #read in from save file if resuming
    if options["resume"]:

        #read in from save file if it exists
        try:
            in_tex = readin(SAVE_FILE)
        except IOError:
            print("NO SAVE FILE PRESENT - STARTING OVER")
            options["resume"] = False
    
    output = find_annotations(in_tex, **options)

    #only write out if we haven't already done so (user didn't quit)
    if output is not None:
        writeout(ofname, output)
 
def find_annotations(content, **options):
    """
    Finds possible annotations in the text and puts them in equations.

    For each possible annotation, prompts the user for input on whether
    it is actually an annotation, and (if it is one) on its properties.
    Returns an updated version of content.
    """
    
    indicators = [
        "When", 
        "Where", 
        "If", 
        "Then", 
        "For", 
        "With", 
        "As", 
        "Throughout", 
        "In"
    ]

    indicators.extend([indicator.lower() for indicator in indicators])

    sentence_pat = re.compile(r'([^.!?\s][^.!?]*(?:[.!?](?!\s|$)[^.!?]*)*[.!?]?(?=\s|$))', re.DOTALL)
 
    label_pat = re.compile(r'\\(?:label|eqref){(?P<eq_id>eq:.*?)}')
    eq_range_pat = re.compile(r'\\eqref{(?P<start>eq:(?P<main_name>.*?\..*?\..*?).+?)}\s*--\s*\\eqref{(?P<end>eq:.*?)}')
    definition_pat = re.compile(r'\$(?P<var_name>.)\$ defined by \\eqref{(?P<eq_id>.*?)}')

    responses = OrderedDict()

    doc_start = content.find("\\begin{document}") + len(r'\begin{document}')
    
    every_sentence = list(sentence_pat.finditer(content[doc_start:]))
    num_sentences = len(every_sentence)

    start = 0

    #set offset and start
    if options["resume"]:
        start = options["start"]    

    #go through each sentence
    #LOOPSTART
    for snum, sentence_match in enumerate(every_sentence):

        #don't start till we get to starting point
        if snum < start:
            continue

        assoc_equations = []
        annotation_lines = []

        sentence = sentence_match.group()

        before = ""

        #this isn't the first sentence, get the previous sentence
        if snum != 0:
            before = every_sentence[snum - 1].group()

        after = ""

        #this isn't the last sentence, get the next sentence
        if snum != num_sentences - 1:
            after = every_sentence[snum + 1].group()

        sentence = sentence.strip()
        sentence = re.sub(r'\n{2,}', r'\n', sentence)

        sectioning = "" 

        #see if the section or subsection is referenced
        if "this subsection" in sentence:
            sectioning = "subsection"
        if "this section" in sentence:
            sectioning = "section"
        if "this chapter" in sentence:
            sectioning = "chapter"

        #either the seciton or subsection was referenced
        if sectioning:

            before = ""
            sentence = sentence[sentence.find("\\" + sectioning):]

            line_ind = snum + 2

            #keep adding sentences to after
            while (line_ind < num_sentences
                and ("\\" + sectioning) not in after):

                after = ''.join([after, every_sentence[line_ind].group()])
                line_ind += 1

            to_join = []

            after_lines = after.split("\n")
            line_ind = 0
            current = after_lines[line_ind] 
 
            #keep adding lines until the start of the next section
            while (("\\" + sectioning) not in current
                and line_ind + 1 < len(after_lines)):

                to_join.append(current)

                line_ind += 1
                current = after_lines[line_ind] 

            to_join.append(current)
            
            after = '\n'.join(to_join)

        found_range = False

        #include ranges of equations if they are referenced
        for match in eq_range_pat.finditer(sentence):
  
            found_range = True

            current = snum + 2
            start_id = match.group("start")
            end_id = match.group("end")
            main_name = match.group("main_name")
            
            #keep adding to after until we have the whole range
            while (current < num_sentences
                and r'\label{' + end_id + '}' not in after):

                to_add = every_sentence[current].group()

                #only add if it has a relevant equation in it
                if r'\label{' in to_add:

                    if main_name not in to_add:
                        to_add = ""

                after = ''.join([after, to_add])

                current += 1

            before = ""
            start_loc = sentence.find(r'\begin{equation}\label{' + start_id + '}')

            #first equation is in this sentence
            if start_loc != -1:
                sentence = sentence[start_loc:]
            else:
                start_loc = after.find(r'\begin{equation}\label{' + start_id + '}')

        #found an equation range, cut out after after last end equaiton
        if found_range:
            after = after[:after.rfind(r'\end{equation}') + len(r'\end{equation}')]

        #if variable is defined by an equation, replace eqref with text
        for match in definition_pat.finditer(sentence):

            eq_id = match.group("eq_id")
            eq_pat = re.compile(r'\\begin{equation}\\label{' + eq_id + r'}.*?\n(?P<content>.*?)\n?\\end{equation}', re.DOTALL)

            search_text = before
            eq_match = eq_pat.search(search_text)

            current = snum - 2

            #keep looking backward until we have a match
            while not eq_match and current > 0:

                search_text = ''.join([every_sentence[current].group(), search_text])
                eq_match = eq_pat.search(search_text) 
                current -= 1
                
            #make sure we found something
            if eq_match:
                sentence = sentence.replace(r'\eqref{' + eq_id + '}', eq_match.group("content").strip().rstrip("."))

        context = before + "\n" + sentence + "\n" + after

        #find the equation ids of all the equations that may be associated with this annotation
        for label_match in label_pat.finditer(context):
            assoc_equations.append(label_match.group("eq_id"))

        #take out the eq labels from the range if they exist
        if found_range:
            assoc_equations = assoc_equations[2:]

        seen = set()
        indicator_found = False

        #go through each indicator
        for indicator in indicators:

            #go through each line in the sentence so we can print out the one with the indicator 
            for line in sentence.split("\n"):

                #store each line that may contain an annotation
                if (line not in seen
                    and (" " + indicator + " " in line)
                    or (indicator + " " in line and line.startswith(indicator))
                    or (" " + indicator + ". " in line)):

                    annotation_lines.append("{0}: {1}".format(indicator, line.lstrip()))
                    indicator_found = True
                    seen.add(line)

        #don't do anything else if there aren't any indicators in the sentence
        if not indicator_found:
            continue

        #ask user about each possible annotation
        for line in annotation_lines:

            to_write = "{0}{1}".format(_create_comment_string(responses), snum)
            result = _check_and_quit(make_annotation_query(line, context, assoc_equations), to_write, content, options)

            #map each InputResponse to the sentence number
            for response in result:
                responses[response] = snum

        begin_loc = sentence_match.start() + doc_start
        end_loc = sentence_match.end() + doc_start

        #if an equation is in the sentence, only remove until there
        if r'\begin{equation}' in sentence:
            end_loc = content.find(r'\begin{equation}', begin_loc, end_loc)

        should_delete = get_input("Would you like to delete this sentence (fragment):\nSTART\n{0}\nEND\n(y/n)".format(content[begin_loc:end_loc]), valid=set("ynq"), wait=False)

        #user wants to quit
        if should_delete == "q":
            to_write = "{0}{1}".format(_create_comment_string(responses), snum)
            _quick_exit(to_write, content, options)

        should_delete = should_delete == "y"

        #we need to delete the sentence (at least up to the first equation)
        if should_delete:

            content = content[:begin_loc] + "~~~~REM_START~~~~" + content[begin_loc:end_loc] + "~~~~REM_END~~~~" + content[end_loc:]

        #shouldn't delete sentence, ask about keywords
        else:

            should_add_word = get_input("Would you like to add a keyword? (y/n)", valid=set("yn"), wait=False)

            #user wants to quit
            if should_add_word == "q":
                to_write = "{0}{1}".format(_create_comment_string(responses), snum)
                _quick_exit(to_write, content, options)

            should_add_word = should_add_word == "y"
            
            #user wants to add a keyword
            if should_add_word: 

                new_keyword = get_input("Enter the new keyword:")

                indicators.append(new_keyword)
                indicators.append(new_keyword.title())

            store_current = get_input("Would you like to store an annotation on this line? (y/n)", valid=set("yn"), wait=False)

            #user wants to quit
            if store_current == "q":
                to_write = "{0}{1}".format(_create_comment_string(responses), snum)
                _quick_exit(to_write, content, options)

            store_current = store_current == "y"

            #user wants to store an annotation on this line
            if store_current:

                to_write = "{0}{1}".format(_create_comment_string(responses), snum)
                result = _check_and_quit(make_annotation_query("", context, assoc_equations), to_write, content, options)

                #map each InputResponse to its sentence number
                for response in result:
                    responses[response] = snum

    #LOOPEND

    comment_str = _create_comment_string(responses)
    content = comment_str + content

    comment_insertion_pat = re.compile(r'^(?:\d+:)?{(?P<eq_id>.*?)}% *\\(?P<name>.*?){(?P<annotation>.*?)}(?P<between>.*?)(?P<equation>\\begin{equation}\\label{(?P=eq_id)}.*?\\end{equation})', re.DOTALL)

    #as long as there is a match in content, keep replacing
    while comment_insertion_pat.search(content):
        content = comment_insertion_pat.sub(_insert_comment, content)
        content = content[1:]   #take out empty line

    #equation_fixer_pat = re.compile(r'\\begin{equation}(?P<before>.*?)(?P<comment>\n%.*?\n)(?P<after>[^%].+?\n)\\end{equation}', re.DOTALL)
    #content = equation_fixer_pat.sub(r'\\begin{equation}\g<before>\g<after>\g<comment>\\end{equation}', content)
    removal_pat = re.compile(r'~~~~REM_START~~~~.*?~~~~REM_END~~~~', re.DOTALL)
    content = removal_pat.sub('', content)

    removal_fix_pat = re.compile(r'(\s*)~~~~REM_START~~~~(.*?)\n(\s*)\\end{equation}')
    content = removal_fix_pat.sub(r'\1\2\n\3\\end{equation}', content)

    save_state(comment_str, content, options)

    #delete the save file when we're done
    try:
        os.remove(SAVE_FILE)
    except OSError:
        print(("THE SAVE FILE COULD NOT BE REMOVED. PLEASE REMOVE IT "
               "MANUALLY WITH rm .save"))

    print("DONE")

    return content

#checks if the user wants to quit, and does so if necessary
def _check_and_quit(response, progress, save, options):

    if _is_quit(response):
        _quick_exit(progress, save, options)

    return response

#exits the program after saving the necessary files
def _quick_exit(progress, save, options):

    print("-" * 35 + "QUITTING" + "-" * 35 + "\n")

    save_state(progress, save, options)

    sys.exit(0)

def save_state(progress, save, options):
    """
    Save program state into files specified by
    PROGRESS_FILE and SAVE_FILE.
    """

    writeout(PROGRESS_FILE, progress, options["append"])
    writeout(SAVE_FILE, save)

#checks if the user want to quit and takes appropriate action if they do
def _is_quit(result):
    return "QUIT" in result

#returns the "comment_str" to be written given the responses list
def _create_comment_string(responses):

    #take out the empty elements
    if () in responses:
        del responses[()]

    comment_str = ""

    #add comment line for every response at the beginning of the file  
    for response in responses:

        seq_num = responses[response]
        comment_str = ''.join([comment_str, input_to_comment(response, seq_num)])

    return comment_str

#inserts the matched comment into the matched equation right before the \\end{equation}
def _insert_comment(match):

    equation = match.group("equation")
    eq_lines = equation.split("\n")

    leading_whitespace = len(eq_lines[1]) - len(eq_lines[1].lstrip())

    comment = "%" + " " * leading_whitespace + "\\{name}{{{annotation}}}".format(name=match.group("name"), annotation=match.group("annotation"))

    eq_lines[-1:-1] = [comment]
    equation = "\n".join(eq_lines)

    return "{between}{equation}".format(between=match.group("between"), equation=equation) 

def make_annotation_query(line, context, assoc_eqs):
    """
    Queries the user for information about the possible annotation.

    Will ask the user a series of questions about the annotation
    and returns an InputResponse tuple containing the result
    of the query. If the annotation was incorrectly identified
    (i.e. it is not an annotation) an empty tuple will be returned.
    """

    to_join = context.split("\n")

    #place -----> marker in front of vital line
    for num, l in enumerate(to_join):
        if l.strip() and l == line[line.find(": ") + 2:]:
            to_join[num] = "----->" + l

    context = "\n".join(to_join)

    yes_no_responses = set(["y", "n", "yes", "no"])

    print("\n----------------------------------------\nIdentified the following:")
    print(line) 

    print("")
    
    print("In the context of:")
    print(context)
    print("----------------------------------------\n")

    valid_check = get_input("Is this an annotation? (y/n or q to quit):", yes_no_responses, wait=False)

    #quit if the user types q
    if valid_check == "q":
        return ["QUIT"]

    #not actually an annotation, return empty
    if valid_check == "n" or valid_check == "no":
        return [()]

    to_return = []

    num_annotations = get_input("Enter the number of annotations on the line (1-9):", set(["1","2","3","4","4","5","6","7","8","9"]), wait=False)

    #user wants to quit
    if num_annotations == "q":
        return ["QUIT"]

    num_annotations = int(num_annotations)

    #create however many annotations there are
    for i in range(num_annotations):

        annotation_type = get_input("Enter the type of annotation: (c)onstraint, (s)ubstitution), (n)ote, na(m)e, (p)roof:", set(["c", "s", "n", "m", "p"]), wait=False)

        #quit if user presses q
        if annotation_type == "q":
            return ["QUIT"]    

        annotation = get_input("Enter the actual text of the annotation:")

        print("\nThe predicted associated equations are:") 
    
        #print out the equation label of each associated equation
        for eq in assoc_eqs:
            print("\t{0}".format(eq))

        correct_eqs = get_input("Are these correct? (y/n):", yes_no_responses, wait=False)

        #if the equations are incorrect, find out if we need to add equations or remove them
        while correct_eqs != "y" or len(assoc_eqs) == 0:

            #quit if the user types q
            if correct_eqs == "q":
                return ["QUIT"]
 
            add_remove = get_input("Would you like to add, remove, or select equations?: (a)dd/(r)emove/(s)elect:", set(["a", "r", "s"]), wait=False)

            #quit if user presses q
            if add_remove == "q":
                return ["QUIT"]    

            #inform user that they need an equation with the annotation
            if len(assoc_eqs) == 0:
                print("Must have at least one associated equation.")
                add_remove = "a"
            
            #display adding menu
            if add_remove == "a":

                eq_label = get_input("Enter the label for the equation you would like to add:", preserve_case=True)
                assoc_eqs.append(eq_label) 
                print("Equation added")

            #display removal menu
            if add_remove == "r":

                #user can't remove equations if there aren't any
                if len(assoc_eqs) == 0:

                    print("There are no equations to remove")

                else:

                    _print_eqs(assoc_eqs)

                    to_remove = get_input("What equation(s) would you like to remove (separate with commas):", set(map(str, xrange(len(assoc_eqs) + 1))), list=True)
                    to_remove = _parse_list(to_remove)

                    #remove each equation in reverse
                    for rem_ind in sorted(to_remove, reverse=True):
                        del assoc_eqs[rem_ind]

                    print("Equation(s) removed")

            #display selection menu
            if add_remove == "s":
            
                #can't select if there are no equations
                if len(assoc_eqs) == 0:

                    print("There are no equaitons to select")

                else:
             
                    _print_eqs(assoc_eqs)

                    to_select = get_input("What equation(s) would you like to select (separate with commas):", set(map(str, xrange(len(assoc_eqs) + 1))), list=True)
                    to_select = _parse_list(to_select)

                    assoc_eqs[:] = [eq for i, eq in enumerate(assoc_eqs) if i in to_select]

                    print("Equation(s) selected")

            print("The predicted associated equations are:") 

            #print out the equation label of each associated equation
            for eq in assoc_eqs:
                print("\t{0}".format(eq))

            correct_eqs = get_input("Are these correct? (y/n):", yes_no_responses, wait=False)

        print("Annotation added\n---------------------------------------------")
        to_return.append(InputResponse(annotation_type, annotation, frozenset(assoc_eqs)))

    return to_return

def input_to_comment(response, snum):
    """
    Takes `InputResponse` and sequence number and returns appropriate comment.

    The comment will be placed in the relevant equations.

    Example:::

        Given:
        
        t = 'c'
        a = '$\\realpart{\\rho} > 0$'
        e = set(['eq:ZE.EX.PR2'])
        
        response = InputResponse(type=t, annotation=a, equations=e) 
        
        input_to_comment(response, 5)

        Returns:

        5:{eq:ZE.EX.PR2}%  \\constraint{$\\realpart{\\rho} > 0$}

        Given:

        t = 'c'
        a = '$\\realpart{\\rho} > 0$'
        e = set(['eq:ZE.EX.PR2', 'eq:ZE.EX.PR3'])
        
        response = InputResponse(type=t, annotation=a, equations=e)

        input_to_comment(response, 10)

        Returns:

        10:{eq:ZE.EX.PR2}%  \\constraint{$\\realpart{\\rho} > 0$}
        {eq:ZE.EX.PR3}%  \\constraint{$\\realpart{\\rho} > 0$}

    """

    type_dict = {
        "c": "constraint",
        "s": "substitution",
        "m": "drmfname",
        "n": "drmfnote",
        "p": "proof"
    }

    comment_str = "{0}:".format(snum)

    #create a new comment line for each equation
    for equation in response.equations: 
        comment_str += "{{{equation}}}% \\{type}{{{annotation}}}\n".format(type=type_dict[response.type], annotation=response.annotation, equation=equation)

    return comment_str

def get_options():
    """
    Returns a dictionary of options necessary for the program.
    """
 
    options = {}

    should_resume = get_input("Would you like to resume from where you left off or start over?: (r)esume/(s)tart over:", set(["r", "s"]), wait=False)
    
    should_resume = should_resume == "r"
    should_append = should_resume
   
    options["resume"] = should_resume
    options["append"] = should_append

    return options

#parses a comma separated list (string) into a python list
def _parse_list(list_str):

    #no comma, treat as single number
    if "," not in list_str:
        list_str = [int(list_str.strip())]
    else:
        list_str = map(int, list_str.replace(" ", "").split(","))

    return list_str

#ennumerates the equations (prints each with an assocaited number)
def _print_eqs(eq_container):

    #print each equation
    for index, eq in enumerate(eq_container):
        print("{0}: {1}".format(index, eq))

if __name__ == "__main__":
    main()
