#!/usr/bin/env python3
"""Run a secret-free command in the source fixture and check its exit code."""
import json
import os
import subprocess
import sys

def aws(*arguments):
    result = subprocess.run(['aws', *arguments, '--output', 'json'],
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}

if len(sys.argv) < 2:
    raise SystemExit('Usage: source/run-task.py node scripts/control.mjs freeze')
stack_name = os.environ['SOURCE_STACK_NAME']
outputs = aws('cloudformation', 'describe-stacks', '--stack-name', stack_name)['Stacks'][0]['Outputs']
outputs = {item['OutputKey']: item['OutputValue'] for item in outputs}
request = {
    'cluster': outputs['Cluster'], 'taskDefinition': outputs['WebTask'],
    'launchType': 'FARGATE', 'platformVersion': '1.4.0', 'count': 1,
    'networkConfiguration': {'awsvpcConfiguration': {
        'assignPublicIp': 'ENABLED', 'subnets': [outputs['SubnetA']],
        'securityGroups': [outputs['TaskNetwork']]}},
    'overrides': {'containerOverrides': [{'name': 'portal', 'command': sys.argv[1:]}]},
    'tags': [{'key': 'project', 'value': 'ecs-migration-example'}],
    'startedBy': 'migration-check'
}
result = aws('ecs', 'run-task', '--cli-input-json', json.dumps(request))
if result.get('failures'):
    raise SystemExit('ECS did not launch the task: ' + json.dumps(result['failures']))
task_arn = result['tasks'][0]['taskArn']
print(json.dumps({'task_arn': task_arn}), flush=True)
aws('ecs', 'wait', 'tasks-stopped', '--cluster', outputs['Cluster'], '--tasks', task_arn)
task = aws('ecs', 'describe-tasks', '--cluster', outputs['Cluster'], '--tasks', task_arn)['tasks'][0]
containers = task['containers']
summary = {'task_arn': task_arn, 'stopped_reason': task.get('stoppedReason'),
           'containers': [{'name': c['name'], 'exit_code': c.get('exitCode')} for c in containers]}
print(json.dumps(summary))
if not all(c.get('exitCode') == 0 for c in containers):
    raise SystemExit('Source command failed; inspect the recorded CloudWatch log stream')
