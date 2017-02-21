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

    parser.add_option(
        '-j',
        '--job',
        dest='job',
        default='jobId', 
        help=('JobID of the Job you are trying to remove.')
    )

    options, args = parser.parse_args()
    
    opts = {}
    opts['config_file'] = options.config_file; 
    opts['job'] =  options.job

    return opts


if __name__ == '__main__':
    
    options = parse()
    
    settings = loadFile(options['config_file'])
    conn = rpyc.connect('localhost', int(settings['monitor']['port']))
    print "Trying to delete Job ID: %s \n " % options['job']
    conn.root.remove_job(str(options['job'])) 
    print "Remaining Jobs: \n" + str(conn.root.get_jobs())  


