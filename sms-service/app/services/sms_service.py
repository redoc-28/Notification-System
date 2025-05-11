import logging
import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from app.core.config import get_settings
from app.models.sms import SMSStatus, SMSMessage
from app.db.database import db_client

logger = logging.getLogger(__name__)


class SMSService:
    """Service for sending SMS messages using various providers"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def process_sms(self, message_data: Dict[str, Any], headers: Dict[str, Any]) -> bool:
        """
        Process an SMS message from RabbitMQ
        
        Args:
            message_data: Message data
            headers: Message headers
            
        Returns:
            bool: Success status
        """
        try:
            # Extract data from message
            notification_id = message_data.get("notification_id")
            user_id = message_data.get("user_id")
            content = message_data.get("content", {})
            metadata = message_data.get("metadata", {})
            
            # Check if required fields are present
            if not all([notification_id, user_id, content, content.get("body")]):
                logger.error(f"Missing required fields in message: {notification_id}")
                return False
            
            # Create SMSMessage object
            sms_message = SMSMessage(
                notification_id=notification_id,
                user_id=user_id,
                body=content.get("body", ""),
                sender_id=content.get("sender_id") or self.settings.DEFAULT_SENDER_ID,
                metadata=metadata,
                created_at=datetime.fromisoformat(message_data.get("created_at", datetime.now().isoformat())),
                scheduled_at=datetime.fromisoformat(message_data.get("scheduled_at")) if message_data.get("scheduled_at") else None,
                priority=message_data.get("priority", "medium")
            )
            
            # Get retry count from headers
            retry_count = headers.get("retry_count", 0)
            
            # Generate log ID
            log_id = str(uuid.uuid4())
            
            # Log initial attempt
            await db_client.log_sms_delivery(
                log_id=log_id,
                notification_id=notification_id,
                user_id=user_id,
                provider=self.settings.SMS_PROVIDER,
                status=SMSStatus.PENDING,
                body=sms_message.body,
                sender_id=sms_message.sender_id,
                retry_count=retry_count,
                metadata=metadata
            )
            
            # Send the SMS
            success, provider_message_id, error_message = await self._send_sms(sms_message)
            
            # Update status based on result
            status = SMSStatus.SENT if success else SMSStatus.FAILED
            sent_at = datetime.now() if success else None
            
            # Update log with result
            await db_client.update_sms_status(
                log_id=log_id,
                status=status,
                provider_message_id=provider_message_id,
                error_message=error_message
            )
            
            if success:
                logger.info(f"SMS sent successfully: {notification_id}")
            else:
                logger.error(f"Failed to send SMS: {notification_id}, error: {error_message}")
                
            return success
            
        except Exception as e:
            logger.exception(f"Error processing SMS: {str(e)}")
            return False
            
    async def _send_sms(self, sms: SMSMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an SMS using the configured provider
        
        Args:
            sms: SMSMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        # Get the SMS provider to use
        provider = self.settings.SMS_PROVIDER.lower()
        
        try:
            if provider == "twilio":
                return await self._send_with_twilio(sms)
            elif provider == "sns":
                return await self._send_with_sns(sms)
            elif provider == "nexmo":
                return await self._send_with_nexmo(sms)
            else:
                error_message = f"Unknown SMS provider: {provider}"
                logger.error(error_message)
                return False, None, error_message
                
        except Exception as e:
            error_message = f"Error sending SMS: {str(e)}"
            logger.exception(error_message)
            return False, None, error_message
    
    async def _send_with_twilio(self, sms: SMSMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an SMS using Twilio
        
        Args:
            sms: SMSMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import Twilio here to avoid dependency if not using
            from twilio.rest import Client
            
            if not all([self.settings.TWILIO_ACCOUNT_SID, self.settings.TWILIO_AUTH_TOKEN, self.settings.TWILIO_PHONE_NUMBER]):
                return False, None, "Twilio credentials not configured"
            
            # Create Twilio client
            client = Client(self.settings.TWILIO_ACCOUNT_SID, self.settings.TWILIO_AUTH_TOKEN)
            
            # Send the message
            message = client.messages.create(
                body=sms.body,
                from_=self.settings.TWILIO_PHONE_NUMBER,
                to=sms.user_id  # Assuming user_id is the phone number
            )
            
            # Extract the message ID
            message_id = message.sid
            
            # Success
            return True, message_id, None
            
        except Exception as e:
            return False, None, f"Twilio error: {str(e)}"
    
    async def _send_with_sns(self, sms: SMSMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an SMS using AWS SNS
        
        Args:
            sms: SMSMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import boto3 here to avoid dependency if not using
            import boto3
            from botocore.exceptions import ClientError
            
            if not all([self.settings.AWS_ACCESS_KEY_ID, self.settings.AWS_SECRET_ACCESS_KEY, self.settings.AWS_REGION]):
                return False, None, "AWS SNS settings not configured"
            
            # Create a new SNS client
            client = boto3.client(
                'sns',
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
                region_name=self.settings.AWS_REGION
            )
            
            # Send the message
            response = client.publish(
                PhoneNumber=sms.user_id,  # Assuming user_id is the phone number
                Message=sms.body,
                MessageAttributes={
                    'AWS.SNS.SMS.SenderID': {
                        'DataType': 'String',
                        'StringValue': sms.sender_id or self.settings.DEFAULT_SENDER_ID
                    },
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'  # or 'Promotional'
                    }
                }
            )
            
            # Extract the message ID
            message_id = response.get('MessageId')
            
            # Success
            return True, message_id, None
            
        except ClientError as e:
            return False, None, f"AWS SNS error: {str(e)}"
        except Exception as e:
            return False, None, f"AWS SNS error: {str(e)}"
    
    async def _send_with_nexmo(self, sms: SMSMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an SMS using Nexmo/Vonage
        
        Args:
            sms: SMSMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import Vonage here to avoid dependency if not using
            import vonage
            
            if not all([self.settings.NEXMO_API_KEY, self.settings.NEXMO_API_SECRET]):
                return False, None, "Nexmo/Vonage credentials not configured"
            
            # Create Vonage client
            client = vonage.Client(
                key=self.settings.NEXMO_API_KEY,
                secret=self.settings.NEXMO_API_SECRET
            )
            sms_client = vonage.Sms(client)
            
            # Send the SMS
            response = sms_client.send_message({
                'from': sms.sender_id or self.settings.NEXMO_FROM or self.settings.DEFAULT_SENDER_ID,
                'to': sms.user_id,  # Assuming user_id is the phone number
                'text': sms.body
            })
            
            # Check response
            if response["messages"][0]["status"] == "0":
                # Success
                return True, response["messages"][0]["message-id"], None
            else:
                # Failure
                return False, None, f"Nexmo error: {response['messages'][0]['error-text']}"
                
        except Exception as e:
            return False, None, f"Nexmo error: {str(e)}"


# Singleton instance
sms_service = SMSService()