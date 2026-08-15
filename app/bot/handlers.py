"""Telegram bot handlers."""
from telegram import Message, Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from app.bot.telegram_service import TelegramService
from app.config.settings import get_settings
from app.ingestion.models import ContentInput, ContentType
from app.memory.service import MemoryService
from app.services.content_service import ContentService
from app.utils.exceptions import (
    ContentTooLargeError,
    DuplicateContentError,
    EmptyContentError,
    IngestionError,
    UnsupportedContentError,
    ValidationError,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BotHandlers:
    """Telegram bot command and message handlers."""
    
    def __init__(
        self,
        telegram_service: TelegramService,
        content_service: ContentService,
        memory_service: MemoryService,
    ):
        self.telegram_service = telegram_service
        self.content_service = content_service
        self.memory_service = memory_service
        self.settings = get_settings()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        welcome_message = (
            "👋 Welcome to the Content Agent!\n\n"
            "I can help you create engaging social media content from:\n"
            "• 📝 Plain text\n"
            "• 🔗 URLs (articles, blog posts)\n"
            "• 📄 PDF documents\n\n"
            "Just send me any of these and I'll generate:\n"
            "✨ A compelling title\n"
            "📋 Editorial rationale\n"
            "🏷️ Relevant category\n"
            "🐦 X/Twitter post (≤280 chars)\n"
            "💼 LinkedIn post (professional, structured)\n\n"
            "Commands:\n"
            "/setstyle <description> - Set your writing style\n"
            "/getstyle - View your current style\n"
            "/clearstyle - Clear your style preference\n\n"
            "Try sending me some content!"
        )
        await self.telegram_service.send_message(update.effective_chat.id, welcome_message)  # type: ignore[union-attr]
    
    async def setstyle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /setstyle command."""
        user_id = update.effective_user.id  # type: ignore[union-attr]
        
        # Extract style from command
        if not context.args:
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                "❌ Please provide a style description.\n"
                "Example: /setstyle Write in a witty, informal tone."
            )
            return
        
        style_prompt = " ".join(context.args).strip()
        
        if not style_prompt:
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                "❌ Style description cannot be empty."
            )
            return
        
        if len(style_prompt) > self.settings.max_style_length:
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                f"❌ Style too long (max {self.settings.max_style_length} characters)."
            )
            return
        
        try:
            await self.memory_service.set_style(user_id, style_prompt)
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                f"✅ Style updated:\n\n_{style_prompt}_",
                parse_mode="Markdown"
            )
        except ValidationError as e:
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                f"❌ {e.message}"
            )
        except (OSError, RuntimeError) as e:
            logger.error("Failed to set style", user_id=user_id, error=str(e))
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                "⚠️ Failed to save style. Please try again."
            )
    
    async def getstyle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /getstyle command."""
        user_id = update.effective_user.id  # type: ignore[union-attr]
        
        try:
            style = await self.memory_service.get_style(user_id)
            if style:
                await self.telegram_service.send_message(
                    update.effective_chat.id,  # type: ignore[union-attr]
                    f"📝 Your current style:\n\n_{style}_",
                    parse_mode="Markdown"
                )
            else:
                await self.telegram_service.send_message(
                    update.effective_chat.id,  # type: ignore[union-attr]
                    "📝 No style set. Use /setstyle to add one."
                )
        except (OSError, RuntimeError) as e:
            logger.error("Failed to get style", user_id=user_id, error=str(e))
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                "⚠️ Failed to retrieve style."
            )
    
    async def clearstyle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clearstyle command."""
        user_id = update.effective_user.id  # type: ignore[union-attr]
        
        try:
            cleared = await self.memory_service.clear_style(user_id)
            if cleared:
                await self.telegram_service.send_message(
                    update.effective_chat.id,  # type: ignore[union-attr]
                    "✅ Style cleared."
                )
            else:
                await self.telegram_service.send_message(
                    update.effective_chat.id,  # type: ignore[union-attr]
                    "📝 No style was set."
                )
        except (OSError, RuntimeError) as e:
            logger.error("Failed to clear style", user_id=user_id, error=str(e))
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                "⚠️ Failed to clear style."
            )
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle plain text messages."""
        message = update.message
        if not message or not message.text:
            return
        
        # Skip commands
        if message.text.startswith("/"):
            return
        
        await self._process_content(update, message, ContentInput(
            content_type=ContentType.TEXT,
            source_identifier=f"text:{message.message_id}",
            raw_content=message.text,
            user_id=update.effective_user.id,  # type: ignore[union-attr]
            message_id=message.message_id,
        ))
    
    async def handle_url_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle messages containing URLs."""
        message = update.message
        if not message or not message.text:
            return
        
        # Extract URLs - if message is primarily a single URL, treat as URL
        from app.utils.text import extract_urls
        from app.utils.urls import is_valid_http_url
        urls = extract_urls(message.text)
        
        if len(urls) == 1 and is_valid_http_url(urls[0]) and urls[0] == message.text.strip():
            await self._process_content(update, message, ContentInput(
                content_type=ContentType.URL,
                source_identifier=urls[0],
                raw_content=urls[0],
                user_id=update.effective_user.id,  # type: ignore[union-attr]
                message_id=message.message_id,
            ))
        else:
            # Multiple URLs or mixed content - treat as text
            await self.handle_text_message(update, context)
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document uploads (PDF)."""
        message = update.message
        if not message or not message.document:
            return
        
        document = message.document
        
        # Check if PDF
        mime_type = document.mime_type or ""
        filename = document.file_name or "document.pdf"
        
        if mime_type != "application/pdf" and not filename.lower().endswith(".pdf"):
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                "❌ I currently support text, URLs, and PDF files only."
            )
            return
        
        # Check file size
        max_size = self.settings.max_pdf_size_mb * 1024 * 1024
        if document.file_size and document.file_size > max_size:
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                f"❌ PDF too large (max {self.settings.max_pdf_size_mb}MB)."
            )
            return
        
        # Send processing message
        processing_msg = await self.telegram_service.send_message(
            update.effective_chat.id,  # type: ignore[union-attr]
            "⏳ Downloading and processing PDF..."
        )
        
        try:
            # Download file
            file = await context.bot.get_file(document.file_id)
            
            # Save to temp file
            import os
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                temp_path = tmp.name
                await file.download_to_drive(temp_path)
            
            try:
                await self._process_content(update, message, ContentInput(
                    content_type=ContentType.PDF,
                    source_identifier=f"pdf:{filename}",
                    raw_content=temp_path,  # File path for extractor
                    metadata={
                        "filename": filename,
                        "mime_type": mime_type,
                        "file_size": document.file_size,
                        "is_document": True,
                    },
                    user_id=update.effective_user.id,  # type: ignore[union-attr]
                    message_id=message.message_id,
                ))
            finally:
                # Cleanup temp file
                try:
                    os.unlink(temp_path)
                except OSError as e:
                    logger.warning("Failed to cleanup temp file", path=temp_path, error=str(e))
            
            # Delete processing message
            try:
                await processing_msg.delete()  # type: ignore[union-attr]
            except (OSError, RuntimeError) as e:
                logger.warning("Failed to delete processing message", error=str(e))
                
        except (OSError, RuntimeError) as e:
            logger.error("PDF handling failed", error=str(e))
            await self.telegram_service.send_message(
                update.effective_chat.id,  # type: ignore[union-attr]
                "⚠️ Failed to process PDF. Please try again."
            )
            try:
                await processing_msg.delete()  # type: ignore[union-attr]
            except (OSError, RuntimeError) as e:
                logger.warning("Failed to delete processing message", error=str(e))
    
    async def _process_content(
        self,
        update: Update,
        message: Message,
        content_input: ContentInput,
    ) -> None:
        """Process content through pipeline."""
        chat_id = update.effective_chat.id  # type: ignore[union-attr]
        
        # Send processing indicator
        processing_msg = await self.telegram_service.send_message(
            chat_id,
            "⏳ Processing your content..."
        )
        
        try:
            is_new, _fingerprint, result = await self.content_service.process_content(content_input)
            
            if is_new and result:
                # Success
                response = (
                    "✅ Content generated and saved!\n\n"
                    f"📌 *Title:* {result.title}\n"
                    f"🏷️ *Category:* {result.category}\n"
                    f"🐦 *X Post:* {result.variants.x_post}\n"
                    f"💼 *LinkedIn Post:* {result.variants.linkedin_post[:200]}{'...' if len(result.variants.linkedin_post) > 200 else ''}"
                )
                await self.telegram_service.send_message(chat_id, response, parse_mode="Markdown")
            else:
                # Should not reach here due to exception
                await self.telegram_service.send_message(
                    chat_id,
                    "ℹ️ This content with your current style was already processed."
                )
                
        except DuplicateContentError:
            await self.telegram_service.send_message(
                chat_id,
                "ℹ️ This content with your current style was already processed."
            )
        except UnsupportedContentError as e:
            await self.telegram_service.send_message(
                chat_id,
                f"❌ {e.message}"
            )
        except EmptyContentError:
            await self.telegram_service.send_message(
                chat_id,
                "❌ Content cannot be empty."
            )
        except ContentTooLargeError as e:
            await self.telegram_service.send_message(
                chat_id,
                f"❌ {e.message}"
            )
        except ValidationError as e:
            await self.telegram_service.send_message(
                chat_id,
                f"❌ {e.message}"
            )
        except IngestionError as e:
            await self.telegram_service.send_message(
                chat_id,
                f"❌ {e.message}"
            )
        except (OSError, RuntimeError) as e:
            logger.error("Content processing failed", error=str(e), user_id=update.effective_user.id)  # type: ignore[union-attr]
            await self.telegram_service.send_message(
                chat_id,
                "⚠️ I couldn't process that content right now. Please try again."
            )
        finally:
            # Clean up processing message
            try:
                await processing_msg.delete()  # type: ignore[union-attr]
            except (OSError, RuntimeError) as e:
                logger.warning("Failed to delete processing message", error=str(e))
    
    def get_handlers(self) -> list:
        """Get all handlers for registration."""
        return [
            CommandHandler("start", self.start_command),
            CommandHandler("setstyle", self.setstyle_command),
            CommandHandler("getstyle", self.getstyle_command),
            CommandHandler("clearstyle", self.clearstyle_command),
            MessageHandler(filters.Document.ALL, self.handle_document),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message),
        ]