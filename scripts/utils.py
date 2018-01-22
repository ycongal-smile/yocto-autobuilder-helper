import subprocess
import copy
import os
import json

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
# Run a command, trigger a traceback with command output if it fails
#
def runcmd(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT)


def fetchgitrepo(clonedir, repo, params, stashdir):
    sharedrepo = "%s/%s" % (clonedir, repo)
    branch = params["branch"]
    revision = params["revision"]
    if os.path.exists(stash + "/" + repo):
        subprocess.check_call(["git", "clone", "file://%s/%s" % (stashdir, repo), "%s/%s" % (clonedir, repo)])
        subprocess.check_call(["git", "remote", "rm", "origin"], cwd=sharedrepo)
        subprocess.check_call(["git", "remote", "add", "origin", params["url"]], cwd=sharedrepo)
        subprocess.check_call(["git", "fetch", "origin", "-t"], cwd=sharedrepo)
    else:
        subprocess.check_call(["git", "clone", params["url"], sharedrepo])

    subprocess.check_call(["git", "checkout", branch], cwd=sharedrepo)
    subprocess.check_call(["git", "reset", revision, "--hard"], cwd=sharedrepo)

def printheader(msg):
    print("")
    print("====================================================================================================")
    print(msg)
    print("====================================================================================================")
    print("")
