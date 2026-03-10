"""
Evolution API Image Source Adapter

Infrastructure adapter that implements IImageSourcePort
for fetching images from Evolution API.
"""

import logging
import json
import base64
import re
from typing import AsyncIterator, List, Optional, Dict, Any, Set
from datetime import datetime

from ....application.ingestion.ports import IImageSourcePort
from ....domain.ingestion.entities import RawImageData
from ....domain.ingestion.value_objects import (
    SourceType,
    MessageId,
    PhoneNumber,
    UserName,
    Instance,
)
from ....domain.ingestion.exceptions import ImageSourceError
from .client import EvolutionApiClient
from .exceptions import EvolutionApiError


logger = logging.getLogger(__name__)


class EvolutionApiImageSourceAdapter(IImageSourcePort):
    """
    Adapter for fetching images from Evolution API.

    Implements IImageSourcePort to provide image data
    from WhatsApp chat messages and user status.

    This adapter handles:
    - Fetching message lists from Evolution API
    - Filtering for image messages only
    - Filtering by specific phone number (REQUIRED per PROJECT_SPECS.md)
    - Downloading media content
    - Converting API responses to domain entities
    """

    # Supported image mime types
    SUPPORTED_IMAGE_TYPES = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
    }

    def __init__(self, client: EvolutionApiClient, evolution_db_url: Optional[str] = None) -> None:
        """
        Initialize the adapter.

        Args:
            client: The Evolution API HTTP client
            evolution_db_url: Connection string for Evolution API's database (for LID resolution)
        """
        self._client = client
        self._evolution_db_url = evolution_db_url
        self._instance_id_cache: Dict[str, str] = {}

    def _normalize_phone_number(self, phone: str) -> str:
        """Normalize phone number by removing non-digit characters."""
        return re.sub(r"\D", "", phone)

    def _build_jid_from_phone(self, phone: str) -> str:
        """Build WhatsApp JID from phone number."""
        normalized = self._normalize_phone_number(phone)
        return f"{normalized}@s.whatsapp.net"

    def _phone_matches_jid(self, phone: str, jid: str) -> bool:
        """Check if a phone number matches a WhatsApp JID."""
        normalized_phone = self._normalize_phone_number(phone)
        jid_phone = self._extract_phone_from_jid(jid)
        return normalized_phone == jid_phone

    async def _get_instance_id(self, instance_name: str) -> Optional[str]:
        """Get Evolution API instance UUID from instance name."""
        if instance_name in self._instance_id_cache:
            return self._instance_id_cache[instance_name]

        try:
            instances = await self._client.list_instances()
            if isinstance(instances, list):
                for inst in instances:
                    name = inst.get("name", inst.get("instanceName", ""))
                    if name == instance_name:
                        inst_id = inst.get("id", "")
                        if inst_id:
                            self._instance_id_cache[instance_name] = inst_id
                            return inst_id
        except Exception as e:
            logger.warning(f"Could not get instance ID: {e}")
        return None

    async def _resolve_lid_via_db(self, instance_name: str, phone: str) -> Optional[str]:
        """
        Resolve phone → LID by querying Evolution API's database.

        Uses the participantAlt field in group messages to find the LID
        corresponding to a phone number.
        """
        if not self._evolution_db_url:
            return None

        instance_id = await self._get_instance_id(instance_name)
        if not instance_id:
            return None

        normalized = self._normalize_phone_number(phone)
        phone_jid = f"{normalized}@s.whatsapp.net"

        try:
            import asyncpg
            conn = await asyncpg.connect(self._evolution_db_url)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT DISTINCT key->>'participant' as lid
                    FROM "Message"
                    WHERE key->>'participantAlt' = $1
                    AND "instanceId" = $2
                    LIMIT 1
                    """,
                    phone_jid, instance_id,
                )

                if row and row['lid']:
                    lid = row['lid']
                    logger.info(f"Resolved {phone} -> {lid} via Evolution DB (participantAlt)")
                    return lid
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"Could not resolve LID via Evolution DB: {e}")

        return None

    async def _fetch_image_messages_from_db(
        self,
        instance_name: str,
        phone: str,
        lid: Optional[str] = None,
        limit: int = 500,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch image messages from Evolution DB for a phone number.

        Searches both group messages (via participantAlt) and
        1-to-1 messages (via resolved LID).
        Supports date range filtering via messageTimestamp.
        """
        if not self._evolution_db_url:
            return []

        instance_id = await self._get_instance_id(instance_name)
        if not instance_id:
            return []

        normalized = self._normalize_phone_number(phone)
        phone_jid = f"{normalized}@s.whatsapp.net"

        # Build date filter clauses
        date_clauses = ""
        params: list = [instance_id, phone_jid]
        param_idx = 3

        if fecha_desde:
            ts_desde = int(fecha_desde.timestamp())
            date_clauses += f' AND "messageTimestamp" >= ${param_idx}'
            params.append(ts_desde)
            param_idx += 1

        if fecha_hasta:
            ts_hasta = int(fecha_hasta.timestamp())
            date_clauses += f' AND "messageTimestamp" <= ${param_idx}'
            params.append(ts_hasta)
            param_idx += 1

        try:
            import asyncpg
            conn = await asyncpg.connect(self._evolution_db_url)
            try:
                if lid:
                    query = f"""
                        SELECT key::text as key_json, "pushName", "messageTimestamp",
                               message::text as message_json
                        FROM "Message"
                        WHERE "messageType" = 'imageMessage'
                        AND "instanceId" = $1
                        AND (
                            key->>'participantAlt' = $2
                            OR (key->>'remoteJid' = ${param_idx} AND key->>'fromMe' = 'false')
                        )
                        {date_clauses}
                        ORDER BY "messageTimestamp" DESC
                        LIMIT ${param_idx + 1}
                    """
                    params.extend([lid, limit])
                else:
                    query = f"""
                        SELECT key::text as key_json, "pushName", "messageTimestamp",
                               message::text as message_json
                        FROM "Message"
                        WHERE "messageType" = 'imageMessage'
                        AND "instanceId" = $1
                        AND key->>'participantAlt' = $2
                        {date_clauses}
                        ORDER BY "messageTimestamp" DESC
                        LIMIT ${param_idx}
                    """
                    params.append(limit)

                rows = await conn.fetch(query, *params)

                result = []
                for row in rows:
                    msg = {
                        'key': json.loads(row['key_json']),
                        'pushName': row['pushName'] or "",
                        'messageTimestamp': row['messageTimestamp'],
                        'message': json.loads(row['message_json']),
                    }
                    result.append(msg)

                logger.info(
                    f"Found {len(result)} image messages for {phone} via Evolution DB "
                    f"(lid={lid}, desde={fecha_desde}, hasta={fecha_hasta})"
                )
                return result
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"Could not fetch images from Evolution DB: {e}")
            return []

    async def _resolve_jid_for_phone(
        self, instance_name: str, phone_number: str
    ) -> str:
        """
        Resolve the actual remoteJid for a phone number.

        Strategies (in order):
        1. Check chats API for standard JID or remoteJidAlt match
        2. Query Evolution DB for LID mapping (via participantAlt in group messages)
        3. Fallback to standard JID format
        """
        normalized = self._normalize_phone_number(phone_number)
        standard_jid = f"{normalized}@s.whatsapp.net"

        # Strategy 1: Check chats API
        try:
            chats = await self._get_chats(instance_name)

            for chat in chats:
                if not isinstance(chat, dict):
                    continue

                remote_jid = chat.get("remoteJid", "") or chat.get("id", "")

                if remote_jid == standard_jid:
                    return standard_jid

                last_msg = chat.get("lastMessage", {})
                if isinstance(last_msg, dict):
                    key = last_msg.get("key", {})
                    if isinstance(key, dict):
                        alt_jid = key.get("remoteJidAlt", "")
                        if alt_jid == standard_jid and remote_jid:
                            logger.info(
                                f"Phone {phone_number} uses LID addressing: {remote_jid}"
                            )
                            return remote_jid

        except Exception as e:
            logger.warning(f"Could not resolve JID via chats API: {e}")

        # Strategy 2: Query Evolution DB for LID mapping
        lid = await self._resolve_lid_via_db(instance_name, phone_number)
        if lid:
            return lid

        # Strategy 3: Fallback to standard format
        logger.debug(f"Using standard JID for {phone_number}: {standard_jid}")
        return standard_jid

    def _is_within_date_range(
        self,
        message: Dict[str, Any],
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> bool:
        """Check if a message's timestamp falls within the date range."""
        if not fecha_desde and not fecha_hasta:
            return True

        msg_ts = self._extract_timestamp(message)

        if fecha_desde and msg_ts < fecha_desde:
            return False
        if fecha_hasta and msg_ts > fecha_hasta:
            return False
        return True

    async def fetch_chat_images(
        self,
        instance_name: str,
        phone_number: str,
        limit: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> AsyncIterator[RawImageData]:
        """
        Fetch images from chat messages for a specific phone number.

        Uses a multi-strategy approach:
        1. Try API-based message fetching via resolved JID
        2. If no results, query Evolution DB directly for image messages
           (handles LID addressing and group messages)

        Args:
            instance_name: The WhatsApp instance to fetch from
            phone_number: The phone number to filter messages by (required)
            limit: Maximum number of images to fetch

        Yields:
            RawImageData for each image found from the specified number
        """
        logger.info(
            f"Fetching chat images from instance: {instance_name}, "
            f"phone: {phone_number}"
        )

        try:
            # Resolve the actual JID (handles LID addressing)
            target_jid = await self._resolve_jid_for_phone(instance_name, phone_number)
            normalized_phone = self._normalize_phone_number(phone_number)

            logger.info(f"Resolved JID for {phone_number}: {target_jid}")

            # Strategy 1: Get messages via API for the resolved JID
            messages = await self._get_messages(instance_name, target_jid)
            images_yielded = 0
            seen_message_ids: Set[str] = set()
            image_messages_found = 0
            skipped_by_date = 0

            for message in messages:
                if limit and images_yielded >= limit:
                    break

                key = message.get("key", {})
                remote_jid = key.get("remoteJid", "")
                msg_id = key.get("id", "")

                if remote_jid != target_jid and not self._phone_matches_jid(phone_number, remote_jid):
                    continue

                # Filter by date range
                if not self._is_within_date_range(message, fecha_desde, fecha_hasta):
                    skipped_by_date += 1
                    continue

                msg_content = message.get("message", {})
                if isinstance(msg_content, dict) and msg_content.get("imageMessage"):
                    image_messages_found += 1

                raw_image = await self._process_message(
                    instance_name=instance_name,
                    message=message,
                    source_type=SourceType.CHAT,
                    request_phone_number=phone_number,
                )

                if raw_image:
                    seen_message_ids.add(msg_id)
                    yield raw_image
                    images_yielded += 1

            logger.info(
                f"API strategy: {image_messages_found} image messages, "
                f"{images_yielded} downloaded, {skipped_by_date} skipped by date "
                f"for {phone_number}"
            )

            # Strategy 2: Query Evolution DB for additional images
            # (group messages + LID chats not found via API)
            if self._evolution_db_url:
                remaining_limit = (limit - images_yielded) if limit else None
                if remaining_limit is None or remaining_limit > 0:
                    lid = target_jid if target_jid.endswith("@lid") else None
                    db_messages = await self._fetch_image_messages_from_db(
                        instance_name=instance_name,
                        phone=phone_number,
                        lid=lid,
                        limit=remaining_limit or 500,
                        fecha_desde=fecha_desde,
                        fecha_hasta=fecha_hasta,
                    )

                    db_images_yielded = 0
                    for message in db_messages:
                        if limit and (images_yielded + db_images_yielded) >= limit:
                            break

                        msg_id = message.get("key", {}).get("id", "")
                        if msg_id in seen_message_ids:
                            continue

                        raw_image = await self._process_message(
                            instance_name=instance_name,
                            message=message,
                            source_type=SourceType.CHAT,
                            request_phone_number=phone_number,
                        )

                        if raw_image:
                            seen_message_ids.add(msg_id)
                            yield raw_image
                            db_images_yielded += 1

                    if db_images_yielded > 0:
                        logger.info(
                            f"DB strategy: {db_images_yielded} additional images "
                            f"for {phone_number}"
                        )
                    images_yielded += db_images_yielded

            logger.info(
                f"Total chat images for {phone_number}: {images_yielded} downloaded"
            )

        except EvolutionApiError as e:
            logger.error(f"Evolution API error fetching chat images: {e}")
            raise ImageSourceError(
                source="chat",
                reason=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error fetching chat images: {e}")
            raise ImageSourceError(
                source="chat",
                reason=f"Unexpected error: {str(e)}",
            )

    async def fetch_status_images(
        self,
        instance_name: str,
        phone_number: str,
        limit: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> AsyncIterator[RawImageData]:
        """
        Fetch images from user status (stories) for a specific phone number.

        Args:
            instance_name: The WhatsApp instance to fetch from
            phone_number: The phone number to filter status by (required)
            limit: Maximum number of images to fetch
            fecha_desde: Only fetch messages after this datetime
            fecha_hasta: Only fetch messages before this datetime

        Yields:
            RawImageData for each status image found from the specified number
        """
        logger.info(
            f"Fetching status images from instance: {instance_name}, "
            f"phone: {phone_number}"
        )

        try:
            # Resolve the actual JID (handles LID addressing)
            target_jid = await self._resolve_jid_for_phone(instance_name, phone_number)
            normalized_phone = self._normalize_phone_number(phone_number)

            # Get status updates (from status@broadcast)
            statuses = await self._get_status_updates(instance_name)
            images_yielded = 0

            logger.info(
                f"Found {len(statuses)} total status messages, "
                f"filtering for phone {phone_number} (jid={target_jid})"
            )

            for status in statuses:
                if limit and images_yielded >= limit:
                    break

                if not isinstance(status, dict):
                    continue

                # In status@broadcast messages, the author is identified by:
                # - key.participant (LID or phone@s.whatsapp.net)
                # - pushName (may contain phone number)
                key = status.get("key", {})
                if not isinstance(key, dict):
                    continue

                participant = key.get("participant", "") or ""
                push_name = status.get("pushName", "") or ""

                # Match by participant JID, resolved JID, phone in pushName, or phone match
                matches = (
                    participant == target_jid
                    or self._phone_matches_jid(phone_number, participant)
                    or normalized_phone in push_name
                    or normalized_phone == self._normalize_phone_number(push_name)
                )

                if not matches:
                    continue

                # Filter by date range
                if not self._is_within_date_range(status, fecha_desde, fecha_hasta):
                    continue

                # Process each status entry
                raw_image = await self._process_message(
                    instance_name=instance_name,
                    message=status,
                    source_type=SourceType.STATUS,
                    request_phone_number=phone_number,
                )

                if raw_image:
                    yield raw_image
                    images_yielded += 1

            logger.info(
                f"Fetched {images_yielded} status images for phone {phone_number}"
            )

        except EvolutionApiError as e:
            logger.error(f"Evolution API error fetching status images: {e}")
            raise ImageSourceError(
                source="status",
                reason=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error fetching status images: {e}")
            raise ImageSourceError(
                source="status",
                reason=f"Unexpected error: {str(e)}",
            )

    async def download_media(
        self,
        instance_name: str,
        message_id: str,
    ) -> bytes:
        """
        Download media content for a specific message.

        Args:
            instance_name: The WhatsApp instance
            message_id: The message ID containing media

        Returns:
            Raw bytes of the media file
        """
        try:
            endpoint = f"/chat/getBase64FromMediaMessage/{instance_name}"
            response = await self._client.post(
                endpoint,
                data={"message": {"key": {"id": message_id}}},
            )

            # Response should contain base64 encoded media
            base64_data = response.get("base64", "")
            if not base64_data:
                raise ImageSourceError(
                    source="media",
                    reason=f"No media data returned for message {message_id}",
                )

            # Remove data URL prefix if present
            if "," in base64_data:
                base64_data = base64_data.split(",", 1)[1]

            return base64.b64decode(base64_data)

        except EvolutionApiError as e:
            raise ImageSourceError(
                source="media",
                reason=f"Failed to download media {message_id}: {str(e)}",
            )

    async def get_available_instances(self) -> List[str]:
        """
        Get list of available WhatsApp instances.

        Returns:
            List of connected instance names
        """
        try:
            response = await self._client.list_instances()

            instances = []
            # Response is a list of instance objects
            if isinstance(response, list):
                for instance in response:
                    name = instance.get("instance", {}).get("instanceName")
                    state = instance.get("instance", {}).get("state")

                    # Only return connected instances
                    if name and state == "open":
                        instances.append(name)

            return instances

        except EvolutionApiError as e:
            raise ImageSourceError(
                source="instances",
                reason=str(e),
            )

    # Private helper methods

    async def _get_chats(self, instance_name: str) -> List[Dict[str, Any]]:
        """Get list of chats for an instance."""
        endpoint = f"/chat/findChats/{instance_name}"
        try:
            response = await self._client.post(endpoint, data={})
        except EvolutionApiError:
            # Fallback to GET if POST fails
            response = await self._client.get(endpoint)

        if isinstance(response, list):
            return response
        return response.get("chats", [])

    async def _get_messages(
        self,
        instance_name: str,
        remote_jid: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get messages for a specific chat."""
        endpoint = f"/chat/findMessages/{instance_name}"
        response = await self._client.post(
            endpoint,
            data={
                "where": {"key": {"remoteJid": remote_jid}},
                "limit": limit,
            },
        )

        logger.debug(f"findMessages response type: {type(response)}")

        messages = []
        if isinstance(response, list):
            messages = response
        elif isinstance(response, dict):
            # Try common response structures
            messages = (
                response.get("messages")
                or response.get("records")
                or response.get("data")
                or []
            )
            # Handle nested: {"messages": {"records": [...]}}
            if isinstance(messages, dict):
                messages = messages.get("records", [])
        else:
            logger.warning(f"Unexpected response type from findMessages: {type(response)}")
            return []

        # Filter out non-dict elements (some API versions return mixed types)
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
            elif isinstance(msg, str):
                # Try to parse JSON strings
                try:
                    import json
                    parsed = json.loads(msg)
                    if isinstance(parsed, dict):
                        result.append(parsed)
                except (json.JSONDecodeError, TypeError):
                    logger.debug(f"Skipping non-dict message: {type(msg)}")
            else:
                logger.debug(f"Skipping non-dict message: {type(msg)}")

        logger.info(f"Found {len(result)} messages for {remote_jid}")
        return result

    async def _get_status_updates(
        self,
        instance_name: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get status updates for an instance.

        Status messages in Evolution API are stored as messages
        with remoteJid='status@broadcast'. The participant field
        or pushName identifies who posted the status.
        """
        try:
            # Status updates live in the status@broadcast chat
            return await self._get_messages(
                instance_name=instance_name,
                remote_jid="status@broadcast",
                limit=limit,
            )
        except EvolutionApiError as e:
            logger.warning(f"Could not fetch status updates: {e}")
            return []

    async def _process_message(
        self,
        instance_name: str,
        message: Dict[str, Any],
        source_type: SourceType,
        request_phone_number: str = "",
    ) -> Optional[RawImageData]:
        """
        Process a message and extract image data if present.

        Args:
            instance_name: WhatsApp instance name
            message: Raw message dict from Evolution API
            source_type: Source type (chat or status)
            request_phone_number: Original phone number from the request,
                used as fallback when JID is LID format

        Returns None if message is not an image.
        """
        try:
            if not isinstance(message, dict):
                logger.debug(f"Skipping non-dict message: {type(message)}")
                return None

            # Extract message details
            key = message.get("key", {})
            if not isinstance(key, dict):
                logger.debug(f"Skipping message with non-dict key: {type(key)}")
                return None

            message_id = key.get("id")
            remote_jid = key.get("remoteJid", "")

            if not message_id:
                return None

            # Check for image message type
            msg_content = message.get("message", {})
            if not isinstance(msg_content, dict):
                return None

            # Handle different image message structures
            image_message = (
                msg_content.get("imageMessage")
                or msg_content.get("extendedTextMessage", {}).get("contextInfo", {}).get("quotedMessage", {}).get("imageMessage")
            )

            if not image_message:
                return None

            # Get mime type
            mime_type = image_message.get("mimetype", "image/jpeg")
            if mime_type not in self.SUPPORTED_IMAGE_TYPES:
                return None

            # Extract phone number from remoteJid
            phone = self._extract_phone_from_jid(remote_jid)

            # For LID JIDs, the extracted "phone" is the LID number, not real phone.
            # Use the request phone number as fallback.
            if remote_jid.endswith("@lid") and request_phone_number:
                phone = self._normalize_phone_number(request_phone_number)

            # Get user name from push name or contact
            push_name = message.get("pushName", "")

            # Download the actual image data
            image_bytes = await self._download_image_from_message(
                instance_name=instance_name,
                message=message,
            )

            if not image_bytes:
                return None

            return RawImageData(
                message_id=MessageId(message_id),
                source_type=source_type,
                phone_number=PhoneNumber(phone) if phone else PhoneNumber("0000000000"),
                user_name=UserName(push_name),
                instance=Instance(instance_name),
                image_bytes=image_bytes,
                original_mime_type=mime_type,
                timestamp=self._extract_timestamp(message),
            )

        except Exception as e:
            logger.warning(f"Failed to process message: {e}")
            return None

    async def _process_status(
        self,
        instance_name: str,
        status: Dict[str, Any],
        request_phone_number: str = "",
    ) -> Optional[RawImageData]:
        """
        Process a status update and extract image data if present.

        Returns None if status is not an image.
        """
        try:
            # Status structure may vary
            key = status.get("key", {})
            message_id = key.get("id") or status.get("id")
            remote_jid = key.get("remoteJid", "") or status.get("remoteJid", "")

            if not message_id:
                return None

            # Check for image in status
            msg_content = status.get("message", {})
            image_message = msg_content.get("imageMessage")

            if not image_message:
                return None

            mime_type = image_message.get("mimetype", "image/jpeg")
            if mime_type not in self.SUPPORTED_IMAGE_TYPES:
                return None

            phone = self._extract_phone_from_jid(remote_jid)
            if remote_jid.endswith("@lid") and request_phone_number:
                phone = self._normalize_phone_number(request_phone_number)
            push_name = status.get("pushName", "")

            # Download status image
            image_bytes = await self._download_image_from_message(
                instance_name=instance_name,
                message=status,
            )

            if not image_bytes:
                return None

            return RawImageData(
                message_id=MessageId(str(message_id)),
                source_type=SourceType.STATUS,
                phone_number=PhoneNumber(phone) if phone else PhoneNumber("0000000000"),
                user_name=UserName(push_name),
                instance=Instance(instance_name),
                image_bytes=image_bytes,
                original_mime_type=mime_type,
                timestamp=self._extract_timestamp(status),
            )

        except Exception as e:
            logger.warning(f"Failed to process status: {e}")
            return None

    async def _download_image_from_message(
        self,
        instance_name: str,
        message: Dict[str, Any],
    ) -> Optional[bytes]:
        """Download image bytes from a message."""
        try:
            endpoint = f"/chat/getBase64FromMediaMessage/{instance_name}"

            # Build the message key structure
            key = message.get("key", {})

            response = await self._client.post(
                endpoint,
                data={"message": {"key": key}},
            )

            base64_data = response.get("base64", "")
            if not base64_data:
                return None

            # Remove data URL prefix if present
            if "," in base64_data:
                base64_data = base64_data.split(",", 1)[1]

            return base64.b64decode(base64_data)

        except Exception as e:
            msg_id = key.get("id", "unknown") if isinstance(key, dict) else "unknown"
            logger.warning(
                f"Failed to download image (msg_id={msg_id}): {e}. "
                f"This usually means the WhatsApp media URL has expired."
            )
            return None

    def _extract_phone_from_jid(self, jid: str) -> str:
        """Extract phone number from WhatsApp JID."""
        if not jid:
            return ""

        # JID format: number@s.whatsapp.net or number@g.us (groups)
        parts = jid.split("@")
        if parts:
            # Remove any non-digit characters
            import re
            return re.sub(r"\D", "", parts[0])

        return ""

    def _extract_timestamp(self, message: Dict[str, Any]) -> datetime:
        """Extract timestamp from message."""
        from datetime import timezone

        timestamp = message.get("messageTimestamp")
        if timestamp:
            try:
                if isinstance(timestamp, (int, float)):
                    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
                dt = datetime.fromisoformat(str(timestamp))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, OSError):
                pass

        return datetime.now(timezone.utc)
