WELCOME_MESSAGE = "សូមស្វាគមន៍មកកាន់ប្រព័ន្ធប្រែសំឡេងជាអក្សរ"

PROCESSING_MESSAGE = "⌛ កំពុងចាប់ផ្តើមបង្កើត SRT..."

TRANSCRIPTION_HEADER = "📝 ការប្រែសម្លេង៖"
LANGUAGE_LABEL = "\U0001f310 \u1797\u17b6\u179f\u17b6\u17d6"
LANGUAGE_KHMER = "🇰🇭 ខ្មែរ (កម្ពុជា)"
LANGUAGE_ENGLISH = "🇬🇧 អង់គ្លេស (English)"

TRANSCRIPTION_DONE = "🎉 ការប្រែសម្លេងបានបញ្ចប់!"
SRT_FILE_LABEL = "📄 ឯកសារ:"
TIME_LABEL = "⏱️ ពេលវេលាប្រតិបត្តិការ:"
TIME_SECONDS = "វិនាទី"
USAGE_LABEL = "✨ បានប្រើ"
SRT_LANGUAGE_LABEL = "\U0001f310 \u1797\u17b6\u179f\u17b6:"
BOT_TECH = "🤖 ប្រើប្រាស់បច្ចេកវិទ្យា A.I"


def get_language_display(lang_code: str) -> str:
    if lang_code.startswith("km"):
        return LANGUAGE_KHMER
    if lang_code.startswith("en"):
        return LANGUAGE_ENGLISH
    return f"\U0001f310 {lang_code}"
