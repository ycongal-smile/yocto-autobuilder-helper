#!/usr/bin/env python3
#
# SPDX-License-Identifier: GPL-2.0-only
#
#Signed-off-by: Abongwa Bonalais Amahnui <abongwabonalais@gmail.com>
#
#
# Script to add banners to the old docs and outdated dunfell docs
#
#

import os

html_content_dunfell = '''
<div id="outdated-warning">This document is outdated, you should select the <a href="https://docs.yoctoproject.org/dunfell">latest release version</a> in this series.</div>
<div xml:lang="en" class="body" lang="en">
'''
html_content = '''
<div id="outdated-warning">This version of the project is now considered obsolete, please select and use a <a href="https://docs.yoctoproject.org">more recent version</a>.</div>
<div xml:lang="en" class="body" lang="en">
'''

# the class body and the last_div are used to make sure any .body property existing in any css file is not overwritten
last_div = '''
</div>

'''

css_replacement_content = '''

  font-family: Verdana, Sans, sans-serif;

  width: 100%;
  margin:  0;
  padding: 0;
  color: #333;
  overflow-x: hidden;
  }

.body{
margin:  0 auto;
min-width: 640px;
padding: 0 5em 5em 5em;
}
#outdated-warning{
text-align: center;
background-color: rgb(255, 186, 186);
color: rgb(106, 14, 14);
padding: 0.5em 0;
width: 100%;
position: fixed;
top: 0;


'''


def add_banner_old_docs(dir):
    for root, dirs, filenames in os.walk(dir):

        if root.startswith('./3.1'):
            html_replacement = html_content_dunfell
        else:
            html_replacement = html_content

        for filename in filenames:
            fullfile = os.path.join(root, filename)
            if os.path.islink(fullfile):
                continue
            if filename.endswith('.html'):
                with open(fullfile, 'r', encoding="ISO-8859-1") as f:
                    current_content = f.read()
                with open(fullfile, 'w', encoding="ISO-8859-1") as f:
                    f.write(current_content.replace('<body>', '<body>' + html_replacement).replace('</body>', last_div + '</body>'))
            elif filename.endswith('.css'):
                with open(fullfile, 'r', encoding="ISO-8859-1") as f:
                    css_content = f.read()
                with open(fullfile, 'w', encoding="ISO-8859-1") as f:
                    f.write(css_content.replace(css_content[css_content.find('body {'):css_content.find('}'[0])], 'body {' + css_replacement_content ))

add_banner_old_docs('.')
