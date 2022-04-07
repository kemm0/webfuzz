import random
import sys
import urllib.request
import urllib.parse
import urllib.error
import json
from enum import Enum
import string
import mutators

class Fields(Enum):
    URL = "url"
    METHOD = "method"
    SAMPLE_INPUT = "sample-input"
    HEADERS = "headers"
    BODY = "body"

def printHelp():
    print("usage: webfuzz.py [-h] [-f FILE]")
    print("-h:, --help : show this help message")
    print("-f FILE : filename to process")

def fuzz(testcase):
    #init values
    url = testcase[Fields.URL.value]
    method = testcase[Fields.METHOD.value]
    sample_input = testcase[Fields.SAMPLE_INPUT.value]
    headers = sample_input[Fields.HEADERS.value]
    body = sample_input[Fields.BODY.value]

    field_num = 0

    while True:
        field_name = list(body.keys())[field_num]
        body[field_name] = mutators.mutate_size(body[field_name], 100)

        data = json.dumps(body)
        data = data.encode('utf-8')

        req = urllib.request.Request(url, data=data, method=method)
        
        for header in headers:
            req.add_header(header, headers[header])
        try:
            with urllib.request.urlopen(req) as res:
                print(res.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if(e.code >= 500):
                print("Internal server error detected. Code: " + e.code + " Message: " + e.reason)
                print("Tested input body: ")
                print(body)
                exit()
            else:
                print("Server responded with bad request. Code: " + str(e.code) + " Message: " + e.reason)
        except urllib.error.URLError as e:
            print("Malformed url or server not running: " + url)
            exit()
    

def readCase(filename):
    try:
        f = open(filename, 'r')
        testcase = f.read()
        testcase = json.loads(testcase)
        fuzz(testcase)
        f.close()
    except FileNotFoundError as e:
        print(e)

def processFiles():
    filenames = sys.argv[2:]
    for filename in filenames:
        readCase(filename)



modes = {
    "-h": printHelp,
    "--help": printHelp,
    "-f" : processFiles,
    "--file": processFiles
}

if __name__ == '__main__':
    mode = sys.argv[1]
    modes[mode]()

