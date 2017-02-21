#! /usr/bin/env python

"""
This is the server-side of Open-NTI Alerting tool showing how to make the scheduler into a remotely 
accessible service. It uses RPyC to set up a service through which the scheduler will be in control 
to ad-hoc execute, add (with schedule) and remove jobs.

To run, first install requirements.txt (pip2.7 install -r requirements.txt)

and then run it with ``nohup python server &``.

Then you use the remaining python files to communicate with the server side in scheduling the measurements 
at different intervals. We can run up to 10 Jobs today, each job launched at different interval. 
Each job is bound with measurements file which can have one or more measurements sharing the interval timing. 
"""

import rpyc
import yaml
import json 
import time
import os
import sys
import optparse

from rpyc.utils.server import ThreadedServer
from influxdb import InfluxDBClient
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

import salt.client
from slackclient import SlackClient

# further testing is needed - while trying to eliminate Global variables.
saltCaller = None   # Salt Client used to publish to local salt minion 
sc = None           # Slack Client 
settings = None     # YAML Settings -> Dictionary 
client = None       # Influxdb Python Client 
cachedEvents = None # Cached Events 
_cachedEventsFile = None # Cached Events Tmp file in temp folder 

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

def writeFile(filename, _cachedEvents): 
    '''
    Write dictionary into a YAML file while overriding existing data.   
    '''
    fhandle = open(filename, 'w')
    fhandle.write(yaml.safe_dump(_cachedEvents, default_flow_style=False))
    fhandle.close()
    return True  

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

def generateQuery(measurement):
    '''
    Generates influxdb query out of a measurement 
    '''
    selectables = ','.join(measurement['monitor'])
    query = "select %s from /.*%s.*/ where time > (Now() - %s) group by device;" % (selectables, 
                measurement['measurement'], measurement['timeInterval'])
    return query 

def checkAction(measurement, test, item, key):
    '''
    Checking if action is needed to be taken once an event is matched.  
    '''
    global cachedEvents
    _measureKey = key  ##  liwa.chassis.routing-engine.0.cpu-idle (device + measurement)
    _measure = [key for key in test.keys() if (key!='message')][0]  # "min", "max" 
    _uniqueId = '.'.join([_measureKey,_measure])
    #print _uniqueId
    _rp = measurement['rp']['hold']
    _now = datetime.now()
    #print "Checking Action.. "
    #print "Cached Events(before): %s" % str(cachedEvents)
    if _uniqueId in cachedEvents.keys():
        _timeStamp = cachedEvents[_uniqueId] 
        if ((_now - _timeStamp).total_seconds()/60) > float(_rp): # if time is higher than hold time 
            cachedEvents[_uniqueId] = _now 
        else: 
            return None # don't take any action 
    else:
        cachedEvents[_uniqueId] = _now
    
    #print "Cached Events(after): %s" % str(cachedEvents)

    _event = {}
    _event['measurement'] = _measureKey
    _event['device'] = _measureKey.split('.')[0]
    _event['monitoredKpi'] = _measure
    _event['message'] = test['message']
    _event['timeStamp'] = _now.strftime("%Y-%m-%d %I:%M:%S %p") 
    
    # Fire an action after verifying hold-timer has expired. 
    fireAction(measurement, _event)

    return _event 

def fireAction(measurement, event):
    '''
    Firing actions with event to differnet channels, after hold-timer has expired.  
    '''
    global cachedEvents
    actions = measurement['action']
    print "Firing Action.. "
    for action in actions: 
        _actionName = action.keys()[0]
        if action[_actionName]['enable']: 
            if _actionName == 'salt': 
                saltCaller = salt.client.Caller()
                if saltCaller == None: 
                    saltCaller = salt.client.Caller()
                try:
                    if 'tagPrefix' in action[_actionName].keys():
                        tag = action[_actionName]['tagPrefix'] 
                    else: 
                        tag = '/jnpr/opennti/' + mesurement.keys()[0]
                    
                    print "Sending event to Salt!"
                    saltCaller.sminion.functions['event.send']( tag, event)
                except:
                    print "Error while sending Salt Event!"
            elif _actionName == 'slack':
                print "Sending event to slack!"
                sc.api_call(
                      "chat.postMessage",
                      channel= action[_actionName]['channel'],
                      text=str(event)
                    ) 

