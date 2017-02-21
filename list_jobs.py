#! /usr/bin/env python

from time import sleep

import rpyc
import yaml
import os
import sys
import optparse

def loadFile(filename):
    '''
    Load YAML file into a dictionary 
    '''
    if os.path.isfile(filename):
        fhandle = open(filename, 'r')
        content = yaml.safe_load(fhandle.read())
        fhandle.close()
        return content 
    else: 
        return None 

def parse():
    '''
    Parse the script command line inputs
    '''
    parser = optparse.OptionParser()

    parser.add_option(
        '-c',
        '--config',
        dest='config_file',
        default='settings.yaml',
        help=('YAML configurator file of OpenNTI Monitor.')
    )

    options, args = parser.parse_args()
    opts = {}
    opts['config_file'] = options.config_file; 

    return opts


if __name__ == '__main__':
    
    # parsing args
    options = parse()

    # loading settings - default file is "settings.yaml" 
    settings = loadFile(options['config_file'])

    # connect to rpyc server - on specified file in settings 
    conn = rpyc.connect('localhost', int(settings['monitor']['port']))
    
    # retrieve jobs list    
    jobs = conn.root.get_jobs()
    
    # Printing total number of running Jobs 
    print "Total of %i Job(s) found." % len(jobs) 

    # Iterate through Jobs and display their JobId and invoke timing 
    for job in jobs: 
        print "JobID: %s \n %s\n" % (job.id, job) 