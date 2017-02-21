# Basic Open-NTI Monitoring Utility - with Salt & Slack Alerts

 This project generates Alerts based on user-configurable contraints of measurement collected from Juniper Open-NTI (https://github.com/Juniper/open-nti) through Influxdb Python API, and provides Salt Event and / or Slack Updates accordingly, based on user-configurable channel(s).

 First version of this script will be focused on running it on the docker-saltstack-junos (https://github.com/Juniper/docker-saltstack-junos), as a stand-alone script, which could be launched with minimal settings within the saltmaster docker container. 

## Installation 

 Once you deployed docker-saltstack-junos (https://github.com/Juniper/docker-saltstack-junos), login to master shell via: 

```
> make master-shell 
> cd ~
> git clone https://github.com/hkarhani/open-nti-mon.git 
> cd open-nti-mon/
```

### 1. First edit settings.yaml file: 

```
monitor:
    port: 8181         # default port to communicate with via RPyC. 

influxdb: 
    ip: '10.0.0.22'		# change ip to match your open-nti host-ip 
    port: 8086 
    user: 'juniper' 
    password: 'juniper'
    db: 'juniper' 
    
slack: <Your Slack botID>  		# example: slack: xoxb-1234567565-NIsC7aJNej7LKGQeQFYfCy3D
								# or you can delete slack if you don't plan to enable slack integration 

								# by default we will use the salt-settings of the host - so no need to 
								# configure additional settings for salt-integration. 

This file is implicitely loaded while running the server-side of open-nti-monitor tool. 
```

### Second: Create or edit measurements files:
``` 
<measurement_name>
	<settings> 			#as explained below. 

Example: 

-------------- single measurement definition -------------------
cpu_idle: 						          # measurement identification - should be unique! 
    measurement: 'cpu-idle'     # measurement as /.*measurement.*/
    
    timeInterval: '1h'          # This is the measurement time (now()-timerInterval) 
    							              # last 1h, 5m or 1d, etc.. 
    
    monitor: 					          # choose what to monitor 
      - min(value)              # choose value, or any function supported by influxdb select  
      - mean(value)				      # such as min, max, mean, etc.. throughout last timeInterval. 
    
    test: 
      - min: 'lt 20'			      # monitored value function to be compared (lt, lte, gt, gte, eq)
        message: 'cpu-idle during the last 1h reached less than 20%!' 
      - mean: 'lt 40'
        message: 'cpu-idle average over the last 1h is less than 40%!'
    rp: 
      hold: 30               	# in minutes - don't take action as long as event 
                             	# is sent during hold period for that specific "measurement" 
                             	# i.e. per device / measurement / monitored value  
    action:       				    # Take Action - today salt and/or slack 
      - salt: 					      # salt-selected 
           enable: true      	# Mandatory! either true or false if action name exists 
           tagPrefix: /jnpr/opennti/cpu_idle    # tag to be used while issuing event for this test
           										# device name will be passed in event data  
           
      - slack:					      # slack-selected
           enable: true 		  # Mandatory! either true or false if action name exists 
           channel: '#automation' 	# chat-room name on slack while issuing event for this test
----------------- end of definition ------------------
```

You can have as many measurements as you want, few suggestions: 
```
	memory-buffer-utilization
	fabric-discard
	down-peer-count
	routes
	software-input-high-drops
  etc..
```

Functions which can be used within influxdb queries: 
```
count, min, max, mean, distinct, median, mode, percentiles, derivative, stddev
````
### 3. Launch script as process:
```
	> nohup python server.py &		# or you can specify explicitely '-c or --config settings.yaml' 

	> ./get_measurement.py -f measurement.yaml # Ad-hoc measuremnts results visulization
  
  > ./add_job.py -i 10 -f measurement.yaml 	# Add Job for measurements each 10seconds in Scheduler 
	  <job-id> is returned
	
	if you wish to stop the job: 
	> ./remove_job.py -j <job-id> 
	
	To monior the jobs ids: 
	> ./list_jobs.py  
```

Now you can monitor your slack channel or salt-events bus (salt-run state.event pretty=True) for Monitored measurements Events. 

## Release History

* 0.0.1
    * 20.FEB.2017: Initial Script with base functionalities.   