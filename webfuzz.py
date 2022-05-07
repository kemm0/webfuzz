import random
import sys
import urllib.request
import urllib.parse
import urllib.error
import json
from enum import Enum
import string
import re
import os
import importlib
import subprocess
from threading import Thread
import time
import http.client
import itertools
from venv import create
from colorama import Fore
from colorama import Style
from fcntl import fcntl, F_GETFL, F_SETFL
from os import O_NONBLOCK


class Fields(Enum):
    EXEC_PATH = "exec-path"
    EXEC = "exec"
    URL = "url"
    METHOD = "method"
    SAMPLE_INPUT = "sample-input"
    HEADERS = "headers"
    BODY = "body"


FUZZLIST_REGEX = re.compile('\[[fF][lL] .* [0-9]+]')
FUZZGEN_REGEX = re.compile('\[[fF][gG] .* [0-9]+]')

# not needed?
class Mutator():
    def __init__(self, template, symbol, generator):
        self.template = template
        self.symbol = symbol
        self.generator = generator

    def get_output(self):
        return self.template.replace(self.symbol, self.generator.generate())

# a stateful word list that returns the next word of the list with the generate() -function
class WordList():
    def __init__(self, words):
        self.counter = 0
        self.words = words

    def generate(self):
        next_word = self.words[self.counter]
        if(self.counter < len(self.words) - 1):
            self.counter += 1
        return next_word


def printHelp():
    print("usage: webfuzz.py [-h] [-f FILE]")
    print("-h:, --help : show this help message")
    print("-f FILE : filename to process")


def create_request(testcase):
    # init values
    url = testcase[Fields.URL.value]
    method = testcase[Fields.METHOD.value]
    headers = testcase[Fields.HEADERS.value]
    body = testcase[Fields.BODY.value]

    data = json.dumps(body)
    data = data.encode('utf-8')

    req = urllib.request.Request(url, data=data, method=method)

    for header in headers:
       req.add_header(header, headers[header])
    res = ""
    with urllib.request.urlopen(req) as f:
        res = f.read().decode('utf-8')
    return res


def readCase(filename):
    f = open(filename, 'r')
    testcase = f.read()
    f.close()
    return testcase


# find tags in the text file and extract information about filename, rounds of execution, execution hierarchy from the tags
def processTags(raw_text):
    fuzzlist_tags = FUZZLIST_REGEX.findall(raw_text)
    fuzzgen_tags = FUZZGEN_REGEX.findall(raw_text)

    fuzzlists = {}
    fuzzgens = {}

    for tag in fuzzlist_tags:
        tag_content = tag[1:-1]
        x = tag_content.split()
        fuzzlists[tag] = {
            "filename": x[1],
            "rounds": int(x[2])
        }

    for tag in fuzzgen_tags:
        tag_content = tag[1:-1]
        x = tag_content.split()
        fuzzgens[tag] = {
            "filename": x[1],
            "rounds": int(x[2])
        }
    return fuzzlists, fuzzgens

# import generator modules from generators and add them to the fuzzgens dictionary under each corresponding tag
def getGenerators(fuzzgens):
    gen_filenames = []
    for key in fuzzgens:
        gen_filenames.append(fuzzgens[key]["filename"])
    genfiles = os.listdir("generators")
    for key in fuzzgens:
        if (fuzzgens[key]["filename"] + ".py") in genfiles:
            module = importlib.import_module(
                "generators" + '.' + fuzzgens[key]["filename"])
            fuzzgens[key]["generator"] = module.getGenerator()
    return fuzzgens

# create word list -objects from text files and add the objects to the fuzzlists dict under each corresponding tag
def getWordLists(fuzzlists):
    for key in fuzzlists:
        filename = fuzzlists[key]["filename"]
        wordlist = []
        try:
            with open(os.path.join("lists", (filename + ".txt"))) as file:
                for line in file:
                    wordlist.append(line.rstrip())
            fuzzlists[key]["generator"] = WordList(wordlist)
        except FileNotFoundError as e:
            print(e)
    return fuzzlists


