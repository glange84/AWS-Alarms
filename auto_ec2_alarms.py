import boto3
from botocore.config import Config
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create file handler for logging to a file
file_handler = logging.FileHandler('ec2_alarms.log')
file_handler.setLevel(logging.INFO)

# Create a stream handler for logging to the console
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

# Create a formatter and set it for both handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Add both handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Configure boto3 with retries and timeouts
boto3_config = Config(
    retries=dict(
        max_attempts=3,
        mode='standard'
    ),
    connect_timeout=5,
    read_timeout=10
)

def get_sns_topic_arn(topic_name: str, region: str) -> str:
    """Get SNS topic ARN with pagination support."""
    sns_client = boto3.client('sns', region_name=region, config=boto3_config)
    paginator = sns_client.get_paginator('list_topics')

    try:
        for page in paginator.paginate():
            for topic in page.get('Topics', []):
                if topic_name in topic['TopicArn']:
                    return topic['TopicArn']
        raise ValueError(f"Topic '{topic_name}' not found in region {region}")
    except Exception as e:
        logger.error(f"Error finding SNS topic: {str(e)}")
        raise

def tag_alarm(cloudwatch_client, alarm_name: str, tags: List[Dict[str, str]]) -> None:
    """Add tags to a CloudWatch alarm."""
    try:
        cloudwatch_client.tag_resource(
            ResourceARN=f"arn:aws:cloudwatch:{cloudwatch_client.meta.region_name}:{boto3.client('sts').get_caller_identity()['Account']}:alarm:{alarm_name}",
            Tags=tags
        )
        logger.info(f"Tags added to alarm {alarm_name}: {tags}")
    except Exception as e:
        logger.error(f"Failed to tag alarm {alarm_name}: {str(e)}")

def create_cloudwatch_alarm_batch(cloudwatch_client, alarms_config: List[Dict]) -> None:
    """Create multiple CloudWatch alarms individually and tag them."""
    for alarm_config in alarms_config:
        try:
            # Create each alarm individually
            cloudwatch_client.put_metric_alarm(**alarm_config)
            logger.info(f"Successfully created alarm: {alarm_config['AlarmName']}")

            # Add tags to the alarm
            tag_alarm(
                cloudwatch_client,
                alarm_config['AlarmName'],
                tags=[
                    {'Key': alarm_tag, 'Value': datetime.utcnow().strftime('%Y-%m-%d')}
                ]
            )
        except Exception as e:
            logger.error(f"Error creating or tagging alarm {alarm_config['AlarmName']}: {str(e)}")

def process_instance(instance: Dict, account_alias: str, sns_topic_arn: str, region: str) -> List[Dict]:
    """Process a single EC2 instance and return its alarm configurations."""
    instance_id = instance['InstanceId']
    instance_type = instance['InstanceType']
    instance_name = next((tag['Value'] for tag in instance.get('Tags', []) 
                         if tag['Key'] == 'Name'), 'UnnamedInstance')
    image_id = instance.get('ImageId', 'UnknownImage')
    
    # Identify SO
    platform = instance.get('Platform', 'linux').lower()  # Return 'windows' or 'linux'.
    
    alarm_configs = []
    base_alarm = {
        'ActionsEnabled': True,
        'AlarmActions': [sns_topic_arn],
        'OKActions': [sns_topic_arn],
        'Statistic': 'Average',
        'Period': 60,
        'EvaluationPeriods': 5,
        'TreatMissingData': 'breaching'
    }

    # Status Check Alarm
    alarm_configs.append({
        **base_alarm,
        'AlarmName': f"{alarm_prefix}_{account_alias}_ec2_{instance_name}_status-check",
        'MetricName': 'StatusCheckFailed',
        'Namespace': 'AWS/EC2',
        'Dimensions': [{'Name': 'InstanceId', 'Value': instance_id}],
        'Threshold': 1,
        'ComparisonOperator': 'GreaterThanOrEqualToThreshold'
    })

    # CPU Utilization Alarm
    alarm_configs.append({
        **base_alarm,
        'AlarmName': f"{alarm_prefix}_{account_alias}_ec2_{instance_name}_cpu-used",
        'MetricName': 'CPUUtilization',
        'Namespace': 'AWS/EC2',
        'Dimensions': [{'Name': 'InstanceId', 'Value': instance_id}],
        'Threshold': 95,
        'ComparisonOperator': 'GreaterThanOrEqualToThreshold'
    })

    # Add alarms for Linux (CWAgent)
    if platform == 'linux':
        metrics_client = boto3.client('cloudwatch', region_name=region, config=boto3_config)
        metrics = metrics_client.list_metrics(
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            Namespace='CWAgent'
        )
        metrics_available = metrics.get('Metrics', [])

        for metric in metrics_available:
            metric_name = metric['MetricName']
            dimensions = metric['Dimensions']

            if metric_name == 'mem_used_percent':
                alarm_configs.append({
                    **base_alarm,
                    'AlarmName': f"{alarm_prefix}_{account_alias}_ec2_{instance_name}_mem-used",
                    'MetricName': metric_name,
                    'Namespace': 'CWAgent',
                    'Dimensions': dimensions,
                    'Threshold': 95,
                    'ComparisonOperator': 'GreaterThanOrEqualToThreshold'
                })

            if metric_name == 'disk_used_percent':
                for dimension in dimensions:
                    if dimension['Name'] == 'path' and dimension['Value'] == '/':
                        alarm_configs.append({
                            **base_alarm,
                            'AlarmName': f"{alarm_prefix}_{account_alias}_ec2_{instance_name}_disk-used",
                            'MetricName': metric_name,
                            'Namespace': 'CWAgent',
                            'Dimensions': dimensions,
                            'Threshold': 95,
                            'ComparisonOperator': 'GreaterThanOrEqualToThreshold'
                        })

    # Add alarms for Windows
    elif platform == 'windows':
        # Mem alarm for Windows
        alarm_configs.append({
            **base_alarm,
            'AlarmName': f"{alarm_prefix}_{account_alias}_ec2_{instance_name}_mem-used",
            'MetricName': 'Memory % Committed Bytes In Use',
            'Namespace': 'CWAgent',
            'Dimensions': [
                {'Name': 'InstanceId', 'Value': instance_id},
                {'Name': 'ImageId', 'Value': image_id},
                {'Name': 'objectname', 'Value': 'Memory'},
                {'Name': 'InstanceType', 'Value': instance_type}
            ],
            'Threshold': 95,
            'ComparisonOperator': 'GreaterThanOrEqualToThreshold'
        })
        
        # Disk Alarm for Windows (C:)
        alarm_configs.append({
            **base_alarm,
            'AlarmName': f"{alarm_prefix}_{account_alias}_ec2_{instance_name}_disk-used",
            'MetricName': 'LogicalDisk % Free Space',
            'Namespace': 'CWAgent',
            'Dimensions': [
                {'Name': 'InstanceId', 'Value': instance_id},
                {'Name': 'ImageId', 'Value': image_id},
                {'Name': 'objectname', 'Value': 'LogicalDisk'},
                {'Name': 'InstanceType', 'Value': instance_type},
                {'Name': 'instance', 'Value': 'C:'} 
            ],
            'Threshold': 5,  # % of free space
            'ComparisonOperator': 'LessThanOrEqualToThreshold'
        })

    return alarm_configs

