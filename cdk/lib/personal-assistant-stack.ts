import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { Construct } from 'constructs';

export class PersonalAssistantStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VPC for isolation
    const vpc = new ec2.Vpc(this, 'AssistantVpc', {
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    // Reference existing ECR Repository (don't create new one)
    const repository = ecr.Repository.fromRepositoryArn(
      this,
      'AssistantRepository',
      'arn:aws:ecr:eu-west-2:817437953724:repository/personal-assistant'
    );

    // ECS Cluster
    const cluster = new ecs.Cluster(this, 'AssistantCluster', {
      vpc,
      clusterName: 'personal-assistant-cluster',
      containerInsights: true,
    });

    // Task Execution Role (for pulling images and writing logs)
    const executionRole = new iam.Role(this, 'TaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    // Grant ECR pull permissions
    executionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ecr:GetAuthorizationToken',
          'ecr:BatchCheckLayerAvailability',
          'ecr:GetDownloadUrlForLayer',
          'ecr:BatchGetImage',
        ],
        resources: ['*'],
      })
    );

    // Task Role (for application permissions)
    const taskRole = new iam.Role(this, 'TaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });

    // Grant Secrets Manager access to existing secrets
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret',
        ],
        resources: [
          `arn:aws:secretsmanager:eu-west-2:817437953724:secret:personal-assistant/*`,
        ],
      })
    );

    // CloudWatch Logs Group
    const logGroup = new logs.LogGroup(this, 'AssistantLogs', {
      logGroupName: '/ecs/personal-assistant',
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Task Definition
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'TaskDef', {
      memoryLimitMiB: 1024,
      cpu: 512,
      executionRole,
      taskRole,
    });

    // Container Definition - using existing ECR image
    const container = taskDefinition.addContainer('AssistantContainer', {
      image: ecs.ContainerImage.fromRegistry(
        '817437953724.dkr.ecr.eu-west-2.amazonaws.com/personal-assistant:latest'
      ),
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'assistant',
        logGroup,
      }),
      environment: {
        APP_ENV: 'production',
        AWS_REGION: 'eu-west-2',
        GATEWAY_HOST: '0.0.0.0',
        GATEWAY_PORT: '8000',
        AWS_SECRETS_PREFIX: 'personal-assistant/',
        LOG_LEVEL: 'INFO',
      },
      healthCheck: {
        command: ['CMD-SHELL', 'python -c "import httpx; httpx.get(\'http://localhost:8000/health\', timeout=5.0)" || exit 1'],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(10),
        retries: 3,
        startPeriod: cdk.Duration.seconds(40),
      },
    });

    container.addPortMappings({
      containerPort: 8000,
      protocol: ecs.Protocol.TCP,
    });

    // Security Group
    const securityGroup = new ec2.SecurityGroup(this, 'AssistantSecurityGroup', {
      vpc,
      description: 'Security group for Personal Assistant',
      allowAllOutbound: true,
    });

    // ECS Service
    const service = new ecs.FargateService(this, 'AssistantService', {
      cluster,
      taskDefinition,
      desiredCount: 1,
      assignPublicIp: false,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      securityGroups: [securityGroup],
      serviceName: 'personal-assistant',
      enableExecuteCommand: true, // For debugging
    });

    // Auto Scaling (optional)
    const scaling = service.autoScaleTaskCount({
      minCapacity: 1,
      maxCapacity: 3,
    });

    scaling.scaleOnCpuUtilization('CpuScaling', {
      targetUtilizationPercent: 70,
      scaleInCooldown: cdk.Duration.seconds(60),
      scaleOutCooldown: cdk.Duration.seconds(60),
    });

    // Reference existing secrets (don't create new ones)
    const telegramBotToken = secretsmanager.Secret.fromSecretNameV2(
      this,
      'TelegramBotToken',
      'personal-assistant/telegram/bot-token'
    );

    const anthropicApiKey = secretsmanager.Secret.fromSecretNameV2(
      this,
      'AnthropicApiKey',
      'personal-assistant/anthropic/api-key'
    );

    const githubToken = secretsmanager.Secret.fromSecretNameV2(
      this,
      'GitHubToken',
      'personal-assistant/github/token'
    );

    // Application Load Balancer for API Gateway integration
    const alb = new elbv2.ApplicationLoadBalancer(this, 'AssistantALB', {
      vpc,
      internetFacing: true,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PUBLIC,
      },
    });

    const targetGroup = new elbv2.ApplicationTargetGroup(this, 'AssistantTargetGroup', {
      vpc,
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        path: '/health',
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
    });

    // Attach ECS service to target group
    service.attachToApplicationTargetGroup(targetGroup);

    const listener = alb.addListener('HttpListener', {
      port: 80,
      protocol: elbv2.ApplicationProtocol.HTTP,
      defaultTargetGroups: [targetGroup],
    });

    // Allow inbound traffic from anywhere to ALB
    alb.connections.allowFromAnyIpv4(
      ec2.Port.tcp(80),
      'Allow HTTP traffic from anywhere'
    );

    // Allow ALB to reach ECS tasks
    service.connections.allowFrom(
      alb,
      ec2.Port.tcp(8000),
      'Allow ALB to reach ECS tasks'
    );

    // API Gateway REST API
    const api = new apigateway.RestApi(this, 'AssistantAPI', {
      restApiName: 'Personal Assistant API',
      description: 'API Gateway for Telegram webhook',
      deployOptions: {
        stageName: 'prod',
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
      },
    });

    // VPC Link to connect API Gateway to private ALB
    const vpcLink = new apigateway.VpcLink(this, 'VpcLink', {
      targets: [alb],
      vpcLinkName: 'personal-assistant-vpc-link',
    });

    // Webhook endpoint
    const webhookResource = api.root.addResource('webhook');

    // POST method for Telegram webhook
    webhookResource.addMethod(
      'POST',
      new apigateway.Integration({
        type: apigateway.IntegrationType.HTTP_PROXY,
        integrationHttpMethod: 'POST',
        uri: `http://${alb.loadBalancerDnsName}/webhook`,
        options: {
          connectionType: apigateway.ConnectionType.VPC_LINK,
          vpcLink: vpcLink,
          requestParameters: {
            'integration.request.header.X-Forwarded-For': 'context.identity.sourceIp',
          },
        },
      })
    );

    // Health check endpoint
    const healthResource = api.root.addResource('health');
    healthResource.addMethod(
      'GET',
      new apigateway.Integration({
        type: apigateway.IntegrationType.HTTP_PROXY,
        integrationHttpMethod: 'GET',
        uri: `http://${alb.loadBalancerDnsName}/health`,
        options: {
          connectionType: apigateway.ConnectionType.VPC_LINK,
          vpcLink: vpcLink,
        },
      })
    );

    // Outputs
    new cdk.CfnOutput(this, 'ClusterName', {
      value: cluster.clusterName,
      description: 'ECS Cluster Name',
    });

    new cdk.CfnOutput(this, 'ServiceName', {
      value: service.serviceName,
      description: 'ECS Service Name',
    });

    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: api.url,
      description: 'API Gateway URL for Telegram webhook',
    });

    new cdk.CfnOutput(this, 'WebhookUrl', {
      value: `${api.url}webhook`,
      description: 'Full webhook URL to configure in Telegram',
      exportName: 'TelegramWebhookUrl',
    });

    new cdk.CfnOutput(this, 'LoadBalancerDns', {
      value: alb.loadBalancerDnsName,
      description: 'Application Load Balancer DNS',
    });

    new cdk.CfnOutput(this, 'LogGroupName', {
      value: logGroup.logGroupName,
      description: 'CloudWatch Logs Group Name',
    });

    new cdk.CfnOutput(this, 'VpcId', {
      value: vpc.vpcId,
      description: 'VPC ID',
    });
  }
}
