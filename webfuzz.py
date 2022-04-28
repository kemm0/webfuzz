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

class Fields(Enum):
    EXEC_PATH = "exec-path"
    EXEC = "exec"
    URL = "url"
    METHOD = "method"
    SAMPLE_INPUT = "sample-input"
    HEADERS = "headers"
    BODY = "body"


FUZZLIST_REGEX = re.compile('\[[fF][lL] .* [0-9]+ [0-9]+]')
FUZZGEN_REGEX = re.compile('\[[fF][gG] .* [0-9]+ [0-9]+]')

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


def pipe_reader(f, buffer):
    while True:
        line = f.readline()
        if line:
            buffer.append(line)
        else:
            break

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
    with urllib.request.urlopen(req) as res:
        return res


def readCase(filename):
    try:
        f = open(filename, 'r')
        testcase = f.read()
        f.close()
        return testcase
    except FileNotFoundError as e:
        print(e)


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
            "rounds": int(x[2]),
            "hierarchy": int(x[3]),
            "tag": tag
        }

    for tag in fuzzgen_tags:
        tag_content = tag[1:-1]
        x = tag_content.split()
        fuzzgens[tag] = {
            "filename": x[1],
            "rounds": int(x[2]),
            "hierarchy": int(x[3]),
            "tag": tag
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


def processFiles():
    filenames = sys.argv[2:]
    for filename in filenames:
        testcase_txt = readCase(filename)
        testcase_dict = json.loads(testcase_txt)
        exec_path = testcase_dict["exec-path"]
        exec_args = testcase_dict["exec"]
        print("original file")
        print(testcase_txt)
        fuzzlists, fuzzgens = processTags(testcase_txt)
        fuzzlists = getWordLists(fuzzlists)
        fuzzgens = getGenerators(fuzzgens)

        modifiers = dict(fuzzlists)
        modifiers.update(fuzzgens)

        errbuffer = []
        outbuffer = []

        server = open_server(exec_args, exec_path, testcase_dict["url"], 100)

        if(server == None):
            print("could not open server")
            exit()

        error_reader = Thread(target=pipe_reader, args=(server.stderr, errbuffer))
        out_reader = Thread(target=pipe_reader, args=(server.stdout, outbuffer))

        error_reader.daemon = True
        error_reader.start()

        out_reader.daemon = True
        out_reader.start()

        # modify the original test case
        for i in range(0, 4):
            modified_testcase = testcase_txt
            for key in modifiers:
                modified_testcase = modified_testcase.replace(
                    key, modifiers[key]["generator"].generate())
            print('------------------------')
            print('Testcase {num} payload: '.format(num=i))
            print(modified_testcase)
            try:
                create_request(json.loads(modified_testcase))
            except urllib.error.HTTPError as e:
                if(e.code >= 500):
                    print("Internal server error detected. Code: " +
                        e.code + " Message: " + e.reason)
                    print("Tested input body: ")
                    print(body)
                else:
                    print("Server responded with bad request. Code: " +
                            str(e.code) + " Message: " + e.reason)
            except urllib.error.URLError as e:
                print("Malformed url or server error: " + url)
                server.kill()
                open_server(exec_args, exec_path, testcase_dict["url"], 100)
            except http.client.HTTPException as e:
                print("HTTP exception")
                server.kill()
                open_server(exec_args, exec_path, testcase_dict["url"], 100)
            print('Error buffer: ')
            print(errbuffer)
            print(outbuffer)
            print('------------------------')
        server.kill()


modes = {
    "-h": printHelp,
    "--help": printHelp,
    "-f": processFiles,
    "--file": processFiles
}

if __name__ == '__main__':
    mode = sys.argv[1]
    modes[mode]()
