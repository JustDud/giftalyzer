texts = {
    "start_command": "Launch the Bot",
    "about_command": "Information about the bot and its features",
    "language_command": "Change the interface language",
    "support_command": "Contact support",
    "start": (
        "Hi! I'm Giftalyser.\n"
        "I'll help you quickly and accurately determine the value of Telegram gifts in TON and USD.\n\n"
        "What I can do:\n"
        "• Show current market prices\n"
        "• Analyze gift value based on key parameters\n"
        "• Support collections like Plush Pepes, Bunny Muffins, Loot Bags, and more\n"
        "• Allow manual and filtered searches\n\n"
        "👇 Choose how you'd like to proceed:"
    ),

    "id_input_prompt": "Send the gift ID (e.g., MadPumpkin-1218)",
    "gift_result": (
        "🎁 Gift: {name}\n"
        "💎 Model: {model}\n"
        "🔮 Symbol: {symbol}\n"
        "🌌 Backdrop: {backdrop}\n\n"
        "💰 Estimated Value:\n{ton} TON\n≈ ${usd_estimated}\n\n"
        "📊 Price on {market}: \n{market_price} TON\n≈ ${usd_market}"
    ),
    "btn_check_another": "🔁 Check another",
    "btn_back": "🔙 Back",
    "btn_enter_id": "🔎 Enter gift ID",
    "btn_enter_manual": "✍️ Market search (type, backdrop..)",
    "btn_ask_ai": "🤖 Ask AI",
    "btn_help": "🆘 Help",
    "btn_subscription": "🌟 Subscription",
    "btn_check_subscription": "🔄 Check subscription",
    "btn_refund": "💸 Refund",
    "btn_active_tickets": "📬 Active tickets",
    "btn_close_all_tickets": "✅ Close all tickets",
    "btn_subscription_stats": "📊 Subscription stats",
    "nft_not_found": "❌ Gift not found in the database. Try another ID.",
    "returned_to_menu": "You've returned to the main menu. Choose an action 👇",
    "keyboard_restored": "Functionality restored",
    "loading_phrases": [
        "📦 Reviewing gifts... comparing parameters",
        "🧩 Analyzing rarity and value...",
        "✨ Gathering gifts with top traits...",
        "🔍 Finding patterns across collections...",
        "🌀 Processing data… almost non-stop",
        "⚙️ Modeling price ranges...",
    ],
    "locking_message": "🔒 Locking functionality while processing...",
    "collection_not_found": "Collection not found.",
    "no_results_found": "❌ No results found for the selected parameters.",
    "processing_done": "✅ Processing complete: 100%",
    "select_one_model": "Select at least one model.",
    "no_backdrops_available": "No backdrops available for the selected models.",
    "select_model_and_backdrop": "Select at least one model and one backdrop.",
    "select_one_backdrop": "Select at least one backdrop.",
    "prompt_select_collection": "Select a collection:",
    "prompt_select_model": "Select a model from collection {collection_name}",
    "prompt_select_backdrop": "Select a backdrop from collection {collection_name}",
    "btn_next_page": "➡️ Next page",
    "btn_prev_page": "⬅️ Previous page",
    "please_wait": "⏳ Please wait... Don’t close this window.",

    "btn_select_all_models": "✅ Select all",
    "btn_proceed_to_backdrops": "➡️ Choose backdrop",
    "btn_back_to_collections": "🔙 Back",
    "btn_select_all_backdrops": "✅ Select all",
    "btn_show_filtered_results": "🔎 Show results",
    "btn_back_to_models": "🔙 Back to models",
    "btn_back_to_main": "🔙 Back",

    "prompt_support_message": "✍️ Please describe your issue in as much detail as possible:",
    "support_received": "✅ Your message has been sent to support. We’ll contact you soon.",
    "support_thank_you": "Thank you for reaching out!",

    "ticket_not_found": "❌ Ticket not found.",
    "reply_sent": "✅ Reply sent.",
    "reply_failed": "❌ Failed to send reply:",
    "prompt_reply_message": "✍️ Enter your response to the ticket:",
    "support_reply": "💬 Support response",
    "clarify": "✏️ Clarify",

    "write_and_submit": "✍️ Write your message, then press \"📨 Send\".",
    "no_admin_access": "❌ You don’t have access to this command.",
    "tickets_closed": "✅ {count} tickets closed.",
    "no_active_tickets": "📭 No active tickets.",

    "clarify_button": "📝 Clarify",

    "admin_panel_activated": "🛠 Admin panel activated.\nChoose an action below:",
    "enter_user_id_refund": "Enter <b>User ID</b> for refund:",
    "enter_user_id_sub_check": "🔍 Enter <b>User ID</b> to check subscription:",
    "enter_transaction_id": "Now enter <b>Transaction ID</b>:",
    "subscription_stats": (
        "📊 <b>Subscription Stats</b>:\n"
        "👥 Total: <b>{total}</b>\n"
        "✅ Active: <b>{active}</b>"
    ),

    "gift_extraction_failed": "❌ Failed to extract gift parameters. The link may be invalid or the page structure has changed.",
    "no_similar_gifts": "⚠️ No similar gifts found. Your gift may be unique or not yet in the database. Try another ID.",
    "exact_match_found": "✅ Found gifts with exact match (model, symbol, backdrop):",
    "partial_match_found": "⚠️ Found similar gifts without a symbol match:",
    "model_only_match_found": "🔍 Found gifts matching only by model:",
    "no_gift_found_final": "😔 Unfortunately, no similar gifts were found.",

    "btn_confirm": "📨 Confirm",

    "subscription_activated": "✅ Congratulations! Your subscription is now active!\n Transaction ID:\n{charge_id}",
    "btn_language_ru": "Russian",
    "btn_language_en": "English",
    "language_switched": "✅ Interface language switched.",
    "support_write_message": "✍️ Please describe your issue in as much detail as possible:",
    "no_active_subscription": "❌ You don't have an active subscription. Please purchase one to use this feature.",
    "active_subscription_until": "✅ You already have an active subscription until {date}",
    "support_confirm_prompt": "📨 Press 'Confirm' to send the message to support, or enter a new one.",
    "support_thread_history": "🧵 Previous conversation:",
    "support_send_error": "❌ Failed to send message to support. Please try again later.",
    "choose_language": "🌐 Choose interface language:",
    "subscription_refunded": "✅ Subscription for user ID {user_id} successfully refunded.",
    "refund_error": "❌ Refund error: {error}",

    "giftalyserpro_full": (
    "✨ <b>GIFTALYSER PRO — your smart assistant</b>\n\n"
    "📅 <b>30-day subscription</b>\n"
    "Access to advanced analytics and support.\n\n"
    "🔹 <b>Price analysis</b>\n"
    "Accurate gift valuation based on 30+ factors: rarity, sales history, collection popularity, and more.\n\n"
    "🤖 <b>AI forecast</b>\n"
    "Find out whether the price is going up or likely to drop soon.\n\n"
    "📊 <b>Similar models</b>\n"
    "Compare similar gifts to find the best price/quality option.\n\n"
    "⚡ <b>Priority support</b>\n"
    "Your requests are handled first."
    ),
    "giftalyserpro_invoice_description": "Pay for your subscription using the button below",
    "btn_refund_policy": "🔁 Refund Policy",
    "refund_policy_notice": "The refund policy is available via the button below.",
    "refund_policy_text": (
        "🔁 Refund Policy\n\n"
        "Thank you for using our service. We aim to ensure transparency and fair conditions. "
        "Refunds are only possible in case of technical failures on the platform side that prevent delivery of the paid service.\n\n"
        "✅ Refund conditions\n"
        "Refunds are issued if:\n"
        "• The service failed to start or ended with an error caused by us.\n"
        "• The result was not provided due to a technical issue.\n"
        "• Access to the service was not granted after confirmed payment.\n\n"
        "📌 Refund requests must be submitted within 24 hours of payment.\n\n"
        "🧾 Required:\n"
        "• Transaction ID\n"
        "• Screenshots showing the issue (preferably with a date)\n"
        "• A brief description of the problem\n\n"
        "Each request is reviewed individually.\n\n"
        "🕒 Review timeframe\n"
        "A refund decision is made within 21 calendar days from submission of a valid request. You’ll receive a response via Telegram.\n\n"
        "❌ Refunds are NOT issued if:\n"
        "• The service was delivered as described, but the result did not meet expectations\n"
        "• An incorrect service was selected\n"
        "• You changed your mind after payment\n"
        "• The error was caused by the user (unstable internet, device issues, etc.). We may request technical logs if needed.\n\n"
        "📬 How to request a refund:\n"
        "1. Go to the “Help” section on the platform or in the bot\n"
        "2. Click “Support”\n"
        "3. Choose “Refund Request” as the topic, add your order ID and a description\n"
        "4. Attach evidence (e.g., a screenshot of the error)\n"
        "5. Submit your request\n\n"
        "⏱ We will reply within 48 hours."
    ),
    "support_confirm_error": "❌ No message to confirm. Please describe your issue before sending.",
    "refund_log": "🔁 Refund issued for user ID {user_id}, transaction: {charge_id}",
    "new_payment_log": "✅ New subscription issued! User ID: {user_id}, transaction: {charge_id}",

    "btn_manage_promocodes": "🎁 Promo Code Management",
    "btn_add_promocode": "➕ Add Promo Code",
    "btn_delete_promocode": "🗑 Delete Promo Code",
    "btn_list_promocodes": "📋 All Promo Codes",
    "btn_promocode_stats": "📊 Promo Code Stats",
    "btn_top_promocodes": "🏆 Top Promo Codes",
    "enter_promocode_for_stats": "Enter a promo code to view its stats:",
    "promocode_not_found": "❌ Promo code {code} not found",
    "promocode_stats": "📊 Promo code <b>{code}</b>\nUsed: {usage} times\nTotal revenue: {total_profit}\nActive: {active}",
    "enter_promocode_code": "Enter the promo code name:",
    "enter_promocode_owner": "Enter the promo code owner's ID:",
    "enter_promocode_discount": "Enter the discount percentage for users:",
    "enter_promocode_profit": "Enter the profit percentage for the owner:",
    "enter_promocode_single_use": "Enter 0 for multi-use, 1 for one-time use:",
    "promocode_created": "✅ Promo code <b>{code}</b> successfully created",
    "enter_promocode_for_delete": "Enter the promo code to disable:",
    "promocode_disabled": "✅ Promo code {code} has been disabled",
    "no_promocodes_found": "❌ No promo codes found",
    "promocodes_list_header": "📋 List of all promo codes:",
    "operation_error": "❌ An error occurred. Please try again.",
    "owner": "Owner:",
    "discount": "Discount:",
    "profit": "Profit:",
    "btn_back_admin": "🔙 Back",

    "ask_promo_code": "Do you have a promo code? Send it now or tap Skip:",
    "btn_skip_promo": "⏭ Skip",
    "promo_applied": "✅ Promo code applied! Discounted price: {discounted_price}⭐",
    "promo_try_again_or_skip": "Try another promo code or press Skip.",
    "my_promocodes_header": "📋 Your promo codes:",
    "no_my_promocodes": "❌ You haven’t created any promo codes.",

    "db_update_started": "Database update started",
    "db_update_finished": "Database update completed",

    "ai_analyse_gift": "🔎 Analyse gift",
    "ai_undervalued": "📈 Show undervalued",
    "ai_only_up": "⬆ Only with 'up' forecast",
    "ai_analyse_collection": "🧪 Analyse without upgrades",
    "ai_analyse_collection_description": "",
    "ai_prompt_select_model": "Select a model to analyse: {collection_name}",
    "ai_prompt_select_backdrop": "Select a backdrop for collection {collection_name}:",
    "ai_btn_show_results": "Show AI analysis results",
    "ai_prompt_select_collection": "Select a collection:",
    "ai_collection_not_found": "Collection not found in AI mode.",
    "ai_select_backdrop": "Select a backdrop",

    "btn_link_analysis": "🔗 Paste link",
    "btn_manual_analysis": "📦 Manual selection",
    "choose_analysis_method": "How would you like to analyse the gift?",

    "ai_prompt_enter_supply": "📦 Enter supply:",
    "ai_prompt_enter_price": "💰 Now enter the price in stars:",
    "ai_error_invalid_supply": "❌ Enter a valid integer supply value.",
    "ai_error_invalid_price": "❌ Enter a valid integer price.",
    "ai_analysis_collection_result_template": (
        "📊 Analysis result:\n\n"
        "• Supply: {supply} 📦\n"
        "• Price: {price} ⭐\n"
        "• Verdict: {verdict}\n"
        "• Justification: {explanation}\n\n"
        "📌 {policy}"
    ),
    "ai_collection_analysis_intro": "✨ Let's check how good your gift deal is.\n\n📦 Send the supply value for the collection.",
    "promo_error_not_found_or_inactive": "Promo code doesn't exist or is inactive.",
    "promo_error_already_used": "You’ve already used this promo code.",
    "promo_error_unknown": "An unknown error occurred with the promo code.",
}