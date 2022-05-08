import sys
import urllib.request
import urllib.parse
import urllib.error
import json
from enum import Enum
import re
import os
import importlib
import subprocess
import time
import http.client
import itertools
from colorama import Fore
from colorama import Style
from fcntl import fcntl, F_GETFL, F_SETFL
from os import O_NONBLOCK
from datetime import datetime


class Fields(Enum):
    EXEC_PATH = "exec-path"
    EXEC = "exec"
    URL = "url"
    METHOD = "method"
    SAMPLE_INPUT = "sample-input"
    HEADERS = "headers"
    BODY = "body"
    REQUEST = "request"
    CATCH = "catch"
    CODES = "codes"
    RESPONSE = "response"
    OUTPUT = "output"

class TestResult():
    def __init__(self, request):
        self.request = request
        self.catched_total = 0
        self.network_errors = []
        self.response_catches = []
        self.output_catches = []
        self.code_catched = ''
        self.server_out = ''
        self.server_err = ''
        self.response = ''

class Report():
    def __init__(self, filename):
        self.filename = filename
        self.catched_total = 0
        self.network_errors = 0
        self.server_errors = 0
        self.response_catches = 0
        self.output_catches = 0
        self.codes_catched = 0
        self.__test_results = []
    
    def addResult(self, test_result):
        self.catched_total += test_result.catched_total
        self.network_errors += len(test_result.network_errors)
        self.response_catches += len(test_result.response_catches)
        self.output_catches += len(test_result.output_catches)
        if(test_result.code_catched != ''):
            self.codes_catched += 1
        if(test_result.server_err != ''):
            self.server_errors += 1
        self.__test_results.append(test_result)

    def getResults(self):
        return self.__test_results

    def __catches_by_type(self):
        catches_by_type = [
        f'Total Catches: {self.catched_total}', 
        f'Network errors: {self.network_errors}', 
        f'Server errors: {self.server_errors}', 
        f'Response keywords: {self.response_catches}', 
        f'Server output keywords: {self.output_catches}', 
        f'HTTP Codes catched: {self.codes_catched}'
        ]
        return catches_by_type

    def get_cli_report(self):
        cli_report = []

        def addLine(line, color = None):
            if(color == None):
                cli_report.append(line + '\n')
            else:
                cli_report.append(f'{color}{line}{Style.RESET_ALL} \n')

        current_time = datetime.now().astimezone()
        addLine('******************************************')
        addLine(f'File: {self.filename}')
        addLine(', '.join(self.__catches_by_type()), Fore.RED)
        addLine(f'Generated on {current_time.strftime("%d %B %Y, %H:%M %Z")}')
        addLine('******************************************')

        for i in range(0, len(self.__test_results)):
            test_result = self.__test_results[i]
            addLine('------------------')
            addLine(f'{i}', Fore.YELLOW)
            addLine(f'Catched: {test_result.catched_total} \n', Fore.RED)
            addLine('Request: \n')
            addLine(json.dumps(test_result.request, indent=4))

            if(test_result.server_err != ''):
                addLine(f'Server error output (stderr): \n', Fore.RED)
                addLine(test_result.server_err)

            if(len(test_result.network_errors) > 0):
                addLine(f'Network errors ({len(test_result.network_errors)}): \n', Fore.RED)
                for err in test_result.network_errors:
                    addLine("Error type: " + type(err).__name__)
                    addLine("Error message: " + str(err))

            if(test_result.code_catched != ''):
                addLine(f'Catched HTTP code: {test_result.code_catched}')

            if(len(test_result.response_catches) > 0):
                addLine(f'Catched keywords in HTTP response: {", ".join(test_result.response_catches)} \n')
                addLine('Response: \n', Fore.BLUE)
                addLine(f'{test_result.response}')

            if(len(test_result.output_catches) > 0):
                addLine(f'Catched keywords in server output (stdout): {", ".join(test_result.output_catches)}')
                addLine('Server output: \n')
                addLine(test_result.server_out, Fore.BLUE)

        return ''.join(cli_report)

    def get_html_report(self):

        def createHTMLTag(content, elem='p', classname='', sanitize=False):
            class_attr = ''
            if(classname != ''):
                class_attr = f'class="{classname}"'
            if(sanitize):
                content = html_encode(content)
            tag = f'<{elem} {class_attr}>{content}</{elem}>'
            return tag
        
        report_html_content = []
        testcases_html_content = []

        for i in range(0, len(self.__test_results)):
            
            test_result = self.__test_results[i]
            panel_body = []
            request = html_encode(json.dumps(test_result.request, indent=4))
            if(test_result.server_err != ''):
                panel_body.append(createHTMLTag('Server error output (stderr):', 'b'))
                panel_body.append(createHTMLTag(content=test_result.server_err, elem='pre', sanitize=True))
            if(len(test_result.network_errors) > 0):
                panel_body.append(createHTMLTag('Network errors:', 'b'))
                for err in test_result.network_errors:
                    panel_body.append(createHTMLTag(content=f'Error type: {type(err).__name__}', elem='pre'))
                    panel_body.append(createHTMLTag(content=f'Error message: {str(err)}', elem='pre', sanitize=True))
            if(test_result.code_catched != ''):
                panel_body.append(createHTMLTag(content='Code catched in HTTP response:', elem='b'))
                panel_body.append(createHTMLTag(content=f'{test_result.code_catched}', elem='p'))
            if(len(test_result.response_catches) > 0):
                panel_body.append(createHTMLTag(content=f'Catched keywords in HTTP response:', elem='b'))
                panel_body.append(createHTMLTag(content=", ".join(test_result.response_catches), elem='p', sanitize=True))
                panel_body.append(createHTMLTag('Response:', 'b'))
                panel_body.append(createHTMLTag(content=test_result.response, elem='pre', sanitize=True))
            if(len(test_result.output_catches) > 0):
                panel_body.append(createHTMLTag(content='Catched keywords in Server output (stdout):', elem='b'))
                panel_body.append(createHTMLTag(content=", ".join(test_result.output_catches), elem='p', sanitize=True))
                panel_body.append(createHTMLTag(content='Server output:', elem='b'))
                panel_body.append(createHTMLTag(content=test_result.server_out, elem='pre', sanitize=True))
            
            panel_body = ''.join(panel_body)
            result_html = f'''
            <div class="panel panel-default">
                <div class="panel-heading">
                    <h4 class="panel-title">
                        <a data-toggle="collapse" href="#collapse{i}">&#8226 {i} (Catched: {test_result.catched_total})</a>
                    </h4>
                </div>
                <div id="collapse{i}" class="panel-collapse collapse">
                    <div class="panel-body">
                        <b>Request:</b>
                        <pre>{request}</pre>
                        <div>
                            {panel_body}
                        </div>
                    </div>
                </div>
            </div>
            '''
            testcases_html_content.append(result_html)

        testcases_html_content = ''.join(testcases_html_content)

        total_catches_by_type = self.__catches_by_type()
        current_time = datetime.now().astimezone()
        report_html_template = f'''
        <h1>Webfuzzer Report</h1>
        <p>File: {self.filename} </p>
        <p>{", ".join(total_catches_by_type)}</p>'
        <p>{'Generated on {t}'.format(t=current_time.strftime("%d %B %Y, %H:%M %Z"))}</p>
        <div class="panel-group">
            {testcases_html_content}
        </div>
        '''
        report_html_content.append(report_html_template)

        page_html_content = f'''
            <!doctype html>
            <html lang="en">
            <head>
                <!-- Required meta tags -->
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

                <!-- Bootstrap CSS -->
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.3.1/dist/css/bootstrap.min.css" integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous">

                <title>Hello, world!</title>
            </head>
            <body>
                <div class="container">
                    {''.join(report_html_content)}
                </div>
                <!-- Optional JavaScript -->
                <!-- jQuery first, then Popper.js, then Bootstrap JS -->
                <script src="https://code.jquery.com/jquery-3.3.1.slim.min.js" integrity="sha384-q8i/X+965DzO0rT7abK41JStQIAqVgRVzpbzo5smXKp4YfRvH+8abtTE1Pi6jizo" crossorigin="anonymous"></script>
                <script src="https://cdn.jsdelivr.net/npm/popper.js@1.14.7/dist/umd/popper.min.js" integrity="sha384-UO2eT0CpHqdSJQ6hJty5KVphtPhzWj9WO1clHTMGa3JDZwrnQq4sF86dIHNDz0W1" crossorigin="anonymous"></script>
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.3.1/dist/js/bootstrap.min.js" integrity="sha384-JjSmVgyd0p3pXB1rRibZUAYoIIy6OrQ6VrjIEaFf/nJGzIxFDsf4x0xIM+B07jRM" crossorigin="anonymous"></script>
            </body>
            </html>
        '''
        return page_html_content
        

