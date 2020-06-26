import subprocess
import copy
import os
import json
import errno
import time
import codecs
import sys
import re
import argparse
import fnmatch
import glob
import fcntl

#
# Check if config contains all the listed params
#
def contains(params, config):
    for p in params:
        if p not in config:
            return False
    return True

# Check if a config boolean is set
def configtrue(name, config):
    if name in config and config[name]:
        return True
    return False

# Handle variable expansion of return values, variables are of the form ${XXX}
# need to handle expansion in list and dicts
__expand_re__ = re.compile(r"\${[^{}@\n\t :]+}")
def expandresult(entry, config):
    if isinstance(entry, list):
        ret = []
        for k in entry:
            ret.append(expandresult(k, config))
        return ret
    if isinstance(entry, dict):
        ret = {}
        for k in entry:
            ret[expandresult(k, config)] = expandresult(entry[k], config)
        return ret
    if not isinstance(entry, str):
        return entry
    class expander:
        def __init__(self, config):
            self.config = config
        def expand(self, entry):
            ret = getconfig(entry.group(0)[2:-1], config)
            if not ret:
                return entry.group(0)
            return ret

    e = expander(config)
    while entry.find('${') != -1:
        newentry = __expand_re__.sub(e.expand, entry)
        if newentry == entry:
            break
        entry = newentry
    return entry

# Get a configuration value
def getconfig(name, config):
    if name in config:
        ret = config[name]
        return expandresult(ret, config)
    return False

# Get a build configuration variable, check overrides first, then defaults
def getconfigvar(name, config, target=None, stepnum=None):
    if target:
        if target in config['overrides']:
            if stepnum:
                step = "step" + str(stepnum)
                if step in config['overrides'][target] and name in config['overrides'][target][step]:
                    ret = config['overrides'][target][step][name]
                    return expandresult(ret, config)
            if name in config['overrides'][target]:
                ret = config['overrides'][target][name]
                return expandresult(ret, config)
    if name in config['defaults']: 
        ret = config['defaults'][name]
        return expandresult(ret, config)
    return False

def getconfiglist(name, config, target, stepnum):
    ret = []
    step = "step" + str(stepnum)
    if target in config['overrides']:
        if step in config['overrides'][target] and name in config['overrides'][target][step]:
            ret.extend(config['overrides'][target][step][name])
        if name in config['overrides'][target]:
            ret.extend(config['overrides'][target][name])
    if name in config['defaults']: 
        ret.extend(config['defaults'][name])
    return expandresult(ret, config)

# Return only unique configuration values (identified with '=' in them)
def getconfiglistfilter(name, config, target, stepnum):
    def merge(main, newvals):
        have = []
        for i in main:
            a, b = i.split(" ", 1)
            have.append(a)
        for i in newvals:
            # Don't want to match +=
            if " = " in i:
                a, b = i.split(" ", 1)
                if a not in have:
                    main.append(i)
            else:
                main.append(i)
    ret = []
    step = "step" + str(stepnum)
    if target in config['overrides']:
        if step in config['overrides'][target] and name in config['overrides'][target][step]:
            merge(ret, config['overrides'][target][step][name])
        if name in config['overrides'][target]:
            merge(ret, config['overrides'][target][name])
    if name in config['defaults']:
        merge(ret, config['defaults'][name])
    return expandresult(ret, config)

#
# Expand 'templates' with the configuration
#
# This allows values to be imported from a template if they're not already set
#
def expandtemplates(ourconfig):
    orig = copy.deepcopy(ourconfig)
    for t in orig['overrides']:
        if "TEMPLATE" in orig['overrides'][t]:
            template = orig['overrides'][t]["TEMPLATE"]
            if template not in orig['templates']:
                print("Error, template %s not defined" % template)
                sys.exit(1)
            for v in orig['templates'][template]:
                val = orig['templates'][template][v]
                if v not in ourconfig['overrides'][t]:
                    ourconfig['overrides'][t][v] = copy.deepcopy(orig['templates'][template][v])
                elif not isinstance(val, str) and not isinstance(val, bool) and not isinstance(val, int):
                    for w in val:
                        if w not in ourconfig['overrides'][t][v]:
                            ourconfig['overrides'][t][v][w] = copy.deepcopy(orig['templates'][template][v][w])
    return ourconfig

