# AWS-Alarms
Automations to create alarms on CloudWatch to resources

## Prerequisites
- CloudWatch Agent installed and running
- Personalized metrics for Linux:
  - mem_used_percent
  - disk_used_percent

- Personalized metrics for Windows:
  - Memory % Committed Bytes In Use
  - LogicalDisk % Free Space


## auto_ec2_alarms.py
Create default alarms for EC2
- This script automatically create the following alarms to Linux EC2, with CW Agent installed.

### Linux/Windows
- Memory >= 95% during 5 minuts
- CPU 95% >= 95% during 5 minuts
- Disk usage >= 95% during 5 minuts
- StatusCheckFailed >= 1 during 5 minuts