class Mutator():
    def __init__(self, type, filename, rounds):
        self.type = type
        self.filename = filename
        self.rounds = rounds 
        try:
            if(type == 'FL'):
                file_folder = 'lists'
                file_ending = '.txt'
                wordlist = []
                with open(os.path.join(file_folder, (filename + file_ending))) as file:
                    for line in file:
                        wordlist.append(line.rstrip())
                self.generator = WordList(wordlist)
            else:
                file_folder = 'generators'
                file_ending = '.py'
                genfiles = os.listdir(file_folder)
                if (filename + ".py") in genfiles:
                    module = importlib.import_module(file_folder + '.' + filename)
                    self.generator = module.getGenerator()
        except FileNotFoundError as e:
            print(e)

# Returns the next word of the list with the generate() -function
class WordList():
    def __init__(self, words):
        self.counter = 0
        self.words = words

    def generate(self):
        next_word = self.words[self.counter]
        if(self.counter < len(self.words) - 1):
            self.counter += 1
        else:
            self.counter = 0
        return next_word

FUZZLIST_REGEX = re.compile('\[[fF][lL] .* [0-9]+]')
FUZZGEN_REGEX = re.compile('\[[fF][gG] .* [0-9]+]')

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

    all_tags = fuzzlist_tags + fuzzgen_tags

    return all_tags

