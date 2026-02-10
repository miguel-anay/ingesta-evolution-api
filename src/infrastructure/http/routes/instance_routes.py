"""
Instance Routes

FastAPI routes for WhatsApp instance management.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ....application.instances.use_cases import (
    CreateInstanceUseCase,
    CreateInstanceRequest,
    ConnectInstanceUseCase,
    ConnectInstanceRequest,
    GetInstanceStatusUseCase,
    GetInstanceStatusRequest,
    ListInstancesUseCase,
    DeleteInstanceUseCase,
    DeleteInstanceRequest,
)
from ....domain.instances.exceptions import (
    InstanceNotFoundError,
    InstanceAlreadyExistsError,
    InvalidInstanceNameError,
    InstanceConnectionError,
)
from ..dependencies import (
    get_create_instance_use_case,
    get_connect_instance_use_case,
    get_instance_status_use_case,
    get_list_instances_use_case,
    get_delete_instance_use_case,
)


router = APIRouter(prefix="/instances", tags=["Instances"])


# Request/Response DTOs

class CreateInstanceDTO(BaseModel):
    """Request body for creating an instance."""

    name: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$",
        description="Instance name (alphanumeric, starting with letter)",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for receiving events",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "my-whatsapp-instance",
                "webhook_url": "https://myapp.com/webhooks/whatsapp",
            }
        }
    }


class InstanceResponseDTO(BaseModel):
    """Response for instance operations."""

    instance_id: str
    name: str
    status: str
    message: str


class ConnectResponseDTO(BaseModel):
    """Response for connect operation with QR code."""

    instance_name: str
    qr_code: str  # Base64 image
    qr_code_raw: str
    expires_in_seconds: int
    message: str


class InstanceStatusDTO(BaseModel):
    """Response for instance status."""

    instance_name: str
    status: str
    connection_state: str
    phone_number: Optional[str]
    profile_name: Optional[str]
    is_connected: bool
    is_ready_to_send: bool


class InstanceSummaryDTO(BaseModel):
    """Summary of an instance for list response."""

    name: str
    status: str
    connection_state: str
    phone_number: Optional[str]
    is_connected: bool


class ListInstancesResponseDTO(BaseModel):
    """Response for listing instances."""

    instances: List[InstanceSummaryDTO]
    total_count: int
    connected_count: int


class DeleteInstanceDTO(BaseModel):
    """Request body for deleting an instance."""

    force: bool = Field(
        default=False,
        description="Force delete even if connected",
    )


class DeleteResponseDTO(BaseModel):
    """Response for delete operation."""

    instance_name: str
    deleted: bool
    message: str


@router.post(
    "",
    response_model=InstanceResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create instance",
    description="Create a new WhatsApp instance",
)
async def create_instance(
    body: CreateInstanceDTO,
    use_case: CreateInstanceUseCase = Depends(get_create_instance_use_case),
) -> InstanceResponseDTO:
    """
    Create a new WhatsApp instance.

    After creating, use the connect endpoint to get a QR code for authentication.
    """
    try:
        request = CreateInstanceRequest(
            name=body.name,
            webhook_url=body.webhook_url,
        )

        result = await use_case.execute(request)

        return InstanceResponseDTO(
            instance_id=result.instance_id,
            name=result.name,
            status=result.status,
            message=result.message,
        )

    except InvalidInstanceNameError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.message, "code": e.code},
        )
    except InstanceAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": e.message, "code": e.code},
        )


@router.post(
    "/{instance_name}/connect",
    response_model=ConnectResponseDTO,
    summary="Connect instance",
    description="Get QR code to connect WhatsApp",
)
async def connect_instance(
    instance_name: str,
    use_case: ConnectInstanceUseCase = Depends(get_connect_instance_use_case),
) -> ConnectResponseDTO:
    """
    Initiate WhatsApp connection for an instance.

    Returns a QR code that must be scanned with the WhatsApp mobile app.
    The QR code expires after approximately 60 seconds.
    """
    try:
        request = ConnectInstanceRequest(name=instance_name)
        result = await use_case.execute(request)

        return ConnectResponseDTO(
            instance_name=result.instance_name,
            qr_code=result.qr_code,
            qr_code_raw=result.qr_code_raw,
            expires_in_seconds=result.expires_in_seconds,
            message=result.message,
        )

    except InstanceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "code": e.code},
        )
    except InstanceConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": e.message, "code": e.code},
        )


@router.get(
    "/{instance_name}/status",
    response_model=InstanceStatusDTO,
    summary="Get instance status",
    description="Get current status of an instance",
)
async def get_instance_status(
    instance_name: str,
    use_case: GetInstanceStatusUseCase = Depends(get_instance_status_use_case),
) -> InstanceStatusDTO:
    """
    Get the current status of a WhatsApp instance.

    Returns connection state, phone number, and profile information.
    """
    try:
        request = GetInstanceStatusRequest(name=instance_name)
        result = await use_case.execute(request)

        return InstanceStatusDTO(
            instance_name=result.instance_name,
            status=result.status,
            connection_state=result.connection_state,
            phone_number=result.phone_number,
            profile_name=result.profile_name,
            is_connected=result.is_connected,
            is_ready_to_send=result.is_ready_to_send,
        )

    except InstanceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "code": e.code},
        )


@router.get(
    "",
    response_model=ListInstancesResponseDTO,
    summary="List instances",
    description="List all WhatsApp instances",
)
async def list_instances(
    use_case: ListInstancesUseCase = Depends(get_list_instances_use_case),
) -> ListInstancesResponseDTO:
    """
    List all WhatsApp instances with their status.
    """
    result = await use_case.execute()

    return ListInstancesResponseDTO(
        instances=[
            InstanceSummaryDTO(
                name=inst.name,
                status=inst.status,
                connection_state=inst.connection_state,
                phone_number=inst.phone_number,
                is_connected=inst.is_connected,
            )
            for inst in result.instances
        ],
        total_count=result.total_count,
        connected_count=result.connected_count,
    )


@router.delete(
    "/{instance_name}",
    response_model=DeleteResponseDTO,
    summary="Delete instance",
    description="Delete a WhatsApp instance",
)
async def delete_instance(
    instance_name: str,
    body: DeleteInstanceDTO = DeleteInstanceDTO(),
    use_case: DeleteInstanceUseCase = Depends(get_delete_instance_use_case),
) -> DeleteResponseDTO:
    """
    Delete a WhatsApp instance.

    By default, won't delete connected instances. Use force=true to override.
    """
    try:
        request = DeleteInstanceRequest(
            name=instance_name,
            force=body.force,
        )

        result = await use_case.execute(request)

        return DeleteResponseDTO(
            instance_name=result.instance_name,
            deleted=result.deleted,
            message=result.message,
        )

    except InstanceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": e.message, "code": e.code},
        )
