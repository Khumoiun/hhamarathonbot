import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.error import BadRequest
import sqlite3

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
conn = sqlite3.connect('users.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, username TEXT, invited_count INTEGER, 
              channels_followed INTEGER, referrer_id INTEGER)''')
conn.commit()

# Constants
REQUIRED_INVITES = 5
CHANNEL_LINK = "https://t.me/+GmCMsWCTsZYyMzhi"
CHANNELS_TO_FOLLOW = ["@english_avenue", "@humoyunsielts"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username

    # Check if user was referred
    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])

    # Register user in the database
    c.execute("INSERT OR IGNORE INTO users (user_id, username, invited_count, channels_followed, referrer_id) VALUES (?, ?, ?, ?, ?)", 
              (user_id, username, 0, 0, referrer_id))
    conn.commit()

    # Ask user to follow channels
    channels_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"Follow {channel}", url=f"https://t.me/{channel[1:]}")] for channel in CHANNELS_TO_FOLLOW
    ] + [[InlineKeyboardButton(text="I've followed all channels", callback_data="channels_followed")]])

    await update.message.reply_text(
        "Welcome! Please follow these channels to continue:",
        reply_markup=channels_markup
    )

async def channels_followed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Update user's status
    c.execute("UPDATE users SET channels_followed = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

    # Check if this user was referred and update referrer's count if necessary
    c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    referrer_id = c.fetchone()[0]
    if referrer_id:
        c.execute("UPDATE users SET invited_count = invited_count + 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        
        # Check if the referrer has reached the required invites
        c.execute("SELECT invited_count FROM users WHERE user_id = ?", (referrer_id,))
        invited_count = c.fetchone()[0]
        if invited_count >= REQUIRED_INVITES:
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"Congratulations! You have invited {REQUIRED_INVITES} friends. "
                         f"You can now join the channel via this link: {CHANNEL_LINK}"
                )
            except Exception as e:
                logger.error(f"Failed to send channel link to user {referrer_id}: {e}")

    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id

    # Generate referral link
    referral_link = f"https://t.me/hhamarathonbot?start={user_id}"

    welcome_message = (
        f"Hello {query.from_user.first_name if query else update.effective_user.first_name}! "
        f"Congratulations on your first step towards a bright future!\n\n"
        f"Now, invite your friends to get your link to our private channel where we have lessons together.\n\n"
        f"Your referral link: {referral_link}"
    )

    keyboard = [
        [InlineKeyboardButton("Profile", callback_data='profile'),
         InlineKeyboardButton("Referral Link", callback_data='referral_link')],
        [InlineKeyboardButton("Invite Friends", switch_inline_query=("""
                                                                        🍬🎉🍬🎊🎉🎉🎉
                                                                     Congratulations on your first step towards a bright future!
        Now, invite your friends to get your link to our private channel where we have lessons together.
        
        """ + referral_link))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(welcome_message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest as e:
        if "Query is too old" in str(e):
            logger.warning("Received an expired callback query. Proceeding without answering.")
        else:
            raise

    if query.data == 'channels_followed':
        await channels_followed_callback(update, context)
    elif query.data == 'profile':
        await show_profile(update, context)
    elif query.data == 'referral_link':
        await show_referral_link(update, context)
    elif query.data == 'back_to_main':
        await show_main_menu(update, context)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    c.execute("SELECT invited_count, channels_followed FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        invited_count, channels_followed = result
        remaining = max(0, REQUIRED_INVITES - invited_count)

        if channels_followed:
            profile_message = (
                f"Name: {query.from_user.first_name}\n"
                f"Invited friends: {invited_count}\n"
            )
            
            if invited_count >= REQUIRED_INVITES:
                profile_message += f"\nCongratulations! You can join the channel via this link: {CHANNEL_LINK}"
            else:
                profile_message += f"\nFriends to invite for channel access: {remaining}"
        else:
            profile_message = "Please follow the required channels first."
        
        keyboard = [[InlineKeyboardButton("Back", callback_data='back_to_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(text=profile_message, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                raise
    else:
        await query.edit_message_text(text="User not found. Please start the bot again.")

async def show_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    c.execute("SELECT channels_followed FROM users WHERE user_id = ?", (user_id,))
    channels_followed = c.fetchone()[0]
    
    if channels_followed:
        referral_link = f"""Congratulations on your first step towards a bright future!
        Now, invite your friends to get your link to our private channel where we have lessons together.
        https://t.me/hhamarathonbot?start={user_id}"""
        keyboard = [
            [InlineKeyboardButton("Invite Friends", switch_inline_query=(referral_link + """Congratulations on your first step towards a bright future!
        Now, invite your friends to get your link to our private channel where we have lessons together."""))],
            [InlineKeyboardButton("Back", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_text(text=f"Your referral link: {referral_link}", reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                pass
            else:
                raise
    else:
        await query.edit_message_text(text="Please follow the required channels first to get your referral link.")

async def check_invites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT invited_count, channels_followed FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result:
        invited_count, channels_followed = result
        if channels_followed:
            if invited_count >= REQUIRED_INVITES:
                await update.message.reply_text(
                    f"You have successfully invited {REQUIRED_INVITES} friends. "
                    f"Now you can join the channel via this link: {CHANNEL_LINK}"
                )
            else:
                remaining = REQUIRED_INVITES - invited_count
                await update.message.reply_text(f"You need to invite {remaining} more friends to get access to the channel.")
        else:
            await update.message.reply_text("Please follow the required channels first.")
    else:
        await update.message.reply_text("User not found. Please start the bot again.")

def main():
    application = ApplicationBuilder().token('7096006109:AAH-FggO9x-v1rR-gt8uAe8KUJdhzkoZuLk').build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler("check", check_invites))

    application.run_polling()

if __name__ == '__main__':
    main()