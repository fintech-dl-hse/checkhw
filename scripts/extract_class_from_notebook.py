
import sys
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--notebook', type=str, required=True)
parser.add_argument('--class_definition', type=str, required=True)
parser.add_argument('--out_filename', type=str, required=True)

args = parser.parse_args()

NOTEBOOK_FILE = args.notebook
CLASS_DEFENITION = args.class_definition
FILE_NAME = args.out_filename

print("Looking for class definition", CLASS_DEFENITION, "in notebook", NOTEBOOK_FILE)

with open(NOTEBOOK_FILE, 'r') as f:
    notebook = json.load(f)

    for cell in notebook['cells']:
        if cell['cell_type'] == "code":
            cell_code = "".join(cell['source'])
            if CLASS_DEFENITION in cell_code:
                print("Found!:\n", cell_code)
                with open(FILE_NAME, 'w') as class_file:
                    class_file.write(cell_code)
                    sys.exit(0)

print("Class definition was not found in notebook")
sys.exit(1)