#
# Helper to load the json config files
#
# Defaults to the top level config.json file
# however this can be customised from the environment, e.g.:
#   ABHELPER_JSON="config.json local.json"
#   ABHELPER_JSON="config.json /path/to/local.json"
# files without paths are assumed to be in scripts/..
#
# Values from later files overwrite values from earlier files
# Lists are replaced, dict elements are replaced.
# Deletion of a field isn't possible
#
def loadconfig():
    files = "config.json"
    if "ABHELPER_JSON" in os.environ:
        files = os.environ["ABHELPER_JSON"]

    scriptsdir = os.path.dirname(os.path.realpath(__file__))

    def handledict(config, ourconfig, c):
        if not c in ourconfig:
            ourconfig[c] = config[c]
            return
        for x in config[c]:
            if isinstance(config[c][x], dict):
                handledict(config[c], ourconfig[c], x)
            else:
                ourconfig[c][x] = config[c][x]

    ourconfig = {}
    for f in files.split():
        p = f
        if not f.startswith("/"):
            p = os.path.join(scriptsdir, '..', f)
        with open(p) as j:
            config = json.load(j)
            for c in config:
                if isinstance(config[c], dict):
                    handledict(config, ourconfig, c)
                else:
                    ourconfig[c] = config[c]

    # Expand templates in the configuration
    ourconfig = expandtemplates(ourconfig)

    return ourconfig


#
# Common function to determine if buildhistory is enabled and what the parameters are
#
def getbuildhistoryconfig(ourconfig, builddir, target, reponame, branchname, stepnum):
    if contains(["BUILD_HISTORY_DIR", "BUILD_HISTORY_REPO"], ourconfig):
        if getconfigvar("BUILDHISTORY", ourconfig, target, stepnum):
            base = None
            if "/" in reponame:
                reponame = reponame.rsplit("/", 1)[1]
            if reponame.endswith(".git"):
                reponame = reponame[:-4]
            if (reponame + ":" + branchname) in getconfig("BUILD_HISTORY_DIRECTPUSH", ourconfig):
                base = reponame + ":" + branchname
            if (reponame + ":" + branchname) in getconfig("BUILD_HISTORY_FORKPUSH", ourconfig):
                base = getconfig("BUILD_HISTORY_FORKPUSH", ourconfig)[reponame + ":" + branchname]
            if base:
                baserepo, basebranch = base.split(":")
                bh_path = getconfig("BUILD_HISTORY_DIR", ourconfig)
                if not os.path.isabs(bh_path):
                    bh_path = os.path.join(builddir, bh_path)
                remoterepo = getconfig("BUILD_HISTORY_REPO", ourconfig)
                remotebranch = reponame + "/" + branchname + "/" + target
                baseremotebranch = baserepo + "/" + basebranch + "/" + target

                return bh_path, remoterepo, remotebranch, baseremotebranch
    return None, None, None, None

#
# Run a command, trigger a traceback with command output if it fails
#
def runcmd(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT)


def fetchgitrepo(clonedir, repo, params, stashdir):
    sharedrepo = "%s/%s" % (clonedir, repo)
    branch = params["branch"]
    revision = params["revision"]
    if os.path.exists(stashdir + "/" + repo):
        subprocess.check_call(["git", "clone", "file://%s/%s" % (stashdir, repo), "%s/%s" % (clonedir, repo)])
        subprocess.check_call(["git", "remote", "rm", "origin"], cwd=sharedrepo)
        subprocess.check_call(["git", "remote", "add", "origin", params["url"]], cwd=sharedrepo)
        subprocess.check_call(["git", "fetch", "origin"], cwd=sharedrepo)
        subprocess.check_call(["git", "fetch", "origin", "-t"], cwd=sharedrepo)
    else:
        subprocess.check_call(["git", "clone", params["url"], sharedrepo])

    subprocess.check_call(["git", "checkout", branch], cwd=sharedrepo)
    # git reset revision==HEAD won't help, we need to reset onto the potentially fetched origin branch
    subprocess.check_call(["git", "reset", "origin/" + branch, "--hard"], cwd=sharedrepo)
    subprocess.check_call(["git", "reset", revision, "--hard"], cwd=sharedrepo)

def publishrepo(clonedir, repo, publishdir):
    sharedrepo = "%s/%s" % (clonedir, repo)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sharedrepo).decode('utf-8').strip()
    archive_name = repo + "-" + revision + ".tar.bz2"
    subprocess.check_call("git archive --format=tar HEAD --prefix=" + repo + "/ | bzip2 -c > " + archive_name, shell=True, cwd=sharedrepo)
    subprocess.check_call("sha256sum " + archive_name + " >> " + archive_name + ".sha256sum", shell=True, cwd=sharedrepo)
    mkdir(publishdir)
    subprocess.check_call("rsync -av " + archive_name + "* " + publishdir, shell=True, cwd=sharedrepo)

def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            # Do not complain if the directory exists
            raise e

def flush():
    sys.stdout.flush()
    sys.stderr.flush()

def printheader(msg, timestamp=True):
    print("")
    print("====================================================================================================")
    if timestamp is True:
        print("%s (%s)" % (msg, round(time.time(), 1)))
    elif timestamp:
        print("%s (%s)" % (msg, timestamp))
    else:
        print(msg)
    print("====================================================================================================")
    print("")
    flush()

class HeaderPrinter(object):
    def __init__(self):
        self.last = time.time()
    def printheader(self, msg):
        printheader(msg, "%s: %s" % (round(time.time(), 1), round(time.time() - self.last, 1)))
        self.last = time.time()

def errorreportdir(builddir):
    return builddir + "/tmp/log/error-report/"

