#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { PersonalAssistantStack } from '../lib/personal-assistant-stack';

const app = new cdk.App();

new PersonalAssistantStack(app, 'PersonalAssistantStack', {
  env: {
    account: '817437953724',
    region: 'eu-west-2',
  },
  description: 'Personal AI Assistant infrastructure on AWS ECS Fargate',
});

app.synth();
