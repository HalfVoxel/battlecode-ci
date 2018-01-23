from trueskill import Rating, rate_1vs1
import json
import subprocess
import random
import os
import shutil
import time


project_dir = "battlecode2018"


def crash(bot):
    return (bot[0], bot[1] + 1, bot[2])


def win(winner, loser):
    rWin, rLose = rate_1vs1(winner[0], loser[0])
    return ((rWin, winner[1], winner[2] + 1), (rLose, loser[1], loser[2] + 1))


def test(commitA, commitB, rA, rB):
    keyA = "rand_" + str(random.randrange(0, 1000000))
    keyB = "rand_" + str(random.randrange(0, 1000000))

    if subprocess.call("git reset --hard HEAD", shell=True, cwd=project_dir) != 0:
        raise Exception("reset failed")
    subprocess.call("git checkout " + commitA, shell=True, cwd=project_dir)
    subprocess.call("git checkout master backup run player/common.cpp", shell=True, cwd=project_dir)

    if subprocess.call(["./backup", keyA], cwd=project_dir) != 0:
        print(commitA + " didn't compile")
        rA = crash(rA)
        rB, rA = win(rB, rA)
        return rA, rB

    if subprocess.call("git reset --hard HEAD", shell=True, cwd=project_dir) != 0:
        raise Exception("reset failed")
    subprocess.call("git checkout " + commitB, shell=True, cwd=project_dir)
    subprocess.call("git checkout master backup run player/common.cpp", shell=True, cwd=project_dir)
    if subprocess.call(["./backup", keyB], cwd=project_dir) != 0:
        print(commitB + " didn't compile")
        rB = crash(rB)
        rA, rB = win(rA, rB)
        return rA, rB

    print("Starting tournament")

    # Some symlink is destroying things
    subprocess.call("rm bc18-scaffold/battlecode/battlecode", shell=True, cwd=project_dir)

    if not os.path.isdir(project_dir + "/replays"):
        shutil.rmtree(project_dir + "/replays")
        os.mkdir(project_dir + "/replays")

    output = subprocess.check_output(["./run", "--tournament", "--threads", "2", "-a", keyA, "-b", keyB, "--max-epochs", "1", "--max-maps", "2", "--no-color"], cwd=project_dir).decode('utf-8')
    print(output)
    output = [l for l in output.strip().split('\n') if "won at round" in l]
    winsForA = sum(1 if "A won at round" in l else 0 for l in output)
    winsForB = sum(1 if "B won at round" in l else 0 for l in output)
    assert winsForA + winsForB == len(output), "Victories didn't sum up to the total length?? " + str(winsForA) + " " + str(winsForB) + " " + str(len(output))

    print("Wins: " + str(winsForA) + " vs " + str(winsForB))
    for _ in range(winsForA):
        rA, rB = win(rA, rB)

    for _ in range(winsForB):
        rB, rA = win(rB, rA)

    return rA, rB


def score(x):
    rating = x[0]
    crashes = x[1]
    return (rating.mu + rating.sigma**2)/(1 + crashes)


def iteration():
    if os.path.isfile("scores.json"):
        f = open("scores.json")
        data = json.loads(f.read())
        f.close()
    else:
        data = {}

    if subprocess.call("git checkout master", shell=True, cwd=project_dir) != 0:
        raise Exception("master checkout failed")

    if subprocess.call("git pull", shell=True, cwd=project_dir) != 0:
        raise Exception("pull failed")

    if subprocess.call("git submodule init", shell=True, cwd=project_dir) != 0:
        raise Exception("submodule init")

    if subprocess.call("git submodule sync", shell=True, cwd=project_dir) != 0:
        raise Exception("submodule sync")

    if subprocess.call("git submodule update", shell=True, cwd=project_dir) != 0:
        raise Exception("submodule update")

    if subprocess.call("git reset --hard HEAD", shell=True, cwd=project_dir) != 0:
        raise Exception("reset failed")

    commits = [l.split()[0] for l in subprocess.check_output(["git", "log", "d067cb2..master", "--pretty=oneline", "player"], cwd=project_dir).decode('utf-8').strip().split('\n')]

    for c in commits:
        if c not in data:
            data[c] = {'mu': 25, 'sigma': 8.3333, 'crashes': 0, 'tests': 0}

    ratings = {key: (Rating(mu=v['mu'], sigma=v['sigma']), v['crashes'], v['tests']) for key, v in data.items()}
    ratingsList = [(key, value) for key, value in ratings.items()]

    # Pick rating with highest sigma
    scores = [(score(x[1]), x) for x in ratingsList]
    scores.sort(reverse=True)

    to_test = scores[0]
    opponent = random.choice(scores[1:])

    commitA = to_test[1][0]
    commitB = opponent[1][0]
    rA = ratings[commitA]
    rB = ratings[commitB]

    rA, rB = test(commitA, commitB, rA, rB)
    ratings[commitA] = rA
    ratings[commitB] = rB

    print("Writing new scores")
    output = json.dumps({key: {"mu": x[0].mu, "sigma": x[0].sigma, "crashes": x[1], "tests": x[2]} for (key, x) in ratings.items()}, indent=4)
    f = open("scores.json", "w")
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
