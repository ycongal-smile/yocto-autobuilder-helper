import subprocess
import copy
import os
import json
import errno
import time
import codecs
import sys
import re

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
    print(str(entry))
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
            ret = getconfig(entry[0][2:-1], config)
            if not ret:
                return entry[0][2:-1]
            return ret

    e = expander(config)
    while entry.find('${') != -1:
        entry = __expand_re__.sub(e.expand, entry)
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
    return ret

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
# Helper to load the config.json file for scripts in the scripts directory (pass in __file__)
#
def loadconfig(f):
    scriptsdir = os.path.dirname(os.path.realpath(f))

    with open(os.path.join(scriptsdir, '..', 'config.json')) as f:
        ourconfig = json.load(f)

    # Expand templates in the configuration
    ourconfig = expandtemplates(ourconfig)

    return ourconfig


#
# Common function to determine if buildhistory is enabled and what the parameters are
#
def getbuildhistoryconfig(ourconfig, target, reponame, branchname):
    if contains(["BUILD_HISTORY_DIR", "build-history-targets", "BUILD_HISTORY_REPO"], ourconfig):
        if target in ourconfig["build-history-targets"]:
            base = None
            if (reponame + ":" + branchname) in ourconfig["BUILD_HISTORY_DIRECTPUSH"]:
                base = reponame + ":" + branchname
            if (reponame + ":" + branchname) in ourconfig["BUILD_HISTORY_FORKPUSH"]:
                base = ourconfig["BUILD_HISTORY_FORKPUSH"][reponame + ":" + branchname]
            if base:
                baserepo, basebranch = base.split(":")
                bh_path = os.path.join(ourconfig["BUILD_HISTORY_DIR"], reponame, branchname, target)
                remoterepo = ourconfig["BUILD_HISTORY_REPO"]
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
    subprocess.check_call("md5sum " + archive_name + " >> " + archive_name + ".md5sum", shell=True, cwd=sharedrepo)
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
    if timestamp:
        print("%s (%s)" % (msg, time.time()))
    else:
        print(msg)
    print("====================================================================================================")
    print("")
    flush()

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