def testMeasurement(measurement, result):
    '''
    Testing measurements rules and invoking checkAction if matching.  
    '''
    global cachedEvents
    measurementKeys = result.keys()
    #print "Testing Measurement.. "

    for test in measurement['test']: 
        for key, value in test.items():
            if key not in ('message'):
                i=0 # used for indexing measurementKeys
                for item in result.get_points():
                    if key in item.keys(): 
                        # now key and item[key] has min: 62 (as value)
                        testOp, testValue = test[key].split(' ')
                        testMatch = False 
                        if testOp == 'lt':
                            testMatch = float(item[key]) < float(testValue)
                        elif testOp == 'gt':
                            testMatch = float(item[key]) > float(testValue)
                        elif testOp == 'lte':
                            testMatch = float(item[key]) <= float(testValue)
                        elif testOp == 'gte':
                            testMatch = float(item[key]) >= float(testValue)
                        elif testOp == 'eq':
                            testMatch = float(item[key]) == float(testValue) 
                        
                        if testMatch == True:
                            checkAction(measurement, test, item, measurementKeys[i][0])
                    i += 1 


def executeMeasurements(fileName, configFile):
    '''
    Executing list of measurements and invoking testMeasurement for each measurement.  
    This is the function used by APScheduler. 
    '''
    global client 
    global sc 
    global saltCaller 
    global cachedEvents
    global _cachedEventsFile
    settings = loadFile(configFile)
    _cachedEventsFile = settings['temp']['folder'] + fileName + '.tmp'

    client = InfluxDBClient(settings['influxdb']['ip'], 
                        settings['influxdb']['port'], 
                        settings['influxdb']['user'],
                        settings['influxdb']['password'],
                        settings['influxdb']['db'])
    
    if os.path.isfile(_cachedEventsFile):
        cachedEvents = loadFile(_cachedEventsFile)
    else: 
        cachedEvents = {}

    if 'slack' in settings.keys():
        sc = SlackClient(settings['slack']) 

    saltCaller = salt.client.Caller()

    measurements = loadFile(fileName)
    print "Executing Measurements: %s \n" % ','.join(measurements.keys())

    for measurement in measurements.keys():
        query=generateQuery(measurements[measurement])
        #print "sending Query: %s " % query 
        result = client.query(query)
        #print "Result: %s" % str(result.raw)  
        testMeasurement(measurements[measurement], result)

    writeFile(_cachedEventsFile, cachedEvents)

def showMeasurement(fileName):
    '''
    Executing an ad-hoc measurements results without testing and without taking any actions.  
    '''
    measurements = loadFile(fileName)
    print "Measuring.. \n"
    ret = ""
    for measurement in measurements.keys():
        query=generateQuery(measurements[measurement])
        result = client.query(query)
        keys = result.keys()
        i = 0
        gen = result.get_points()
        
        for item in gen:
            ret += "Device: %s, Measurement: %s): \n %s \n" % (keys[i][1]['device'],keys[i][0], str(item)) 
            # print "Device: %s, Measurement: %s): \n" % (keys[i][1]['device'],keys[i][0]) + str(item) 
            i+=1
    return ret 

class SchedulerService(rpyc.Service):
    '''
    Main Class Scheduler for scheduling measurements or executing ad-hoc command.  
    '''
    def exposed_add_job(self, func, *args, **kwargs):
        print "Adding a new job.."
        return scheduler.add_job(func, *args, **kwargs)

    def exposed_modify_job(self, job_id, jobstore=None, **changes):
        return scheduler.modify_job(job_id, jobstore, **changes)

    def exposed_reschedule_job(self, job_id, jobstore=None, trigger=None, **trigger_args):
        return scheduler.reschedule_job(job_id, jobstore, trigger, **trigger_args)

    def exposed_pause_job(self, job_id, jobstore=None):
        return scheduler.pause_job(job_id, jobstore)

    def exposed_resume_job(self, job_id, jobstore=None):
        return scheduler.resume_job(job_id, jobstore)

    def exposed_remove_job(self, job_id, jobstore=None):
        scheduler.remove_job(job_id, jobstore)

    def exposed_showMeasurement(self, fileName):
        return showMeasurement(fileName) 

    def exposed_get_job(self, job_id):
        return scheduler.get_job(job_id)

    def exposed_get_jobs(self, jobstore=None):
        return scheduler.get_jobs(jobstore)


if __name__ == '__main__':
    
    options = parse()
    
    settings = loadFile(options['config_file'])
    
    client = InfluxDBClient(settings['influxdb']['ip'], 
                        settings['influxdb']['port'], 
                        settings['influxdb']['user'],
                        settings['influxdb']['password'],
                        settings['influxdb']['db'])
    
    if 'slack' in settings.keys():
        sc = SlackClient(settings['slack']) 

    saltCaller = salt.client.Caller()

    scheduler = BackgroundScheduler()
    
    scheduler.start()
    
    protocol_config = {'allow_public_attrs': True}
    
    print "OpenNTI Monitor is being laucnhed and will be accessible via rpyc port: %s \n" % settings['monitor']['port']
    
    server = ThreadedServer(SchedulerService, port=settings['monitor']['port'], protocol_config=protocol_config)
    
    try:
        server.start()

    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
        