# -*- coding: utf-8 -*-
#
# Python script to manage load balancer alarms on AWS
#
# Pre-requisite: Requires boto3 package
# http://boto3.readthedocs.io/en/latest/guide/quickstart.html
#
# Usage: python <script-name>
#


from boto3 import client
from boto3 import resource

# AWS keys
AWS_ACCESS_KEY = '<Your-key>'
AWS_SECRET_ACCESS_KEY = '<Your-secret>'

# Alarm constants
ALARM_NAMESPACE = 'AWS/ApplicationELB'
ALARM_TargetResponseTime = 'TargetResponseTime'
ALARM_HTTPCode_Target_4XX_Count = 'HTTPCode_Target_4XX_Count'
ALARM_HTTPCode_Target_5XX_Count = 'HTTPCode_Target_5XX_Count'

# SNS Topic
TOPIC_NAME = 'LoadBalancer_Alarm_Notification'
TOPIC_ARN = 'arn:aws:sns:us-east-1:643234842159:LoadBalancer_Alarm_Notification'
SNS_ENDPOINT = 'https://requestb.in/oyry32oy'

# Load Balancer states
ELB_STATES = ('active', 'provisioning', 'active_impaired')


def get_client(service_name):
    return client(
        service_name,
        aws_access_key_id = AWS_ACCESS_KEY,
        aws_secret_access_key = AWS_SECRET_ACCESS_KEY,
        region_name = 'us-east-1',
    )

def get_resource(service_name):
    return resource(
        service_name,
        aws_access_key_id = AWS_ACCESS_KEY,
        aws_secret_access_key = AWS_SECRET_ACCESS_KEY,
        region_name = 'us-east-1',
    )

# check if an alarm with metric already exists on this load balancer
def is_alarm_enabled(metric_name, elb_path, cw):
    cw_alarms = filter(
        lambda x: x.namespace == ALARM_NAMESPACE and \
            x.metric_name == metric_name and \
            x.dimensions[0]['Name'] == 'LoadBalancer' and \
            x.dimensions[0]['Value'] == elb_path,
            cw.alarms.all()
    )

    return len(cw_alarms) > 0

# create SNS topic and subscribe to HTTPS endpoint
def create_sns_notification(topic, url):
    resp = client.create_topic(Name=topic)
    topic_arn = resp['TopicArn']
    # topic_arn -> arn:aws:sns:us-east-1:643234842159:LoadBalancer_Alarm_Notification
    resp = client.subscribe(
        TopicArn=topic_arn,
        Protocol='https',
        Endpoint=url
    )

    return

# wait until alarm exists, else throw exception
def wait_for_alarm_exists(client, name):
    waiter = client.get_waiter('alarm_exists')
    # wait for alarm to reach OK state
    try:
        waiter.wait(
            AlarmNames=[name],
            StateValue='OK',
            WaiterConfig={
                'Delay': 5,
                'MaxAttempts': 120
            }
        )
    except Exception as ex:
        print ex

    return

# create alarm for Response time latency
def create_response_time_alarm(client, name, elb):
    response = client.put_metric_alarm(
        AlarmName=name,
        AlarmDescription='Alarm whenever the latency exceeds 1s.',
        ActionsEnabled=True,
        AlarmActions=[TOPIC_ARN],
        MetricName=ALARM_TargetResponseTime,
        Namespace=ALARM_NAMESPACE,
        Statistic='Average',
        Dimensions=[
            {
                'Name': 'LoadBalancer',
                'Value': elb,
            }
        ],
        Period=60,
        Threshold=1.0,
        EvaluationPeriods=1,
        ComparisonOperator='GreaterThanThreshold',
        TreatMissingData='missing',
    )
    
    wait_for_alarm_exists(client, name)

    return response

# create alarm for HTTP 4xx and 5xx count
def create_http_repsonse_code_count_alarm(client, name, description, metric_name, elb):
    response = client.put_metric_alarm(
        AlarmName=name,
        AlarmDescription=description,
        ActionsEnabled=True,
        AlarmActions=[TOPIC_ARN],
        MetricName=metric_name,
        Namespace=ALARM_NAMESPACE,
        Statistic='Sum',
        Dimensions=[
            {
                'Name': 'LoadBalancer',
                'Value': elb,
            }
        ],
        Period=60,
        Threshold=20,
        Unit='Count',
        EvaluationPeriods=1,
        ComparisonOperator='GreaterThanThreshold',
        TreatMissingData='missing',
    )

    wait_for_alarm_exists(client, name)

    return response


def main():
    elb_client = get_client('elbv2')
    cw_client = get_client("cloudwatch")
    cw_resource = get_resource('cloudwatch')
    sns_client = get_client('sns')
    
    try:
        # SNS topic create and subscribing topic to endpoints is already complete. 
        # create_sns_notification(sns_client, topic=TOPIC_NAME, url=SNS_ENDPOINT)

        # iterate all ELB's in the system
        for elb in elb_client.describe_load_balancers()['LoadBalancers']:
            # create alarms for ELB's
            if elb.get('State') and elb['State']['Code'] in ELB_STATES:
                elb_arn = elb.get('LoadBalancerArn')
                elb_path = elb_arn.rsplit(':', 1)[-1]
                elb_path = elb_path.split('/', 1)[-1]
                elb_name = elb.get('LoadBalancerName')

                print "ELB path is %s" % elb_path
                print "--------------------------"
                
                if not is_alarm_enabled(ALARM_TargetResponseTime, elb_path, cw_resource):
                    print "Creating {0} alarm for {1}".format(ALARM_TargetResponseTime, elb_path)
                    res = create_response_time_alarm(
                        cw_client, 
                        name=elb_name+'-ResponseTime', 
                        elb=elb_path
                    )
                    print "Alarm created"

                if not is_alarm_enabled(ALARM_HTTPCode_Target_4XX_Count, elb_path, cw_resource):
                    print "Creating {0} alarm for {1}".format(ALARM_HTTPCode_Target_4XX_Count, elb_path)
                    res = create_http_repsonse_code_count_alarm(
                        cw_client, 
                        name=elb_name+'-HTTPCode_4XX_Count',
                        description='Alarm whenever count of HTTP status code 4XX exceeds 20',
                        metric_name=ALARM_HTTPCode_Target_4XX_Count,
                        elb=elb_path
                    )
                    print "Alarm created"

                if not is_alarm_enabled(ALARM_HTTPCode_Target_5XX_Count, elb_path, cw_resource):
                    print "Creating {0} alarm for {1}".format(ALARM_HTTPCode_Target_5XX_Count, elb_path)
                    res = create_http_repsonse_code_count_alarm(
                        cw_client, 
                        name=elb_name+'-HTTPCode_5XX_Count',
                        description='Alarm whenever count of HTTP status code 5XX exceeds 20',
                        metric_name=ALARM_HTTPCode_Target_5XX_Count,
                        elb=elb_path
                    )
                    print "Alarm created"

    except Exception as ex:
        print ex 


if __name__ == '__main__':
    main()


