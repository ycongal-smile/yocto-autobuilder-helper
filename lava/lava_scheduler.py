#!/usr/bin/env python3
'''
author__ = "Aaron Chan"
__copyright__ = "Copyright 2018, Intel Corp"
__credits__" = ["Aaron Chan"]
__license__" = "GPL"
__version__" = "1.0"
__maintainer__ = "Aaron Chan"
__email__ = "aaron.chun.yew.chan@intel.com"
'''

import xmlrpc

class scheduler():

    def __init__(self, server, user, token, url):
        self.server = server
        self.user = user
        self.token = token
        self.url = url

    @classmethod
    # Description: Submit the given job data which is in LAVA
    #              job JSON or YAML format as a new job to
    #              LAVA scheduler.
    # Return: dict <type>
    def lava_jobs_submit(self, server, data):
        return server.scheduler.jobs.submit(data)

    @classmethod
    # Description: Cancel the given job referred by its id
    # Return: Boolean <type>
    def lava_jobs_cancel(self, server, jobid):
        state = server.scheduler.jobs.cancel(jobid)
        if type(state) is bool: return state

    @classmethod
    def lava_jobs_resubmit(self, server, jobid):
        return server.scheduler.jobs.resubmit(jobid)

    @classmethod
    # Description: Return the logs for the given job
    # Args: jobid <str>, line <int> - Show only after the given line
    # Return: tuple <type>
    def lava_jobs_logs(self, server, jobid, line):
        return server.scheduler.jobs.logs(jobid, line)
    
    @classmethod
    # Description: Show job details
    # Return: Dict <type>
    def lava_jobs_show(self, server, jobid):
        return server.scheduler.jobs.show(jobid)

    @classmethod
    # Description: Return the job definition
    # Return: Instance <type>
    def lava_jobs_define(self, server, jobid):
        return server.scheduler.jobs.definition(jobid)

    @classmethod
    def lava_jobs_status(self, server, jobid):
        return server.scheduler.job_status(jobid)

    @classmethod
    def lava_jobs_output(self, server, jobid, offset):
        return server.scheduler.job_output(jobid, offset)

    @classmethod
    def lava_jobs_details(self, server, jobid):
        return server.scheduler.job_details(jobid)
