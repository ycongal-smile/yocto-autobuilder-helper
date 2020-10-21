#!/usr/bin/env python3
#
# Copyright (c) 2019, Linux Foundation
#
# SPDX-License-Identifier: GPL-2.0-only
#

import argparse
import os
import glob
import json
import subprocess
from jinja2 import Template

index_templpate = """
<h1>Index of autobuilder test results</h1>
    
<table>
<tr>
  <td>Build</td>     
  <td>Type</td>
  <td>Branch</td>
  <td>Report</td>
  <td>Buildhistory</td>
</tr>
{% for entry in entries %}
<tr>
   <td><a href="{{entry[1]}}">{{entry[0]}}</a></td>
   <td>{% if entry[2] %} {{entry[2]}}{% endif %}</td>
   <td>{% if entry[4] %} {{entry[4]}}{% endif %}</td>
   <td> {% if entry[3] %}<a href="{{entry[3]}}">Report</a>{% endif %} </td>
   <td>
   {% for bh in entry[5] %}
     <a href="{{bh[0]}}">{{bh[1]}}</a>
   {% endfor %}
   </td>
</tr>
{% endfor %}
</table>
"""

def parse_args(argv=None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
            description="Generate an html index for a directory of autobuilder results",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('path', help='path to directory to index')

    return parser.parse_args(argv)

args = parse_args()
path = os.path.abspath(args.path)
entries = []

def get_build_branch(p):
    for root, dirs, files in os.walk(p):
        for name in files:
            if name == "testresults.json":
                f = os.path.join(root, name)
                with open(f, "r") as filedata:
                    data = json.load(filedata)
                for build in data:
                    try:
                        return data[build]['configuration']['LAYERS']['meta']['branch']
                    except KeyError:
                        continue 

    return ""

# Pad so 20190601-1 becomes 20190601-000001 and sorts correctly
def keygen(k):
    if "-" not in k:
         return k
    k1, k2 = k.split("-")
    return k1 + "-" + k2.rjust(6, '0')

for build in sorted(os.listdir(path), key=keygen, reverse=True):
    buildpath = os.path.join(path, build, "testresults")
    if not os.path.exists(buildpath):
        # No test results
        continue
    reldir = "./" + build + "/testresults/"
    btype = "other"
    files = os.listdir(buildpath)
    if os.path.exists(buildpath + "/a-full-posttrigger") or \
            os.path.exists(buildpath + "/a-full"):
        btype = "full"
    elif os.path.exists(buildpath + "/a-quick-posttrigger") or \
            os.path.exists(buildpath + "/a-quick"):
        btype = "quick"
    elif len(files) == 1:
        btype = files[0]
    testreport = ""
    if os.path.exists(buildpath + "/testresult-report.txt"):
        testreport = reldir + "testresult-report.txt"
    elif btype.startswith("buildperf-"):
        try:
            testreport = reldir + btype + "/" + os.path.basename(glob.glob(buildpath + "/" + btype + "/*.html")[0])
        except IndexError:
            pass

    buildhistory = []
    if os.path.exists(buildpath + "/qemux86-64/buildhistory.txt"):
        buildhistory.append((reldir + "/qemux86-64/buildhistory.txt", "qemux86-64"))

    if os.path.exists(buildpath + "/qemuarm/buildhistory.txt"):
        buildhistory.append((reldir + "/qemuarm/buildhistory.txt", "qemuarm"))

    branch = get_build_branch(buildpath)

    entries.append((build, reldir, btype, testreport, branch, buildhistory))

    # Also ensure we have saved out log data for ptest runs to aid debugging
    if "ptest" in btype or btype in ["full", "quick"]:
        for root, dirs, files in os.walk(buildpath):
            for name in dirs:
                if "ptest" in name:
                    f = os.path.join(root, name)
                    logs = glob.glob(f + "/*.log")
                    if logs:
                        continue
                    subprocess.check_call(["resulttool", "log", f, "--dump-ptest", f])

t = Template(index_templpate)
with open(os.path.join(path, "index.html"), 'w') as f:
    f.write(t.render(entries = entries))
