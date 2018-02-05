import subprocess
import copy
import os
import json
import errno
import time
import codecs

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

# Get a configuration variable, check overrides, first, the defaults
def getconfigvar(name, config, target, stepnum):
    step = "step" + str(stepnum)
    if target in config['overrides']:
        if step in config['overrides'][target] and name in config['overrides'][target][step]:
            return config['overrides'][target][step][name]
        if name in config['overrides'][target]:
            return config['overrides'][target][name]
    if name in config['defaults']: 
        return config['defaults'][name]
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
        subprocess.check_call(["git", "fetch", "origin", "-t"], cwd=sharedrepo)
    else:
        subprocess.check_call(["git", "clone", params["url"], sharedrepo])

    subprocess.check_call(["git", "checkout", branch], cwd=sharedrepo)
    subprocess.check_call(["git", "reset", revision, "--hard"], cwd=sharedrepo)


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            # Do not complain if the directory exists
            raise e

def printheader(msg):
    print("")
    print("====================================================================================================")
    print(msg)
    print("====================================================================================================")
    print("")

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