class ErrorReport(object):
    def __init__(self, ourconfig, target, builddir, branchname, revision):
        self.ourconfig = ourconfig
        self.target = target
        self.builddir = builddir
        self.branchname = branchname
        self.revision = revision


    def create(self, command, stepnum, logfile):
        report = {}
        report['machine'] = getconfigvar("MACHINE", self.ourconfig, self.target, stepnum)
        report['distro'] = getconfigvar("DISTRO", self.ourconfig, self.target, stepnum)

        report['build_sys'] = "unknown"
        report['nativelsb'] = "unknown"
        report['target_sys'] = "unknown"

        report['component'] = 'bitbake'

        report['branch_commit'] = self.branchname + ': ' + self.revision

        failure = {}
        failure['package'] = "bitbake"
        if 'bitbake-selftest' in command:
            report['error_type'] = 'bitbake-selftest'
            failure['task'] = command[command.find('bitbake-selftest'):]
        elif  'oe-selftest' in command:
            report['error_type'] = 'oe-selftest'
            failure['task'] = command[command.find('oe-selftest'):]
        else:
            report['error_type'] = 'core'
            failure['task'] = command[command.find('bitbake'):]

        if os.path.exists(logfile):
            with open(logfile) as f:
                loglines = f.readlines()

            failure['log'] = "".join(loglines)
        else:
            failure['log'] = "Command failed"

        report['failures'] = [failure]

        errordir = errorreportdir(self.builddir)
        mkdir(errordir)

        filename = os.path.join(errordir, "error_report_bitbake_%d.txt" % (int(time.time())))
        with codecs.open(filename, 'w', 'utf-8') as f:
            json.dump(report, f, indent=4, sort_keys=True)

class ArgParser(argparse.ArgumentParser):
    def error(self, message):
        # Show the help if there's an argument parsing error (e.g. no arguments, missing argument, ...)
        sys.stderr.write('error: %s\n' % message)
        self.print_help()
        sys.exit(2)

#
# Figure out which branch we might need to compare against
# Also return whether this is a forked branch or not.
#
def getcomparisonbranch(ourconfig, reponame, branchname):
    print("Working off %s:%s\n" % (reponame, branchname))
    if "/" in reponame:
        reponame = reponame.rsplit("/", 1)[1]
    if reponame.endswith(".git"):
        reponame = reponame[:-4]
    if (reponame + ":" + branchname) in getconfig("BUILD_HISTORY_FORKPUSH", ourconfig):
        base = getconfig("BUILD_HISTORY_FORKPUSH", ourconfig)[reponame + ":" + branchname]
        if base:
            comparerepo, comparebranch = base.split(":")
            print("Comparing to %s\n" % (comparebranch))
            return branchname, comparebranch
    if (reponame + ":" + branchname) in getconfig("BUILD_HISTORY_DIRECTPUSH", ourconfig):
        return branchname, None
    return None, None

def setup_buildtools_tarball(ourconfig, workername, btdir):
    bttarball = None
    if "buildtools" in ourconfig and workername:
        btcfg = getconfig("buildtools", ourconfig)
        for entry in btcfg:
            if fnmatch.fnmatch(workername, entry):
                bttarball = btcfg[entry]
                break

    btenv = None
    if bttarball:
        btdir = os.path.abspath(btdir)
        if not os.path.exists(btdir):
            btdlpath = getconfig("BASE_SHAREDDIR", ourconfig) + "/buildtools/" + os.path.basename(bttarball)
            print("Extracting buildtools %s" % bttarball)
            btlock = btdlpath + ".lock"
            if not os.path.exists(os.path.dirname(btdlpath)):
                os.makedirs(os.path.dirname(btdlpath), exist_ok=True)
            while True:
                try:
                    with open(btlock, 'a+') as lf:
                        fileno = lf.fileno()
                        fcntl.flock(fileno, fcntl.LOCK_EX)
                        if not os.path.exists(btdlpath):
                            if bttarball.startswith("/"):
                                subprocess.check_call(["cp", bttarball, btdlpath])
                            else:
                                subprocess.check_call(["wget", "-O", btdlpath, bttarball])
                            os.chmod(btdlpath, 0o775)
                    break
                except OSError:
                    # We raced with someone else, try again
                    pass
            subprocess.check_call(["bash", btdlpath, "-d", btdir, "-y"])
        btenv = glob.glob(btdir + "/environment-setup*")
        print("Using buildtools %s" % btenv)
        # We either parse or wrap all our execution calls, rock and a hard place :(
        with open(btenv[0], "r") as f:
            for line in f.readlines():
                if line.startswith("export "):
                    line = line.strip().split(" ", 1)[1].split("=", 1)
                    if "$PATH" in line[1]:
                        line[1] = line[1].replace("$PATH", os.environ["PATH"])
                    if line[1].startswith(("'", '"')):
                        line[1] = line[1][1:-1]
                    os.environ[line[0]] = line[1]
