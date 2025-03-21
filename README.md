# AWS-Alarms
Automations to create alarms on CloudWatch to resources

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
