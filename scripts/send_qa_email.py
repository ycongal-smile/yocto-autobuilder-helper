#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Send email about the build to prompt QA to begin testing
#

import json
import os
import sys
import subprocess
import tempfile
import re

import utils

def is_non_release_version(version):
    p = re.compile('\d{8}-\d+')
    return p.match(version) is not None

def get_previous_tag(targetrepodir, version):
    previousversion = None
    previousmilestone = None
    if version:
        if is_non_release_version(version):
            return subprocess.check_output(["git", "describe", "--abbrev=0"], cwd=targetrepodir).decode('utf-8').strip()
        compareversion, comparemilestone, _ = utils.get_version_from_string(version)
        compareversionminor = compareversion[-1]
        # After ignoring rc part, if we get a minor to 0 on point release (e.g 4.0.0),
        # reject last digit since such versions do not exist
        if len(compareversion) == 3 and compareversionminor == 0:
            compareversion = compareversion[:-1]

        # Process milestone if not first in current release
        if comparemilestone and comparemilestone > 1:
            previousversion = compareversion
            previousmilestone = comparemilestone-1
        # Process first milestone or release if not first in major release
        elif compareversionminor > 0:
            previousversion = compareversion[:-1] + [compareversion[-1] - 1]
        # Otherwise : format it as tag (which must exist) and search previous tag
        else:
            comparetagstring = utils.get_tag_from_version(compareversion, comparemilestone)
            return subprocess.check_output(["git", "describe", "--abbrev=0", comparetagstring + "^"], cwd=targetrepodir).decode('utf-8').strip()

        return utils.get_tag_from_version(previousversion, previousmilestone)

    # All other cases : merely check against latest tag reachable
    defaultbaseversion, _, _ = utils.get_version_from_string(subprocess.check_output(["git", "describe", "--abbrev=0"], cwd=targetrepodir).decode('utf-8').strip())
    return utils.get_tag_from_version(defaultbaseversion, None)

def get_sha1(targetrepodir, revision):
    return subprocess.check_output(["git", "rev-list", "-n", "1", revision], cwd=targetrepodir).decode('utf-8').strip()

def fetch_testresults(resultdir, revision):
    rawtags = subprocess.check_output(["git", "ls-remote", "--refs", "--tags", "origin", f"*{revision}*"], cwd=resultdir).decode('utf-8').strip()
    if not rawtags:
        raise Exception(f"No reference found for commit {revision} in {resultdir}")
    for ref in [rawtag.split()[1] for rawtag in rawtags.splitlines()]:
        print(f"Fetching matching revisions: {ref}")
        subprocess.check_call(["git", "fetch", "--depth", "1", "origin", f"{ref}:{ref}"], cwd=resultdir)


def generate_regression_report(resulttool, targetrepodir, basebranch, resultdir, outputdir, yoctoversion):
    baseversion = get_previous_tag(targetrepodir, yoctoversion)
    baserevision = get_sha1(targetrepodir, baseversion)
    comparerevision = get_sha1(targetrepodir, basebranch)
    print(f"Compare version : {basebranch} ({comparerevision})")
    print(f"Base tag : {baseversion} ({baserevision})")

    try:
        """
        Results directory is likely a shallow clone :
        we need to fetch results corresponding to base revision before
        running resulttool
        """
        fetch_testresults(resultdir, baserevision)
        fetch_testresults(resultdir, comparerevision)
        regreport = subprocess.check_output([resulttool, "regression-git", "-B", basebranch, "--commit", baserevision, "--commit2", comparerevision, resultdir])
        with open(outputdir + "/testresult-regressions-report.txt", "wb") as f:
           f.write(regreport)
    except subprocess.CalledProcessError as e:
        error = str(e)
        print(f"Error while generating report between {baserevision} and {comparerevision} : {error}")


