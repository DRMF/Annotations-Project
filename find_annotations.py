"""
Prints all lines in the file that contain words which
indicate that the line may contain an annotation.
"""

import re
import sys
from collections import namedtuple, OrderedDict

from utilities import (readin, writeout, get_input, get_last_line)

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

    options = {"resume": False, "append": False}

    start_point = 0

    #if file does not exist, no endline
    try:
        endline = get_last_line(ofname)
    except IOError as ie:
        endline = "" 
    
    #if last line is a number, give user option to resume or start over
    try:
        start_point = int(endline.strip())

        print("Existing file ends at sentence #{0}".format(start_point))
        options = get_options()

    except ValueError:
        pass

    #user wants to start over 
    if not options["resume"]:
        start_point = 0
    
    output = find_annotations(readin(fname), ofname, start_point, **options)

    #only write out if we haven't already done so (user didn't quit)
    if output:
        writeout(ofname, output, options["append"])
 
def find_annotations(content, out_deck, start, **options):
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

    doc_start = content.find("\\begin{document}")
    
    every_sentence = sentence_pat.findall(content[doc_start:])
    #print(len(every_sentence))
    #sys.exit(0)

    #go through each sentence
    for snum, sentence in enumerate(every_sentence):

        #don't start till we get to starting point
        if snum < start:
            continue

        assoc_equations = []
        annotation_lines = []

        before = ""

        #this isn't the first sentence, get the previous sentence
        if snum != 0:
            before = every_sentence[snum - 1]

        after = ""

        #this isn't the last sentence, get the next sentence
        if snum != len(every_sentence) - 1:
            after = every_sentence[snum + 1]

        sentence = sentence.strip()
        sentence = re.sub(r'\n{2,}', r'\n', sentence)

        #take out lines that start with \index
        sentence = "\n".join(line for line in sentence.split("\n") if not line.lstrip().startswith("\\index"))

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

            current = snum + 2

            #keep adding sentences to after
            while (current < len(every_sentence)
                and ("\\" + sectioning) not in after):

                after = ''.join([after, every_sentence[current]])
                current += 1

            to_join = []

            after_lines = after.split("\n")
            line_ind = 0
            current = after_lines[line_ind] 
 
            #keep adding lines until the start of the next section
            while ("\\" + sectioning) not in current:
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
            while (current < len(every_sentence)
                and r'\label{' + end_id + '}' not in after):

                to_add = every_sentence[current]

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

                search_text = ''.join([every_sentence[current], search_text])
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
                    seen.add(line)

        #ask user about each possible annotation
        for line in annotation_lines:

            result = make_annotation_query(line, context, assoc_equations)

            #user wants to quit, write out file and exit
            if "QUIT" in result:

                print("-" * 40 + "QUITTING" + "-" * 40 + "\n")

                to_write = "{0}{1}".format(_create_comment_string(responses), snum)

                writeout(out_deck, to_write, append=options["append"])
                return ""

            #map each InputResponse to the sentence number
            for response in result:
                responses[response] = snum

    comment_str = _create_comment_string(responses)
    content = comment_str + content

    comment_insertion_pat = re.compile(r'^% *\\(?P<name>.*?){(?P<annotation>.*?)}~~~~(?P<eq_id>.*?)~~~~(?P<between>.*?)(?P<equation>\\begin{equation}\\label{(?P=eq_id)}.*?\\end{equation})', re.DOTALL)

    #as long as there is a match in content, keep replacing
#    while comment_insertion_pat.search(content):
#        content = comment_insertion_pat.sub(_insert_comment, content)
#        content = content[1:]   #take out empty line

    #equation_fixer_pat = re.compile(r'\\begin{equation}(?P<before>.*?)(?P<comment>\n%.*?\n)(?P<after>[^%].+?\n)\\end{equation}', re.DOTALL)
    #content = equation_fixer_pat.sub(r'\\begin{equation}\g<before>\g<after>\g<comment>\\end{equation}', content)

    print("DONE")

    return comment_str

#returns the "comment_str" to be written given the responses list
def _create_comment_string(responses):

    #take out the empty elements
    if () in responses:
        del responses[()]

    comment_str = ""

    #add comment line for every response at the beginning of the file  
    for response in responses:

        seq_num = responses[response]
        comment_str = ''.join(set([comment_str, input_to_comment(response, seq_num)]))

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
    num_annotations = int(num_annotations)

    #create however many annotations there are
    for i in range(num_annotations):

        type = get_input("Enter the type of annotation: (c)onstraint, (s)ubstitution), (n)ote, na(m)e, (p)roof:", set(["c", "s", "n", "m", "p"]), wait=False)
    
        annotation = get_input("Enter the actual text of the annotation:")

        print("\nThe predicted associated equations are:") 
    
        #print out the equation label of each associated equation
        for eq in assoc_eqs:
            print("\t{0}".format(eq))

        correct_eqs = get_input("Are these correct? (y/n):", yes_no_responses, wait=False)

        #quit if the user types q
        if correct_eqs == "q":
            return ["QUIT"]
 
        #if the equations are incorrect, find out if we need to add equations or remove them
        while correct_eqs == "n" or correct_eqs == "no" or len(assoc_eqs) == 0:

            add_remove = get_input("Would you like to add, remove, or select equations?: (a)dd/(r)emove/(s)elect:", set(["a", "r", "s"]), wait=False)

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
        to_return.append(InputResponse(type, annotation, frozenset(assoc_eqs)))

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

