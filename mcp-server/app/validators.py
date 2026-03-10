"""Parameter validators for cloud operations."""

ALLOWED_INSTANCE_TYPES = {
    "t2.micro",
    "t2.small",
    "t2.medium",
    "t3.micro",
    "t3.small",
    "t3.medium",
}

class ValidationError(Exception):
    pass


def validate_bucket_name(name: str) -> None:
    if not name or len(name) < 3 or len(name) > 63:
        raise ValidationError("Bucket name must be 3-63 characters")
    if not name[0].isalnum():
        raise ValidationError("Bucket name must start with a letter or number")
    import re
    if not re.match(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$", name):
        raise ValidationError(
            "Bucket name can only contain lowercase letters, numbers, hyphens, and dots"
        )


def validate_instance_type(instance_type: str) -> None:
    if instance_type not in ALLOWED_INSTANCE_TYPES:
        raise ValidationError(
            f"Instance type '{instance_type}' is not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_INSTANCE_TYPES))}"
        )
