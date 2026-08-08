"""Start the frontend dev server with the correct cwd."""
import os
import sys
import subprocess

os.chdir("c:/Users/amrsa/Downloads/veriscope/landing-page")

process = subprocess.Popen(
    ["npm", "run", "dev"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    shell=True,
)

with open("frontend_output.log", "w", encoding="utf-8") as f:
    for line in process.stdout:
        f.write(line)
        f.flush()
        print(line, end="")

process.wait()