def create_ec2_alarms(region: str, sns_topic_name: str, instance_ids: List[str], instance_tag_name: str, instance_tag_value: str) -> None:
    """Create EC2 alarms with optimized batch processing."""
    session = boto3.Session(region_name=region)
    ec2_client = session.client('ec2', config=boto3_config)
    cloudwatch_client = session.client('cloudwatch', config=boto3_config)
    iam_client = session.client('iam', config=boto3_config)

    # Get account alias
    account_alias = iam_client.list_account_aliases().get('AccountAliases', ['default-account'])[0]

    # Get SNS topic ARN
    sns_topic_arn = get_sns_topic_arn(sns_topic_name, region)

    # Get instance details in batches
    paginator = ec2_client.get_paginator('describe_instances')
    all_alarm_configs = []

    # Validate that either instance_ids or instance_tag_name and instance_tag_value is provided
    if not instance_ids and (not instance_tag_name or not instance_tag_value):
        raise ValueError("You must provide either instance_ids or both instance_tag_name and instance_tag_value.")

    # If no specific instance IDs are provided, filter by the tag instance_tag_name: instance_tag_value
    if not instance_ids:
        filters = [{'Name': f'tag:{instance_tag_name}', 'Values': [instance_tag_value]}]
        paginator = ec2_client.get_paginator('describe_instances')
        for page in paginator.paginate(Filters=filters):
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        futures.append(
                            executor.submit(
                                process_instance,
                                instance,
                                account_alias,
                                sns_topic_arn,
                                region
                            )
                        )

                for future in futures:
                    all_alarm_configs.extend(future.result())
    else:
        for page in paginator.paginate(InstanceIds=instance_ids):
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        futures.append(
                            executor.submit(
                                process_instance,
                                instance,
                                account_alias,
                                sns_topic_arn,
                                region
                            )
                        )

                for future in futures:
                    all_alarm_configs.extend(future.result())

    # Create alarms in batches of 10
    batch_size = 10
    for i in range(0, len(all_alarm_configs), batch_size):
        batch = all_alarm_configs[i:i + batch_size]
        create_cloudwatch_alarm_batch(cloudwatch_client, batch)

if __name__ == "__main__":
    region = "us-east-1"  # Replace with your AWS region
    sns_topic_name = "Infrastructure_Topic"  # Replace with your SNS topic name
    instance_ids = []  # Leave empty to filter by tag instance_tag_name: instance_tag_value
    alarm_tag = "gl_monitoring"  # Replace with your TAG for CW-Alarm
    alarm_prefix = "gl" # Replace with your Prefix for alarm
    instance_tag_name = "gl_env"  # Replace with your tag name (e.g. gl_env)
    instance_tag_value = "prod"  # Replace with your tag value (e.g. prod)

    try:
        create_ec2_alarms(region, sns_topic_name, instance_ids, instance_tag_name, instance_tag_value)
        logger.info("Alarms created successfully.")
    except Exception as e:
        logger.error(f"Error creating alarms: {str(e)}")