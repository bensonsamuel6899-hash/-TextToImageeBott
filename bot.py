import os
import logging
import asyncio
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import aiohttp
import json

# ===== CONFIGURATION =====
# Try multiple possible environment variable names
TOKEN = (
    os.environ.get("TELEGRAM_TOKEN") or 
    os.environ.get("BOT_TOKEN") or 
    os.environ.get("TOKEN")
)

# API Keys for different image generation services
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# ===== LOGGING SETUP =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== TOKEN VALIDATION =====
if not TOKEN:
    logger.error("❌ NO TOKEN FOUND! Please set TELEGRAM_TOKEN environment variable.")
    logger.error(f"Available env vars: {list(os.environ.keys())}")
    exit(1)

logger.info(f"✅ Token loaded successfully! First 10 chars: {TOKEN[:10]}...")
logger.info(f"✅ Gemini API Key: {'✅ Set' if GEMINI_API_KEY else '❌ Not set'}")
logger.info(f"✅ OpenAI API Key: {'✅ Set' if OPENAI_API_KEY else '❌ Not set'}")
logger.info(f"✅ OpenRouter API Key: {'✅ Set' if OPENROUTER_API_KEY else '❌ Not set'}")

# ===== HELPER FUNCTIONS =====
async def generate_image_with_gemini(prompt: str):
    """Generate image using Google Gemini API"""
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured."
    
    # Use the correct model name for the Gemini API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]  # This is required for image generation!
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract image from response
                    if "candidates" in data and data["candidates"]:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            for part in candidate["content"]["parts"]:
                                if "inlineData" in part:
                                    # Image data is base64 encoded
                                    image_data = part["inlineData"]["data"]
                                    return image_data, "Image generated successfully!"
                                
                                elif "text" in part:
                                    # The model might return text along with the image
                                    continue
                    
                    return None, "No image data found in response"
                else:
                    error_text = await response.text()
                    return None, f"API Error: {response.status} - {error_text}"
    except Exception as e:
        logger.error(f"Gemini API Error: {str(e)}")
        return None, f"Error: {str(e)}"

async def generate_image_with_openai(prompt: str):
    """Generate image using OpenAI DALL-E API"""
    if not OPENAI_API_KEY:
        return None, "OpenAI API key not configured."
    
    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "dall-e-2",
        "prompt": prompt,
        "n": 1,
        "size": "512x512"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if "data" in data and data["data"]:
                        image_url = data["data"][0]["url"]
                        return image_url, "Image generated successfully!"
                    else:
                        return None, "No image generated."
                else:
                    error_text = await response.text()
                    return None, f"API Error: {response.status}"
    except Exception as e:
        logger.error(f"OpenAI API Error: {str(e)}")
        return None, f"Error: {str(e)}"

