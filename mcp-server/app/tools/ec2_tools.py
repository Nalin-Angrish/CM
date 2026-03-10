"""EC2 instance tool implementations using boto3."""
import os
import boto3
from botocore.exceptions import ClientError
from app.validators import validate_instance_type, ValidationError

DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def _get_ec2_client():
    return boto3.client("ec2", region_name=DEFAULT_REGION)


def create_ec2_instance(params: dict) -> dict:
    instance_name = params["instance_name"]
    instance_type = params.get("instance_type", "t2.micro")

    validate_instance_type(instance_type)

    ec2 = _get_ec2_client()

    try:
        response = ec2.run_instances(
            ImageId="ami-0f559c3642608c138",
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": instance_name}],
                }
            ],
        )

        instance_id = response["Instances"][0]["InstanceId"]

        return {
            "success": True,
            "cloud_identifier": instance_id,
            "message": f"EC2 instance '{instance_name}' ({instance_id}) launched in {DEFAULT_REGION}",
            "details": {
                "instance_id": instance_id,
                "instance_name": instance_name,
                "instance_type": instance_type,
                "region": DEFAULT_REGION,
                "state": "pending",
            },
        }
    except ClientError as e:
        return {
            "success": False,
            "message": f"Failed to launch instance: {e.response['Error']['Message']}",
            "details": {"error_code": e.response["Error"]["Code"]},
        }


def modify_ec2_instance(params: dict) -> dict:
    instance_id = params["instance_id"]
    action = params.get("action", "stop")

    ec2 = _get_ec2_client()

    try:
        if action == "stop":
            ec2.stop_instances(InstanceIds=[instance_id])
            msg = f"Instance {instance_id} stopping"
        elif action == "start":
            ec2.start_instances(InstanceIds=[instance_id])
            msg = f"Instance {instance_id} starting"
        elif action == "change_type":
            new_type = params.get("instance_type")
            if not new_type:
                return {
                    "success": False,
                    "message": "instance_type required for change_type action",
                    "details": {},
                }
            validate_instance_type(new_type)
            # Must stop instance first
            ec2.stop_instances(InstanceIds=[instance_id])
            waiter = ec2.get_waiter("instance_stopped")
            waiter.wait(InstanceIds=[instance_id])
            ec2.modify_instance_attribute(
                InstanceId=instance_id,
                InstanceType={"Value": new_type},
            )
            ec2.start_instances(InstanceIds=[instance_id])
            msg = f"Instance {instance_id} type changed to {new_type} and restarted"
        else:
            return {
                "success": False,
                "message": f"Unknown action: {action}",
                "details": {},
            }

        return {
            "success": True,
            "cloud_identifier": instance_id,
            "message": msg,
            "details": {"instance_id": instance_id, "action": action},
        }
    except ClientError as e:
        return {
            "success": False,
            "message": f"Failed to modify instance: {e.response['Error']['Message']}",
            "details": {"error_code": e.response["Error"]["Code"]},
        }


def delete_ec2_instance(params: dict) -> dict:
    instance_id = params["instance_id"]

    ec2 = _get_ec2_client()

    try:
        ec2.terminate_instances(InstanceIds=[instance_id])

        return {
            "success": True,
            "cloud_identifier": instance_id,
            "message": f"EC2 instance {instance_id} terminated",
            "details": {"instance_id": instance_id, "state": "shutting-down"},
        }
    except ClientError as e:
        return {
            "success": False,
            "message": f"Failed to terminate instance: {e.response['Error']['Message']}",
            "details": {"error_code": e.response["Error"]["Code"]},
        }