def send_qa_email():
    parser = utils.ArgParser(description='Process test results and optionally send an email about the build to prompt QA to begin testing.')

    parser.add_argument('send',
                        help="True to send email, otherwise the script will display a message and exit")
    parser.add_argument('repojson',
                        help="The json file containing the repositories to use")
    parser.add_argument('sharedrepodir',
                        help="The shared repos directory (to resolve the repo revision hashes)")
    parser.add_argument('-p', '--publish-dir',
                        action='store',
                        help="Where the artefacts were published")
    parser.add_argument('-R', '--results-dir',
                        action='store',
                        help="Where the test results were published")
    parser.add_argument('-r', '--release',
                        action='store',
                        help="The build/release 'name' for release purposes (optional)")

    args = parser.parse_args()

    scriptsdir = os.path.dirname(os.path.realpath(__file__))
    ourconfig = utils.loadconfig()

    with open(args.repojson) as f:
        repos = json.load(f)

    resulttool = os.path.dirname(args.repojson) + "/build/scripts/resulttool"

    buildtoolsdir = os.path.dirname(args.repojson) + "/build/buildtools"
    if os.path.exists(buildtoolsdir):
        utils.enable_buildtools_tarball(buildtoolsdir)

    repodir = os.path.dirname(args.repojson) + "/build/repos"

    if 'poky' in repos and os.path.exists(resulttool) and args.results_dir:
        # Need the finalised revisions (not 'HEAD')
        targetrepodir = "%s/poky" % (repodir)
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=targetrepodir).decode('utf-8').strip()
        branch = repos['poky']['branch']
        repo = repos['poky']['url']

        basebranch, comparebranch = utils.getcomparisonbranch(ourconfig, repo, branch)
        report = subprocess.check_output([resulttool, "report", args.results_dir])
        with open(args.results_dir + "/testresult-report.txt", "wb") as f:
            f.write(report)

        tempdir = tempfile.mkdtemp(prefix='sendqaemail.')
        try:
            cloneopts = []
            if comparebranch:
                cloneopts = ["--branch", comparebranch]
            elif basebranch:
                cloneopts = ["--branch", basebranch]
            try:
                subprocess.check_call(["git", "clone", "git@push.yoctoproject.org:yocto-testresults", tempdir, "--depth", "1"] + cloneopts)
            except subprocess.CalledProcessError:
                print("No comparision branch found, falling back to master")
                subprocess.check_call(["git", "clone", "git@push.yoctoproject.org:yocto-testresults", tempdir, "--depth", "1"])

            # If the base comparision branch isn't present regression comparision won't work
            # at least until we can tell the tool to ignore internal branch information
            if basebranch:
                try:
                    subprocess.check_call(["git", "rev-parse", "--verify", basebranch], cwd=tempdir)
                except subprocess.CalledProcessError:
                    # Doesn't exist so base it off master
                    # some older hosts don't have git branch old new
                    subprocess.check_call(["git", "checkout", "master"], cwd=tempdir)
                    subprocess.check_call(["git", "branch", basebranch], cwd=tempdir)
                    subprocess.check_call(["git", "checkout", basebranch], cwd=tempdir)

            subprocess.check_call([resulttool, "store", args.results_dir, tempdir])
            if comparebranch:
                subprocess.check_call(["git", "push", "--all", "--force"], cwd=tempdir)
                subprocess.check_call(["git", "push", "--tags", "--force"], cwd=tempdir)
            elif basebranch:
                subprocess.check_call(["git", "push", "--all"], cwd=tempdir)
                subprocess.check_call(["git", "push", "--tags"], cwd=tempdir)

            if basebranch:
                generate_regression_report(resulttool, targetrepodir, basebranch, tempdir, args.results_dir, args.release)

        finally:
            subprocess.check_call(["rm", "-rf",  tempdir])
            pass

    if args.send.lower() != 'true' or not args.publish_dir or not args.release:
        utils.printheader("Not sending QA email")
        sys.exit(0)

    buildhashes = ""
    for repo in sorted(repos.keys()):
        # gplv2 is no longer built/tested in master
        if repo == "meta-gplv2":
            continue
        # Need the finalised revisions (not 'HEAD')
        targetrepodir = "%s/%s" % (repodir, repo)
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=targetrepodir).decode('utf-8').strip()
        buildhashes += "%s: %s\n" % (repo, revision)

    web_root = utils.getconfig('WEBPUBLISH_DIR', ourconfig)
    web_url = utils.getconfig('WEBPUBLISH_URL', ourconfig)

    email = ""
    mailto = utils.getconfig("QAMAIL_TO", ourconfig)
    if mailto:
        email += "To: " + mailto + "\n"
    mailcc = utils.getconfig("QAMAIL_CC", ourconfig)
    if mailcc:
        email += "Cc: " + mailcc + "\n"
    mailbcc = utils.getconfig("QAMAIL_BCC", ourconfig)
    if mailbcc:
        email += "Bcc: " + mailbcc + "\n"

    email += "Subject: " + "QA notification for completed autobuilder build (%s)\n" % args.release
    email += '''\n
    A build flagged for QA (%s) was completed on the autobuilder and is available at:\n\n
        %s\n\n
    Build hash information: \n
    %s

    \nThis is an automated message from the Yocto Project Autobuilder\nGit: git://git.yoctoproject.org/yocto-autobuilder2\nEmail: richard.purdie@linuxfoundation.org\n

    ''' % (args.release, args.publish_dir.replace(web_root, web_url), buildhashes)

    # Store a copy of the email in case it doesn't reach the lists
    with open(os.path.join(args.publish_dir, "qa-email"), "wb") as qa_email:
        qa_email.write(email.encode('utf-8'))

    utils.printheader("Sending QA email")
    env = os.environ.copy()
    # Many distros have sendmail in */sbin
    env["PATH"] = env["PATH"] + ":/usr/sbin:/sbin"
    subprocess.check_call('echo "' + email +' " | sendmail -t', shell=True, env=env)

if __name__ == "__main__":
    send_qa_email()
