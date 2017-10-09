# Devops-Tools
Create Alarms for EC2 Loadbalancers

Create the following alarms for all EC2 Application Loadbalancers in AWS. Some assumptions:
 1. The script should run through all the active load balancers in AWS and should create the alarms.
 2. Any alarms which already exists or manually created for a Load balancer should be skipped.
 3. The Alarm action should send a message to SNS topic and SNS will publish the message to HTTP endpoint ex: https://requestb.in
 4. Create alarms for metrics
    * TargetResponseTime if average latency exceeds 1.0 s
    * HTTPCode_Target_4XX_Count if count of 4xx codes exceeds 20
    * HTTPCode_Target_5XX_Count if count of 5xx codes exceeds 20
 
 
