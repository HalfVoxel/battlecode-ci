#!/usr/bin/python3
from flask import Flask, render_template, request, abort
from flask_compress import Compress
from subprocess import call
import json
import dateutil.parser
from datetime import datetime, timedelta
import sys
import subprocess
from trueskill import Rating

app = Flask(__name__)
Compress(app)

project_dir = "battlecode2018"


@app.route("/")
def main():
    data = json.loads(open("scores.json").read())
    commits = subprocess.check_output(["git", "log", "d067cb2..master", r"--pretty=%H||%an||%s"], cwd=project_dir).decode('utf-8').strip().split('\n')
    items = []
    for line in commits:
        print(line)
        h, author, msg = line.split("||")
        if h in data:
            k = data[h]
            r = Rating(mu=k["mu"], sigma=k["sigma"])
            tests = k["tests"]
            items.append((author + ": " + msg, str(round(r.mu, 3)), "Has crashed during compilation" if k["crashes"] > 0 else "Sigma: " + str(round(r.sigma, 3)) + ", " + str(tests) + " games played"))
        else:
            items.append((author + ": " + msg, "?", ""))

    return render_template("main.html", items=items)


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False, port=5004)
