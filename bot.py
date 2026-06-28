import os
import logging
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import aiohttp
import json

# ===== CONFIGURATION =====
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# ===== LOGGING SETUP =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== TOKEN VALIDATION =====
if not TOKEN:
    logger.error("❌ NO TOKEN FOUND!")
    exit(1)

logger.info(f"✅ Token loaded: {TOKEN[:10]}...")
logger.info(f"✅ Gemini API: {'✅ Set' if GEMINI_API_KEY else '❌ Not set'}")
logger.info(f"✅ OpenRouter API: {'✅ Set' if OPENROUTER_API_KEY else '❌ Not set'}")

# ===== IMAGE GENERATION FUNCTIONS =====
async def generate_with_openrouter(prompt: str):
    """Generate image using OpenRouter API"""
    if not OPENROUTER_API_KEY:
        return None, "OpenRouter API key not configured."
    
    url = "https://openrouter.ai/api/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/TextToImageeBot",
        "X-Title": "TextToImage Bot"
    }
    payload = {
        "model": "black-forest-labs/flux-1.1-pro",
        "prompt": prompt,
        "width": 512,
        "height": 512,
        "num_images": 1
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if "data" in data and data["data"]:
                        image_url = data["data"][0]["url"]
                        return image_url, None
                    else:
                        return None, "No image in response"
                else:
                    error_text = await response.text()
                    logger.error(f"OpenRouter Error: {error_text}")
                    return None, f"API Error: {response.status}"
    except Exception as e:
        logger.error(f"OpenRouter Error: {str(e)}")
        return None, str(e)

async def generate_with_gemini(prompt: str):
    """Generate image using Google Gemini API"""
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if "candidates" in data and data["candidates"]:
                        for part in data["candidates"][0]["content"]["parts"]:
                            if "inlineData" in part:
                                return part["inlineData"]["data"], None
                    return None, "No image generated"
                else:
                    error_text = await response.text()
                    return None, f"API Error: {response.status}"
    except Exception as e:
        logger.error(f"Gemini Error: {str(e)}")
        return None, str(e)

# ===== BOT COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎨 *TextToImage Bot*\n\n"
        "Send me any text description and I'll generate an image!\n\n"
        "📝 *Example:* 'A beautiful sunset over mountains'\n\n"
        "🔧 *Commands:*\n"
        "/start - Show this message\n"
        "/model - Change AI model\n"
        "/status - Check bot status",
        parse_mode="Markdown"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = (
        "📊 *Bot Status*\n\n"
        f"✅ *Status:* Online\n"
        f"🔐 *APIs:*\n"
        f"• Gemini: {'✅' if GEMINI_API_KEY else '❌'}\n"
        f"• OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}\n\n"
        f"🤖 *Username:* @TextToImageeBot"
    )
    await update.message.reply_text(status, parse_mode="Markdown")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ OpenRouter Flux", callback_data="model_openrouter")],
        [InlineKeyboardButton("🧠 Google Gemini", callback_data="model_gemini")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🤖 *Select AI Model*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "model_openrouter":
        context.user_data["model"] = "openrouter"
        await query.edit_message_text("✅ Model changed to: **OpenRouter Flux**\n\nSend me a prompt to generate an image!", parse_mode="Markdown")
    elif query.data == "model_gemini":
        context.user_data["model"] = "gemini"
        await query.edit_message_text("✅ Model changed to: **Google Gemini**\n\nSend me a prompt to generate an image!", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text.strip()
    
    if not prompt:
        await update.message.reply_text("❌ Please send a valid prompt!")
        return
    
    # Get selected model (default: openrouter)
    user_model = context.user_data.get("model", "openrouter")
    
    # Send processing message
    processing = await update.message.reply_text(
        f"🎨 Generating image...\n📝 Prompt: {prompt[:50]}...\n⏳ Please wait..."
    )
    
    try:
        # Try to generate image
        image_data = None
        error = None
        
        if user_model == "openrouter" and OPENROUTER_API_KEY:
            image_data, error = await generate_with_openrouter(prompt)
            if not image_data and GEMINI_API_KEY:
                logger.info("OpenRouter failed, trying Gemini...")
                image_data, error = await generate_with_gemini(prompt)
                if image_data:
                    user_model = "gemini (fallback)"
        elif user_model == "gemini" and GEMINI_API_KEY:
            image_data, error = await generate_with_gemini(prompt)
            if not image_data and OPENROUTER_API_KEY:
                logger.info("Gemini failed, trying OpenRouter...")
                image_data, error = await generate_with_openrouter(prompt)
                if image_data:
                    user_model = "openrouter (fallback)"
        else:
            # Auto-detect available API
            if OPENROUTER_API_KEY:
                image_data, error = await generate_with_openrouter(prompt)
            elif GEMINI_API_KEY:
                image_data, error = await generate_with_gemini(prompt)
            else:
                await processing.delete()
                await update.message.reply_text(
                    "❌ No AI API configured!\n\n"
                    "Please add:\n"
                    "• OPENROUTER_API_KEY\n"
                    "• or GEMINI_API_KEY"
                )
                return
        
        await processing.delete()
        
        if image_data:
            # Send the image
            if image_data.startswith("http"):
                # URL from OpenRouter
                await update.message.reply_photo(
                    image_data,
                    caption=f"🖼️ *Image Generated*\n📝 *Prompt:* {prompt[:100]}\n🤖 *Model:* {user_model.upper()}",
                    parse_mode="Markdown"
                )
            else:
                # Base64 from Gemini
                image_bytes = base64.b64decode(image_data)
                await update.message.reply_photo(
                    image_bytes,
                    caption=f"🖼️ *Image Generated*\n📝 *Prompt:* {prompt[:100]}\n🤖 *Model:* {user_model.upper()}",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                f"❌ *Failed to generate image*\n\n"
                f"📝 *Prompt:* {prompt}\n"
                f"⚠️ *Error:* {error}\n\n"
                f"💡 Try a different prompt or model with /model",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        await processing.delete()
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ===== MAIN =====
def main():
    logger.info("🚀 Starting TextToImage Bot...")
    
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ Bot is ready! Starting polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
