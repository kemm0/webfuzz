import string
import random

def mutate_size(input, amount):
    return input + ''.join(random.choices(input, k=amount))

def rand_ascii_numbers_string(length):
    return ''.join(random.choices(string.ascii_lowercase,string.ascii_uppercase,string.digits, k=length))

def rand_specialchars_string(length):
    return ''.join(random.choices(string.printable, k=length))