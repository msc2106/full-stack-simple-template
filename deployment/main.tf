provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region used for all resources"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID used for resource ARNs"
  type        = string
}

variable "aws_profile" {
  description = "AWS CLI profile to use for credentials"
  type        = string
}

variable "aws_availability_zone" {
  description = "Single availability zone used by the stack"
  type        = string
}

variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be either 'staging' or 'production'."
  }
}

variable "volume_snapshot_id" {
  description = "Optional EBS snapshot ID used to seed the database volume"
  type        = string
  default     = null
}

locals {
  db_allowed_ports = [22, 7474, 7687, 5432]

  # Mirror CDK behavior: production gets larger DB instance type.
  db_instance_type = var.environment == "production" ? "t4g.large" : "t4g.medium"

  db_rule_sources = {
    self    = aws_security_group.db.id
    app     = aws_security_group.app.id
    bastion = aws_security_group.bastion.id
  }

  db_rules = flatten([
    for source_name, source_sg_id in local.db_rule_sources : [
      for port in local.db_allowed_ports : {
        key         = "${source_name}-${port}"
        source_name = source_name
        source_sg   = source_sg_id
        port        = port
      }
    ]
  ])

  ecr_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

data "aws_ssm_parameter" "al2023_arm64_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-arm64"
}

data "aws_ec2_managed_prefix_list" "ec2_instance_connect" {
  name = "com.amazonaws.${var.aws_region}.ec2-instance-connect"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/21"
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.0.0/24"
  availability_zone       = var.aws_availability_zone
  map_public_ip_on_launch = true
}

resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = var.aws_availability_zone
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public.id

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route" "private_default" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main.id
}

resource "aws_route_table_association" "private" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "app" {
  name        = "workforce-engine-app-sg"
  description = "Application security group"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "bastion" {
  name        = "workforce-engine-bastion-sg"
  description = "Bastion security group"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "db" {
  name        = "workforce-engine-db-sg"
  description = "Database security group"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_egress_rule" "app_all_outbound" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound"
}

resource "aws_vpc_security_group_egress_rule" "bastion_all_outbound" {
  security_group_id = aws_security_group.bastion.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound"
}

resource "aws_vpc_security_group_egress_rule" "db_all_outbound" {
  security_group_id = aws_security_group.db.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all outbound"
}

resource "aws_vpc_security_group_ingress_rule" "app_all_inbound" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all inbound traffic from any source"
}

resource "aws_vpc_security_group_ingress_rule" "bastion_ssh_inbound" {
  security_group_id = aws_security_group.bastion.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  description       = "Allow SSH access from any source"
}

resource "aws_vpc_security_group_ingress_rule" "db_from_security_groups" {
  for_each = {
    for rule in local.db_rules : rule.key => rule
  }

  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value.source_sg
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
  description                  = "Allow ${each.value.source_name} access on port ${each.value.port}"
}

resource "aws_vpc_security_group_ingress_rule" "db_from_ec2_instance_connect" {
  security_group_id = aws_security_group.db.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.ec2_instance_connect.id
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  description       = "Allow EC2 Instance Connect"
}

resource "aws_ec2_instance_connect_endpoint" "main" {
  subnet_id          = aws_subnet.private.id
  security_group_ids = [aws_security_group.app.id, aws_security_group.db.id]
}

resource "aws_apprunner_vpc_connector" "main" {
  vpc_connector_name = "workforce-engine-apprunner-vpc-connector"
  subnets            = [aws_subnet.private.id]
  security_groups    = [aws_security_group.app.id]
}

resource "aws_ecr_repository" "frontend" {
  name         = "workforce-engine-frontend"
  force_delete = true
}

resource "aws_ecr_repository" "backend" {
  name         = "workforce-engine-backend"
  force_delete = true
}

resource "aws_ecr_lifecycle_policy" "frontend" {
  repository = aws_ecr_repository.frontend.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy     = local.ecr_lifecycle_policy
}

resource "aws_iam_role" "backend_apprunner" {
  name = "BackendAppRunnerRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role" "frontend_apprunner" {
  name = "FrontendAppRunnerRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "backend_apprunner_ecr_pull" {
  name = "backend-apprunner-ecr-pull"
  role = aws_iam_role.backend_apprunner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:DescribeImages",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = aws_ecr_repository.backend.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "frontend_apprunner_ecr_pull" {
  name = "frontend-apprunner-ecr-pull"
  role = aws_iam_role.frontend_apprunner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:DescribeImages",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = aws_ecr_repository.frontend.arn
      }
    ]
  })
}

resource "aws_iam_role" "db_instance" {
  name = "DatabaseServerInstanceRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "db_ssm" {
  role       = aws_iam_role.db_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "db_logs" {
  name = "db-instance-logs"
  role = aws_iam_role.db_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents",
          "logs:GetLogEvents",
          "logs:FilterLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "db_ecr_pull" {
  name = "db-instance-backend-ecr-pull"
  role = aws_iam_role.db_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:DescribeImages",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = aws_ecr_repository.backend.arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "db" {
  name = "DatabaseServerInstanceProfile"
  role = aws_iam_role.db_instance.name
}

resource "tls_private_key" "db_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "db" {
  key_name   = "database-server-key-pair"
  public_key = tls_private_key.db_key.public_key_openssh
}

resource "aws_instance" "bastion" {
  ami                    = data.aws_ssm_parameter.al2023_arm64_ami.value
  instance_type          = "t4g.nano"
  availability_zone      = var.aws_availability_zone
  subnet_id              = aws_subnet.private.id
  vpc_security_group_ids = [aws_security_group.bastion.id]
  key_name               = aws_key_pair.db.key_name
}

resource "aws_instance" "db" {
  ami                    = data.aws_ssm_parameter.al2023_arm64_ami.value
  instance_type          = local.db_instance_type
  availability_zone      = var.aws_availability_zone
  subnet_id              = aws_subnet.private.id
  vpc_security_group_ids = [aws_security_group.db.id]
  key_name               = aws_key_pair.db.key_name
  iam_instance_profile   = aws_iam_instance_profile.db.name
}

resource "aws_ebs_volume" "db_storage" {
  availability_zone = var.aws_availability_zone
  snapshot_id       = var.volume_snapshot_id
  size              = 2

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_volume_attachment" "db_volume" {
  device_name = "/dev/xvdf"
  volume_id   = aws_ebs_volume.db_storage.id
  instance_id = aws_instance.db.id
}

output "FrontendRepositoryURI" {
  value = aws_ecr_repository.frontend.repository_url
}

output "BackendRepositoryURI" {
  value = aws_ecr_repository.backend.repository_url
}

output "BackendAppRunnerRoleARN" {
  value = aws_iam_role.backend_apprunner.arn
}

output "FrontendAppRunnerRoleARN" {
  value = aws_iam_role.frontend_apprunner.arn
}

output "DatabaseServerDNS" {
  value = aws_instance.db.private_dns
}

output "VpcConnectorARN" {
  value = aws_apprunner_vpc_connector.main.arn
}

output "DatabaseServerID" {
  value = aws_instance.db.id
}

output "VolumeID" {
  value = aws_ebs_volume.db_storage.id
}

output "BastionServerID" {
  value = aws_instance.bastion.id
}

output "KeyPairID" {
  value = aws_key_pair.db.key_pair_id
}

output "DatabaseServerPrivateKeyPem" {
  description = "Generated private key for the EC2 key pair"
  value       = tls_private_key.db_key.private_key_pem
  sensitive   = true
}
