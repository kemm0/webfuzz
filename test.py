import os
import importlib
import string
import json

gens = {}

muts = {
    "template": "http://localhost:3001/[f_PATH 10 1]",
    "symbol": "[f_PATH 10 1]",
    "generator": ""
}


class Mutator():
    def __init__(self, template, symbol, generator):
        self.template = template
        self.symbol = symbol
        self.generator = generator

    def get_output(self):
        return self.template.replace(self.symbol, self.generator.generate())

def mutate_dict(d, mutations):
    for k,v in d.items():
        if isinstance(v, dict):
            mutate_dict(v, mutations)
        elif isinstance(v, str):
            if v in mutations.keys():
                d[k] = mutations[v].get_output()


#for name in os.listdir("generators"):
#    if name.endswith(".py"):
#        # strip the extension
#        module_name = name[:-3]
#        if(module_name == '__init__'):
#            continue
#        # set the module name in the current global name space:
#        module = importlib.import_module("generators" + '.' + module_name)
#        gens.append(module)

if __name__ == '__main__':
    #gen = gens[0].getGenerator()

    sample_input = {
        "exec-path": "/home/kemm0/Opinnot/secure-programming/example-server",
        "exec": ["node", "index.js"],
        "url": "http://localhost:3001/[g_testgen3 10 1]",
        "method": "POST",
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    }

    sample_input = json.dumps(sample_input)

    base = "http://localhost:3001/[g_testgen3 10 1]"
    symbol = "[g_testgen3 10 1]"
    gen_name = "testgen3"

    for name in os.listdir("generators"):
        if name == (gen_name + ".py"):
            # strip the extension
            module_name = name[:-3]
            # set the module name in the current global name space:
            module = importlib.import_module("generators" + '.' + module_name)
            gens[module_name] = module
    
    mutator = Mutator(base, symbol, gens[gen_name].getGenerator())

    mutations = {
        "http://localhost:3001/[g_testgen3 10 1]": mutator
    }

    #mutate_dict(sample_input, mutations)
    for key in mutations:
        sample_input = sample_input.replace(key, mutations[key].get_output())
        #print(mutations[key].get_output())
    print(sample_input)