# import create Mutator objects from parameters
def getMutators(tags):
    mutators = {}
    for tag in tags:
        tag_elements = tag[1:-1].split(' ')
        m_type = tag_elements[0]
        m_filename = tag_elements[1]
        m_rounds = int(tag_elements[2])
        new_mutator = Mutator(m_type, m_filename, m_rounds)
        mutators[tag] = new_mutator

    return mutators



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

def html_encode(line):
    raw = ['&', '<', '>', '"', "'"]
    encoded = ['&amp', '&lt', '&gt', '&quot', '&#x27']
    for i in range(0, len(raw)):
        line = line.replace(raw[i],encoded[i])
    return line

def fuzz(filename, testcase, permutations):

    exec_path = testcase[Fields.EXEC_PATH.value]
    exec_args = testcase[Fields.EXEC.value]
    catch = testcase.get(Fields.CATCH.value) if testcase.get(Fields.CATCH.value) != None else {}
    catch_codes = catch.get(Fields.CODES.value)
    catch_response_keywords = catch.get(Fields.RESPONSE.value)
    catch_output_keywords = catch.get(Fields.OUTPUT.value)

    #create server subprocess for monitoring
    server = open_server(exec_args, exec_path, testcase[Fields.REQUEST.value][Fields.URL.value], 100)

    if(server == None):
        print("could not open server")
        exit()

    report = Report(filename)
    #Make the requests and capture interesting output
    for combination in permutations:
        mod_request = json.dumps(testcase[Fields.REQUEST.value])
        for elem in combination:
            mod_request = mod_request.replace(elem[0], elem[1])
        mod_request_json = json.loads(mod_request)
        test_result = TestResult(mod_request_json)
        try:
            res = create_request(mod_request_json)
            search_results = regex_search_string(res, catch_response_keywords)
            if(len(search_results) != 0):
                test_result.response = res
                test_result.response_catches = search_results
                test_result.catched_total += 1

        except urllib.error.HTTPError as e: #Some HTML error code. Might want to catch certain codes.
            if(check_http_code(e.code, catch_codes)):
                test_result.code_catched = str(e.code)
                test_result.catched_total += 1

        except (urllib.error.URLError, http.client.RemoteDisconnected) as e: #Malformed URL or server not responding
            test_result.network_errors.append(e)
            test_result.catched_total += 1

        if(catch_output_keywords != None):
            output_arr = server.stdout.readlines()
            if(len(output_arr) > 0):
                output = ''.join(output_arr)
                output_results = regex_search_string(output, catch_output_keywords)
                if(len(output_results) != 0):
                    test_result.output_catches = output_results
                    test_result.server_out = output
                    test_result.catched_total += 1

        error_arr = server.stderr.readlines()
        if(len(error_arr) > 0):
            error_output = ''.join(error_arr)
            test_result.server_err = error_output
            test_result.catched_total += 1
            server.kill()
            server = open_server(exec_args, exec_path, testcase[Fields.REQUEST.value][Fields.URL.value], 100)
            if(server == None):
                print("could not open server")
                exit()
        
        if(test_result.catched_total > 0):
            report.addResult(test_result)
    server.kill()
    return report

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

        tags = processTags(testcase_txt)
        mutators = getMutators(tags)

        mutations = []
        for key in mutators:
            values = []
            mutator = mutators[key]
            for round in range(0, mutator.rounds):
                values.append((key, mutator.generator.generate()))
            mutations.append(values)
        
        #create permutations for each field to mutate, these will be the combinations that will be tested
        permutations = list(itertools.product(*mutations))

        report = fuzz(filename, testcase_dict, permutations)
        print(report.get_cli_report())
        report_html = report.get_html_report()
        f = open("webfuzzer-report.html", "w")
        f.write(report_html)
        f.close()
                
                




modes = {
    "-h": printHelp,
    "--help": printHelp,
    "-f": processFiles,
    "--file": processFiles
}

if __name__ == '__main__':
    mode = sys.argv[1]
    modes[mode]()
