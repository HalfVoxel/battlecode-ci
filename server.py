#!/usr/bin/python3
from flask import Flask, render_template, request, abort
from flask_compress import Compress
from subprocess import call
import json
import dateutil.parser
from datetime import datetime, timedelta
import sys
import os
import subprocess
from trueskill import Rating

app = Flask(__name__)
Compress(app)

project_dir = "battlecode2018"


@app.route("/")
def main():
    data = json.loads(open("scores.json").read())
    commits = subprocess.check_output(["git", "log", "d067cb2..master", r"--pretty=%H||%an||%s", "player"], cwd=project_dir).decode('utf-8').strip().split('\n')
    items = []
    jsData = []
    totalGames = 0
    for line in commits:
        h, author, msg = line.split("||")
        commitURL = "/ci/commit/" + h
        if h in data and data[h]['tests'] > 0:
            totalGames += data[h]['tests']
            k = data[h]
            r = Rating(mu=k["mu"], sigma=k["sigma"])
            tests = k["tests"]
            items.append((author + ": " + msg, commitURL, str(round(r.mu, 3)), "Has crashed during compilation" if k["crashes"] > 0 else "Sigma: " + str(round(r.sigma, 3)) + ", " + str(tests) + " games played"))

            # Note: chart library shows ±0.5 sigma, so we double it here
            jsData.append({"label": h[0:6], "mu": r.mu, "sigma": 2*r.sigma})
        else:
            items.append((author + ": " + msg, commitURL, "?", ""))

    return render_template("main.html", items=items, totalGames=totalGames//2, data=json.dumps(list(reversed(jsData))))

# {
#         "type": "game",
#         "time": "2018-01-24T16:20:20.626311",
#         "a": "0c8615e3ea5f1fe4032cc4a6354b5a328478e875",
#         "b": "d1c1321998f09777d8157237b0b339f2be45ad23",
#         "winner": "B",
#         "order": "B vs A",
#         "round": 152,
#         "map": "cross",
#         "mapWidth": "20",
#         "mapHeight": "20"
#     },

@app.route("/commit/<hash>")
def commitPage(hash):
    data = json.loads(open("history.json").read())
    data = [x for x in data if (x['type'] == "game" and (x['a'] == hash or x['b'] == hash) or (x['type'] == "crash" and x['hash'] == hash))]
    items = []
    for x in data:
        if x['type'] == "game":
            a = x['a']
            b = x['b']
            opponent = b if a == hash else a
            outcome = (x['winner'] == "A") == (hash == a)
            replayLink = "/replays/" + os.path.relpath(x['replay'] + ".bc18z")
            logLink = "/replays/" + os.path.relpath(x['replay'] + ".bc18log")
            items.append((x['time'], opponent[0:6], x['map'] + " " + x['mapWidth'] + "x" + x['mapHeight'], "Win" if outcome else "Loss", replayLink, logLink))
        else:
            # Crash
            items.append((x['time'], "", "", "Crashed during compilation", "", ""))

    return render_template("commit.html", items=items, totalGames=len(data))

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False, port=5010)
