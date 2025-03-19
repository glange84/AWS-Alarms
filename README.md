# AWS-Alarms
Automations to create alarms on CloudWatch to resources

## auto_ec2_alarms.py
Create default alarms for EC2
- This script automatically create the following alarms to Linux EC2, with CW Agent installed.

### Linux/Windows
- Memory >= 95% during 5 minuts
- CPU 95% >= 95% during 5 minuts
- Disk usage >= 95% during 5 minuts
- StatusCheckFailed >= 1 during 5 minuts
