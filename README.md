# AWS-Alarms
Automations to create alarms on CloudWatch

## auto_ec2_alarms.py
Create alarms for EC2

## Prerequisites
- CloudWatch Agent installed and running
- Personalized metrics for Linux:
  - mem_used_percent
  - disk_used_percent

- Personalized metrics for Windows:
  - Memory % Committed Bytes In Use
  - LogicalDisk % Free Space

### This script automatically create the following alarms to Linux and Windows EC2, with CW Agent installed.

### Linux/Windows
- Memory >= 95% during 5 minuts
- CPU 95% >= 95% during 5 minuts
- Disk usage >= 95% during 5 minuts
- StatusCheckFailed >= 1 during 5 minuts

### Parameters needed to execute the script
- region = "us-east-1"  # Replace with your AWS region
- sns_topic_name = "Infrastructure_Topic"  # Replace with your SNS topic name
- instance_ids = []  # Leave empty to filter by tag instance_tag_name: instance_tag_value
- alarm_tag = "gl_monitoring"  # Replace with your TAG for CW-Alarm
- alarm_prefix = "gl" # Replace with your Prefix for alarm
- instance_tag_name = "gl_env"  # Replace with your tag name (e.g. gl_env)
- instance_tag_value = "prod"  # Replace with your tag value (e.g. prod)