async def generate_image_with_openrouter(prompt: str):
    """Generate image using OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return None, "OpenRouter API key not configured."
    
    url = "https://openrouter.ai/api/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "black-forest-labs/flux-1.1-pro",
        "prompt": prompt
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if "data" in data and data["data"]:
                        image_url = data["data"][0]["url"]
                        return image_url, "Image generated successfully!"
                    else:
                        return None, "No image generated."
                else:
                    error_text = await response.text()
                    return None, f"API Error: {response.status}"
    except Exception as e:
        logger.error(f"OpenRouter API Error: {str(e)}")
        return None, f"Error: {str(e)}"

# ===== BOT COMMAND HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    welcome_message = (
        "🎨 *Welcome to TextToImage Bot!*\n\n"
        "I can generate images from text descriptions using AI.\n\n"
        "✨ *How to use:*\n"
        "1. Just send me any text description\n"
        "2. I'll generate an image based on your prompt\n"
        "3. The image will be sent back to you\n\n"
        "🔧 *Available Commands:*\n"
        "/start - Show this message\n"
        "/help - Show help information\n"
        "/about - About this bot\n"
        "/model - Change AI model\n"
        "/status - Check bot status\n\n"
        "💡 *Example:* Send \"A beautiful sunset over mountains\""
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    help_text = (
        "🤖 *Help Center*\n\n"
        "📝 *Tips for best results:*\n"
        "• Be descriptive and specific\n"
        "• Include details like style, colors, mood\n"
        "• Example: 'A cyberpunk city at night, neon lights, rain'\n\n"
        "🔄 *Supported Models:*\n"
        "• Gemini 2.0 Flash (if configured)\n"
        "• OpenAI DALL-E 2 (if configured)\n"
        "• Flux Pro (if configured)\n\n"
        "⚠️ *Rate Limits:*\n"
        "• 5 images per user per day\n"
        "• Please be patient with generation time"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send about information."""
    about_text = (
        "📱 *About This Bot*\n\n"
        "🤖 *Name:* TextToImage Bot\n"
        "📝 *Username:* @TextToImageeBot\n"
        "🔧 *Version:* 2.0.0\n"
        "🛠 *Built with:* python-telegram-bot 21.9\n"
        "🎯 *Purpose:* Generate AI images from text\n\n"
        "📚 *Source Code:* Available on GitHub\n"
        "💻 *Deployed on:* Railway"
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status."""
    status_text = (
        "📊 *Bot Status*\n\n"
        "✅ *Status:* Online and ready\n"
        "🔐 *API Status:*\n"
        f"• Gemini: {'✅ Connected' if GEMINI_API_KEY else '❌ Not configured'}\n"
        f"• OpenAI: {'✅ Connected' if OPENAI_API_KEY else '❌ Not configured'}\n"
        f"• OpenRouter: {'✅ Connected' if OPENROUTER_API_KEY else '❌ Not configured'}\n\n"
        "⚡ *Uptime:* Active and running"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change AI model."""
    keyboard = [
        [InlineKeyboardButton("🧠 Gemini", callback_data="model_gemini")],
        [InlineKeyboardButton("🎨 OpenAI DALL-E", callback_data="model_openai")],
        [InlineKeyboardButton("⚡ OpenRouter Flux", callback_data="model_openrouter")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 *Select AI Model*\n\nChoose which AI model to use for image generation:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages and generate images."""
    user = update.effective_user
    prompt = update.message.text.strip()
    
    if not prompt:
        await update.message.reply_text("❌ Please send a valid prompt!")
        return
    
    # Check if user has a preferred model
    user_model = context.user_data.get("model", "gemini")
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        f"🎨 *Generating image for:*\n\n\"{prompt}\"\n\n⏳ Please wait..."
    )
    
    # Generate image based on selected model
    image_result = None
    error_message = None
    
    try:
        if user_model == "gemini" and GEMINI_API_KEY:
            image_result, error_message = await generate_image_with_gemini(prompt)
        elif user_model == "openai" and OPENAI_API_KEY:
            image_result, error_message = await generate_image_with_openai(prompt)
        elif user_model == "openrouter" and OPENROUTER_API_KEY:
            image_result, error_message = await generate_image_with_openrouter(prompt)
        else:
            # Fallback to any available API
            if GEMINI_API_KEY:
                image_result, error_message = await generate_image_with_gemini(prompt)
            elif OPENAI_API_KEY:
                image_result, error_message = await generate_image_with_openai(prompt)
            elif OPENROUTER_API_KEY:
                image_result, error_message = await generate_image_with_openrouter(prompt)
            else:
                await processing_msg.edit_text(
                    "❌ No AI image generation API is configured!\n\n"
                    "Please add one of these environment variables:\n"
                    "• GEMINI_API_KEY\n"
                    "• OPENAI_API_KEY\n"
                    "• OPENROUTER_API_KEY"
                )
                return
        
        # Delete processing message
        await processing_msg.delete()
        
        if image_result:
            # Check if it's base64 image data (from Gemini)
            if not image_result.startswith("http") and len(image_result) > 100:
                # It's base64 encoded image data
                image_bytes = base64.b64decode(image_result)
                await update.message.reply_photo(
                    image_bytes, 
                    caption=f"🖼️ *Generated Image*\n📝 *Prompt:* {prompt}\n🤖 *Model:* {user_model.upper()}",
                    parse_mode="Markdown"
                )
            elif image_result.startswith("http"):
                # URL - send as photo
                await update.message.reply_photo(
                    image_result, 
                    caption=f"🖼️ *Generated Image*\n📝 *Prompt:* {prompt}\n🤖 *Model:* {user_model.upper()}",
                    parse_mode="Markdown"
                )
            else:
                # Local file path
                await update.message.reply_text(
                    f"✅ Image generated successfully!\n\n"
                    f"📝 *Prompt:* {prompt}\n"
                    f"🤖 *Model:* {user_model.upper()}",
                    parse_mode="Markdown"
                )
        else:
            # Error occurred
            await update.message.reply_text(
                f"❌ *Failed to generate image*\n\n"
                f"📝 *Prompt:* {prompt}\n"
                f"⚠️ *Error:* {error_message}\n\n"
                f"💡 Try again with a different prompt or choose a different model with /model"
            )
            
    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        await processing_msg.delete()
        await update.message.reply_text(
            f"❌ *Unexpected Error*\n\n"
            f"Something went wrong: {str(e)}\n\n"
            f"Please try again later."
        )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("model_"):
        model = query.data.replace("model_", "")
        context.user_data["model"] = model
        
        model_names = {
            "gemini": "🧠 Google Gemini",
            "openai": "🎨 OpenAI DALL-E",
            "openrouter": "⚡ OpenRouter Flux"
        }
        
        await query.edit_message_text(
            f"✅ Model changed to: {model_names.get(model, model)}!\n\n"
            f"Send me a prompt to generate an image with the new model."
        )

# ===== ERROR HANDLING =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}")

# ===== MAIN APPLICATION =====
def main():
    """Start the bot."""
    logger.info("🚀 Starting TextToImage Bot...")
    logger.info(f"🤖 Bot Username: @TextToImageeBot")
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("model", model_command))
    
    # Add message handler for text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    logger.info("✅ Bot is ready! Starting polling...")
    
    # Start the Bot with long polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