def open_server(args, path, url, timeout):
    try:
        server = subprocess.Popen(
            args=args, cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        flags_output = fcntl(server.stdout, F_GETFL) # get current p.stdout flags
        fcntl(server.stdout, F_SETFL, flags_output | O_NONBLOCK) #Python file reading is blocking while waiting for data by default. Here we set it to non-blocking (Since server might not always output data)

        flags_err = fcntl(server.stdout, F_GETFL) # get current p.stderr flags
        fcntl(server.stderr, F_SETFL, flags_err | O_NONBLOCK)

    except Exception as e:
        print("Could not execute command + " + args)

    # check if server is up
    server_running = False
    iterations = 0
    while not server_running:
        if(iterations >= timeout):
            server.kill()
            return None
        try:
            urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            server_running = True
        except urllib.error.URLError as e:
            time.sleep(0.1)
        iterations += 1
    return server

def create_cli_report(filename, test_results):
    print('----------------------------------------')
    print('File {f}:'.format(f=filename))
    for i in range(0, len(test_results)):
        test_result = test_results[i]
        print('------------------')
        print('{color}Testcase {i}'.format(color=Fore.YELLOW, i=i))
        print('{color}Catched: {i}{reset_color}'.format(color=Fore.RED, i=test_result['catched'], reset_color=Style.RESET_ALL))
        print('Request:')
        print(test_result['testcase'])
        if(len(test_result['server_errors']) > 0):
            print('\n{color}Server errors ({i}):{reset_color}'.format(color=Fore.RED, i=len(test_result['server_errors']), reset_color=Style.RESET_ALL))
            for err in test_result['server_errors']:
                print(err)
        if(len(test_result['network_errors']) > 0):
            print('\n{color}Network errors ({i}):{reset_color}'.format(color=Fore.RED, i=len(test_result['network_errors']), reset_color=Style.RESET_ALL))
            for err in test_result['network_errors']:
                print("Error type: " + type(err).__name__)
                print("Error message: " + str(err))
        if(len(test_result['codes_catched']) > 0):
            print('\n{color}Catched HTTP codes ({i}):{reset_color}'.format(color=Fore.LIGHTRED_EX, i=len(test_result['codes_catched']), reset_color=Style.RESET_ALL))
            for err in test_result['codes_catched']:
                print("HTTP code: " + str(err.code))
                print("Error message: " + str(err))
        if(len(test_result['response_catches']) > 0):
            print('\n{color}Catched keywords in HTTP response: {words}{reset_color}'.format(color=Fore.CYAN, words=', '.join(test_result['response_catches']), reset_color=Style.RESET_ALL))
            print('Response:')
            print('"{r}"'.format(r=test_result['response']))
        if(len(test_result['output_catches']) > 0):
            print('\n{color}Catched keywords in server output: {words}{reset_color}'.format(color=Fore.LIGHTMAGENTA_EX, words=', '.join(test_result['output_catches']), reset_color=Style.RESET_ALL))
            print('Server output:')
            print(test_result['output_catches'])
        


def check_http_code(code, codes_to_catch):
    if(codes_to_catch == None):
        return False
    for c in codes_to_catch:
        if(type(c) == list):
            if(code >= c[0] and code <= c[1]):
                return True
        elif(type(c) == int):
            if(code == c):
                return True
    return False

def regex_search_string(input, keywords):
    if(keywords == None):
        return []
    found_words = []
    for word in keywords:
        word_regex = re.compile(word)
        if(word_regex.search(input) != None):
            found_words.append(word)
    return found_words



def processFiles():
    filenames = sys.argv[2:]

    for filename in filenames:
        # Read test case parameters from text file
        try:
            testcase_txt = readCase(filename)
            testcase_dict = json.loads(testcase_txt)
        except:
            print('Invalid file: {f}.'.format(f=filename))
            exit()
        exec_path = testcase_dict["exec-path"]
        exec_args = testcase_dict["exec"]
        catch = testcase_dict.get('catch') if testcase_dict.get('catch') != None else {}
        catch_codes = catch.get('codes')
        catch_response = catch.get('response')
        catch_output = catch.get('output')

        fuzzlists, fuzzgens = processTags(testcase_txt)
        fuzzlists = getWordLists(fuzzlists)
        fuzzgens = getGenerators(fuzzgens)

        modifiers = dict(fuzzlists)
        modifiers.update(fuzzgens)

        mutations = []
        for key in modifiers:
            gen_values = []
            modifier = modifiers[key]
            for round in range(0, modifier['rounds']):
                gen_values.append((key, modifier['generator'].generate()))
            mutations.append(gen_values)

        print(mutations)
        #create permutations for each field to mutate, these will be the combinations that will be tested
        permutations = list(itertools.product(*mutations))

        #create server subprocess for monitoring
        server = open_server(exec_args, exec_path, testcase_dict["url"], 100)

        if(server == None):
            print("could not open server")
            exit()
        
        test_results = []
        
        #Make the requests and capture interesting output
        for combination in permutations:
            case_report = {}
            mod_txt = testcase_txt
            for elem in combination:
                mod_txt = mod_txt.replace(elem[0], elem[1])
            testcase = json.loads(mod_txt)
            case_report['testcase'] = mod_txt
            case_report['network_errors'] = []
            case_report['server_errors'] = []
            case_report['response_catches'] = []
            case_report['output_catches'] = []
            case_report['codes_catched'] = []
            case_report['catched'] = 0
            try:
                res = create_request(testcase)
                search_results = regex_search_string(res, catch_response)
                if(len(search_results) != 0):
                    case_report['response'] = res
                    case_report['response_catches'] = search_results
                    case_report['catched'] += 1

            except urllib.error.HTTPError as e: #Some HTML error code. Might want to catch certain codes.
                if(check_http_code(e.code, catch_codes)):
                    case_report['codes_catched'].append(e)
                    case_report['catched'] += 1
            except urllib.error.URLError as e: #Malformed URL or server not responding
                #print("UrlError")
                case_report['network_errors'].append(e)
                case_report['catched'] += 1
            except http.client.RemoteDisconnected as e: #Server stopped connection
                #print("HTTP client HTTPException: " + type(e).__name__)
                case_report['network_errors'].append(e)
                case_report['catched'] += 1

            if(catch_output != None):
                output_lines_arr = server.stdout.readlines()
                if(len(output_lines_arr) > 0):
                    output_lines = ''.join(output_lines_arr)
                    output_results = regex_search_string(output_lines, catch_output)
                    if(len(output_results) != 0):
                        case_report['output_catches'] = output_results
                        case_report['catched'] += 1

            err_lines_arr = server.stderr.readlines()
            if(len(err_lines_arr) > 0):
                err_lines = ''.join(err_lines_arr)
                case_report['server_errors'].append(err_lines)
                case_report['catched'] += 1
                server.kill()
                server = open_server(exec_args, exec_path, testcase_dict["url"], 100)
                if(server == None):
                    print("could not open server")
                    exit()
            
            if(case_report['catched'] > 0):
                test_results.append(case_report)
        server.kill()
        create_cli_report(filename, test_results)
                
                




modes = {
    "-h": printHelp,
    "--help": printHelp,
    "-f": processFiles,
    "--file": processFiles
}

if __name__ == '__main__':
    mode = sys.argv[1]
    modes[mode]()
