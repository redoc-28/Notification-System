import logging
import uuid
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import get_settings
from app.models.email import EmailStatus, EmailMessage
from app.db.database import db_client

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails using various providers"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def process_email(self, message_data: Dict[str, Any], headers: Dict[str, Any]) -> bool:
        """
        Process an email message from RabbitMQ
        
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
            if not all([notification_id, user_id, content]):
                logger.error(f"Missing required fields in message: {notification_id}")
                return False
            
            # Create EmailMessage object
            email_message = EmailMessage(
                notification_id=notification_id,
                user_id=user_id,
                subject=content.get("subject", ""),
                body_text=content.get("body_text", ""),
                body_html=content.get("body_html"),
                from_email=content.get("from_email") or self.settings.DEFAULT_FROM_EMAIL,
                reply_to=content.get("reply_to") or self.settings.DEFAULT_REPLY_TO,
                cc=content.get("cc"),
                bcc=content.get("bcc"),
                attachments=content.get("attachments"),
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
            await db_client.log_email_delivery(
                log_id=log_id,
                notification_id=notification_id,
                user_id=user_id,
                provider=self.settings.EMAIL_PROVIDER,
                status=EmailStatus.PENDING,
                subject=email_message.subject,
                retry_count=retry_count,
                metadata=metadata
            )
            
            # Send the email
            success, provider_message_id, error_message = await self._send_email(email_message)
            
            # Update status based on result
            status = EmailStatus.SENT if success else EmailStatus.FAILED
            sent_at = datetime.now() if success else None
            
            # Update log with result
            await db_client.update_email_status(
                log_id=log_id,
                status=status,
                provider_message_id=provider_message_id,
                error_message=error_message
            )
            
            if success:
                logger.info(f"Email sent successfully: {notification_id}")
            else:
                logger.error(f"Failed to send email: {notification_id}, error: {error_message}")
                
            return success
            
        except Exception as e:
            logger.exception(f"Error processing email: {str(e)}")
            return False
            
    async def _send_email(self, email: EmailMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an email using the configured provider
        
        Args:
            email: EmailMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        # Get the email provider to use
        provider = self.settings.EMAIL_PROVIDER.lower()
        
        try:
            if provider == "sendgrid":
                return await self._send_with_sendgrid(email)
            elif provider == "smtp":
                return await self._send_with_smtp(email)
            elif provider == "ses":
                return await self._send_with_ses(email)
            else:
                error_message = f"Unknown email provider: {provider}"
                logger.error(error_message)
                return False, None, error_message
                
        except Exception as e:
            error_message = f"Error sending email: {str(e)}"
            logger.exception(error_message)
            return False, None, error_message
    
    async def _send_with_sendgrid(self, email: EmailMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an email using SendGrid
        
        Args:
            email: EmailMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import SendGrid here to avoid dependency if not using
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent
            
            if not self.settings.SENDGRID_API_KEY:
                return False, None, "SendGrid API key not configured"
            
            # Create SendGrid client
            sg = sendgrid.SendGridAPIClient(api_key=self.settings.SENDGRID_API_KEY)
            
            # Create mail object
            from_email = Email(email.from_email)
            to_email = To(email.user_id)  # Assuming user_id is the email address
            subject = email.subject
            content = Content("text/plain", email.body_text)
            mail = Mail(from_email, to_email, subject, content)
            
            # Add HTML content if present
            if email.body_html:
                mail.add_content(HtmlContent(email.body_html))
            
            # Add CC recipients if present
            if email.cc:
                for cc_address in email.cc:
                    mail.add_cc(Email(cc_address))
            
            # Add BCC recipients if present
            if email.bcc:
                for bcc_address in email.bcc:
                    mail.add_bcc(Email(bcc_address))
            
            # Add custom headers for tracking
            mail.add_custom_arg("notification_id", email.notification_id)
            
            # Send the email
            response = sg.client.mail.send.post(request_body=mail.get())
            
            # Check response
            if response.status_code >= 200 and response.status_code < 300:
                # Success
                return True, None, None  # SendGrid doesn't provide a message ID in the response
            else:
                # Failure
                return False, None, f"SendGrid API error: {response.status_code} - {response.body}"
                
        except Exception as e:
            return False, None, f"SendGrid error: {str(e)}"
    
    async def _send_with_smtp(self, email: EmailMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an email using SMTP
        
        Args:
            email: EmailMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        if not all([self.settings.SMTP_HOST, self.settings.SMTP_PORT]):
            return False, None, "SMTP settings not configured"
        
        try:
            # Create a multipart message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email.subject
            msg['From'] = email.from_email
            msg['To'] = email.user_id  # Assuming user_id is the email address
            
            # Add Reply-To if specified
            if email.reply_to:
                msg['Reply-To'] = email.reply_to
            
            # Add CC if specified
            if email.cc:
                msg['Cc'] = ', '.join(email.cc)
            
            # Add text body
            msg.attach(MIMEText(email.body_text, 'plain'))
            
            # Add HTML body if present
            if email.body_html:
                msg.attach(MIMEText(email.body_html, 'html'))
            
            # Create SMTP connection
            with smtplib.SMTP(self.settings.SMTP_HOST, self.settings.SMTP_PORT) as server:
                # Use TLS if enabled
                if self.settings.SMTP_USE_TLS:
                    server.starttls()
                
                # Login if credentials are provided
                if self.settings.SMTP_USER and self.settings.SMTP_PASSWORD:
                    server.login(self.settings.SMTP_USER, self.settings.SMTP_PASSWORD)
                
                # Calculate all recipients
                all_recipients = [email.user_id]
                if email.cc:
                    all_recipients.extend(email.cc)
                if email.bcc:
                    all_recipients.extend(email.bcc)
                
                # Send the email
                server.sendmail(email.from_email, all_recipients, msg.as_string())
                
                # Success
                return True, None, None
                
        except Exception as e:
            return False, None, f"SMTP error: {str(e)}"
    
    async def _send_with_ses(self, email: EmailMessage) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send an email using AWS SES
        
        Args:
            email: EmailMessage to send
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (success, provider_message_id, error_message)
        """
        try:
            # Import boto3 here to avoid dependency if not using
            import boto3
            from botocore.exceptions import ClientError
            
            if not all([self.settings.AWS_ACCESS_KEY_ID, self.settings.AWS_SECRET_ACCESS_KEY, self.settings.AWS_REGION]):
                return False, None, "AWS SES settings not configured"
            
            # Create a new SES client
            client = boto3.client(
                'ses',
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
                region_name=self.settings.AWS_REGION
            )
            
            # Create message
            message = {
                'Subject': {
                    'Data': email.subject
                },
                'Body': {
                    'Text': {
                        'Data': email.body_text
                    }
                }
            }
            
            # Add HTML body if present
            if email.body_html:
                message['Body']['Html'] = {
                    'Data': email.body_html
                }
            
            # Prepare destination
            destination = {
                'ToAddresses': [email.user_id]  # Assuming user_id is the email address
            }
            
            # Add CC and BCC if present
            if email.cc:
                destination['CcAddresses'] = email.cc
            if email.bcc:
                destination['BccAddresses'] = email.bcc
            
            # Send the email
            response = client.send_email(
                Source=email.from_email,
                Destination=destination,
                Message=message,
                ReplyToAddresses=[email.reply_to] if email.reply_to else None,
                Tags=[
                    {
                        'Name': 'notification_id',
                        'Value': email.notification_id
                    }
                ]
            )
            
            # Extract the message ID
            message_id = response.get('MessageId')
            
            # Success
            return True, message_id, None
            
        except ClientError as e:
            return False, None, f"AWS SES error: {str(e)}"
        except Exception as e:
            return False, None, f"AWS SES error: {str(e)}"


# Singleton instance
email_service = EmailService()