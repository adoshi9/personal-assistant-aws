#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { PersonalAssistantStack } from '../lib/personal-assistant-stack';

const app = new cdk.App();

new PersonalAssistantStack(app, 'PersonalAssistantStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  description: 'Personal AI Assistant infrastructure on AWS ECS Fargate',
});

app.synth();
