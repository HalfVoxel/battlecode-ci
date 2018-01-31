from trueskill import Rating, rate_1vs1
import json
import subprocess
from subprocess import DEVNULL
import random
import os
import shutil
import time
import re
import datetime


project_dir = "battlecode2018"


def compile_crash(bot):
    return (bot[0], bot[1] + 1, bot[2], bot[3])


def runtime_crash(bot):
    return (bot[0], bot[1], bot[2] + 1, bot[3])


def win(winner, loser):
    rWin, rLose = rate_1vs1(winner[0], loser[0])
    return ((rWin, winner[1], winner[2], winner[3] + 1), (rLose, loser[1], loser[2], loser[3] + 1))


def test(commitA, commitB, rA, rB, history):
    keyA = "rand_" + str(random.randrange(0, 1000000))
    keyB = "rand_" + str(random.randrange(0, 1000000))

    if subprocess.call("git reset --hard HEAD", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("reset failed")
    subprocess.call("git checkout " + commitA, shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL)
    subprocess.call("git checkout master backup run bc18-scaffold", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL)
    if subprocess.call("git submodule update", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("submodule update")

    gameTime = datetime.datetime.utcnow().isoformat()

    if subprocess.call(["./backup", keyA], cwd=project_dir) != 0:
        print(commitA + " didn't compile")
        rA = compile_crash(rA)
        rB, rA = win(rB, rA)
        info = {
            "type": "crash",
            "hash": commitA,
            "time": gameTime,
        }
        history.append(info)
        return rA, rB

    if subprocess.call("git reset --hard HEAD", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("reset failed")
    subprocess.call("git checkout " + commitB, shell=True, cwd=project_dir)
    subprocess.call("git checkout master backup run bc18-scaffold", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL)
    if subprocess.call("git submodule update", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("submodule update")

    if subprocess.call(["./backup", keyB], cwd=project_dir) != 0:
        print(commitB + " didn't compile")
        rB = compile_crash(rB)
        rA, rB = win(rA, rB)

        info = {
            "type": "crash",
            "hash": commitB,
            "time": gameTime,
        }
        history.append(info)
        return rA, rB

    print("Starting tournament")

    # Some symlink is destroying things
    subprocess.call("rm bc18-scaffold/battlecode/battlecode", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL)

    if os.path.isdir(project_dir + "/replays"):
        shutil.rmtree(project_dir + "/replays")

    os.mkdir(project_dir + "/replays")

    output = subprocess.check_output(["./run", "--tournament", "--threads", "2", "-a", keyA, "-b", keyB, "--max-epochs", "1", "--max-maps", "2", "--no-color", "--save-replays"], cwd=project_dir).decode('utf-8')
    print(output)
    output = [l for l in output.strip().split('\n') if "won at round" in l]
    winsForA = [l for l in output if "A won at round" in l]
    winsForB = [l for l in output if "B won at round" in l]
    assert len(winsForA) + len(winsForB) == len(output), "Victories didn't sum up to the total length?? " + str(len(winsForA)) + " " + str(len(winsForB)) + " " + str(len(output))

    print("Wins: " + str(len(winsForA)) + " vs " + str(len(winsForB)))
    winRegex = re.compile(r"(.+?)\s+(\d+|\?)x(\d+|\?)\s+(A vs B|B vs A):\s+(A|B) won at round (\d+) (?:\(opponent (crashed|timed out) on (earth|mars)\))? replay: (.*)", re.DOTALL)

    for line in output:
        match = winRegex.search(line.split("\r")[-1])
        assert(match is not None)
        map = match.group(1)
        w = match.group(2)
        h = match.group(3)
        order = match.group(4)
        winner = match.group(5)
        round = int(match.group(6))
        crashType = match.group(7)
        crashPlanet = match.group(8)
        replay = match.group(9)
        assert(winner == "A" or winner == "B")
        assert(order == "A vs B" or order == "B vs A")
        assert(crashType is None or crashType == "crashed" or crashType == "timed out")
        assert(replay is not None)
        assert(crashPlanet is None or crashPlanet == "earth" or crashPlanet == "mars")

        if crashPlanet is not None:
            if winner == "A":
                rB = runtime_crash(rB)
            else:
                rA = runtime_crash(rA)

        info = {
            "type": "game",
            "time": gameTime,
            "a": commitA,
            "b": commitB,
            "winner": winner,
            "order": order,
            "round": round,
            "map": map,
            "mapWidth": w,
            "mapHeight": h,
            "crash": crashType == "crashed",
            "timeout": crashType == "timed out",
            "crashPlanet": crashPlanet,
            "replay": replay,
        }
        print(info)
        history.append(info)

        if winner == "A":
            rA, rB = win(rA, rB)
        else:
            rB, rA = win(rB, rA)

    return rA, rB


def score(x):
    rating = x[0]
    crashes = x[1]
    return (rating.mu + rating.sigma**2)/(1 + crashes)


def iteration():
    if os.path.isfile("history.json"):
        f = open("history.json")
        history = json.loads(f.read())
        f.close()
    else:
        history = []

    if subprocess.call("git checkout master", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("master checkout failed")

    if subprocess.call("git fetch", shell=True, cwd=project_dir) != 0:
        raise Exception("fetch failed")

    if subprocess.call("git reset --hard origin/master", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("reset failed")

    if subprocess.call("git submodule init", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("submodule init")

    if subprocess.call("git submodule sync", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("submodule sync")

    if subprocess.call("git submodule update", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("submodule update")

    if subprocess.call("git reset --hard HEAD", shell=True, cwd=project_dir, stdout=DEVNULL, stderr=DEVNULL) != 0:
        raise Exception("reset failed")

    commits = [l.split()[0] for l in subprocess.check_output(["git", "log", "d067cb2..master", "--pretty=oneline", "player"], cwd=project_dir).decode('utf-8').strip().split('\n')]

    # Recreate scores
    data = {}
    for c in commits:
        if c not in data:
            data[c] = {'mu': 25, 'sigma': 8.3333, 'crashes': 0, 'runtime_crashes': 0, 'tests': 0}

    ratings = {key: (Rating(mu=v['mu'], sigma=v['sigma']), v['crashes'], v['runtime_crashes'], v['tests']) for key, v in data.items()}

    for item in history:
        if item['type'] == "crash":
            hash = item['hash']
            if hash in ratings:
                ratings[hash] = compile_crash(ratings[hash])
        else:
            # Game
            a = item['a']
            b = item['b']
            if a in ratings and b in ratings:
                winner = a if item['winner'] == "A" else b
                loser = b if item['winner'] == "A" else a
                ratings[winner], ratings[loser] = win(ratings[winner], ratings[loser])

                if 'crash' in item and item['crash']:
                    ratings[loser] = runtime_crash(ratings[loser])

    ratingsList = [(key, value) for key, value in ratings.items() if key in commits]

    # Pick rating with highest sigma
    scores = []
    for i in range(len(ratingsList)):
        x = ratingsList[i]

        rating = x[1][0]
        # deltaScore1 = 0 if i == 0 else (rating.mu - ratingsList[i-1][1][0].mu)**2
        # deltaScore2 = 1 if i == len(ratingsList)-1 else (rating.mu - ratingsList[i+1][1][0].mu)**2
        crashes = x[1][1]
        tests = x[1][3]
        totalScore = 1 / ((1 + crashes) + (1 + tests))**2  # (rating.sigma*rating.sigma + deltaScore1 + deltaScore2)/(1 + crashes)
        scores.append((random.uniform(0,1) * totalScore, x))

    # scores = [(score(x[1]), x) for x in ratingsList]
    scores.sort(reverse=True)
    to_test = scores[0]

    if random.uniform(0,1) < 0.2:
        # Pick a completely random opponent with 20% probability
        opponent = random.choice(scores[1:])
    else:
        scores = []
        opponent = None
        for i in range(len(ratingsList)):
            x = ratingsList[i]
            if x == to_test[1]:
                continue

            rating = x[1][0]
            score = 1/(1 + (rating.mu - to_test[1][1][0].mu)**2)
            scores.append((random.uniform(0,1) * score, x))

        scores.sort(reverse=True)
        opponent = scores[0]

    commitA = to_test[1][0]
    commitB = opponent[1][0]
    rA = ratings[commitA]
    rB = ratings[commitB]
    print("Matching " + str(rA[0].mu) + " against " + str(rB[0].mu))

    rA, rB = test(commitA, commitB, rA, rB, history)
    ratings[commitA] = rA
    ratings[commitB] = rB

    print("Writing new scores")
    output = json.dumps({key: {"mu": x[0].mu, "sigma": x[0].sigma, "crashes": x[1], "runtime_crashes": x[2], "tests": x[3]} for (key, x) in ratings.items()}, indent=4)
    f = open("scores.json", "w")
    f.write(output)
    f.close()

    output = json.dumps(history, indent=4)
    f = open("history.json", "w")
    f.write(output)
    f.close()


def main():
    while True:
        try:
            iteration()
        except Exception as e:
            print(e)
            time.sleep(10)


main()
