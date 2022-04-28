class Asdgen():
    def  __init__(self):
       self.counter = 1
       
    def generate(self):
        payload = 'asd' * self.counter
        self.counter += 1
        return payload

def getGenerator():
    return Asdgen()
    