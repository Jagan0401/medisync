# MediSync WhatsApp Language Preference - Fix Documentation

## 🎯 Problem Statement

When patients reply with language preference options (1, 2, etc.) via WhatsApp, there was **NO REPLY** on follow-up messages because the language preference was stored in RAM only and lost on server restart.

### Root Cause
- **File**: `backend/apps/outreach/views.py`
- **Issue**: Used in-memory dictionary `_user_language = {}` 
- **Impact**: 
  - Lost on server restart
  - Failed in multi-instance deployments
  - No database persistence

---

## ✅ Solution Implemented

### Phase 1: Basic Fix (IMPLEMENTED)
**File**: `backend/apps/outreach/views.py` - COMPLETELY REWRITTEN

#### Changes:
1. ❌ Removed: In-memory `_user_language = {}` dictionary
2. ✅ Added: Database persistence of language preferences to `patients.preferred_language`
3. ✅ Added: State machine tracking `patients.whatsapp_state` (awaiting_language → active)
4. ✅ Added: Proper error handling and logging
5. ✅ Added: Support for multi-language (English, Tamil, expandable)

#### Data Model Changes:
```python
# MongoDB patients collection now stores:
{
    "_id": ObjectId(...),
    "patient_id": "P12345",
    "name": "John Doe",
    "phone": "9876543210",
    "preferred_language": "ta",  # NEW: ISO 639-1 code (en, ta, hi, te, kn, ml, etc.)
    "whatsapp_state": "active",  # NEW: awaiting_language OR active
    "disease": "Diabetes",
    "last_test": "HbA1c",
    "last_result": "7.5%",
    # ... other fields
}
```

#### State Flow:
```
Patient receives message
         ↓
whatsapp_state="awaiting_language"? 
         YES → Ask "Choose language: 1=English, 2=தமிழ்"
         NO → Check if "1" or "2" received
              YES → Save language, move to "active", send health details
              NO → Process as normal conversation
```

---

### Phase 2: LangChain Integration (OPTIONAL ENHANCEMENT)

**File**: `backend/integrations/langchain_service.py` - NEW

#### Features:
- ✅ Persistent conversation memory (MongoDB-backed)
- ✅ Context-aware responses
- ✅ Multi-language support
- ✅ Intent detection with confidence scores
- ✅ Session management

#### Classes:
```python
class PatientConversationMemory:
    """Stores conversation history in MongoDB"""
    - add_message(role, content, language)
    - get_context(limit=10)
    - clear_conversation()

class WhatsAppConversationManager:
    """Manages conversation flow with LangChain patterns"""
    - analyze_patient_intent_with_context()
    - generate_contextual_response()
    - log_exchange()

class MultiLanguageProcessor:
    """Advanced language handling"""
    - detect_language(text) → ISO code
    - get_language_name(code) → "Tamil", "Hindi", etc.
```

#### New MongoDB Collection:
```python
db.whatsapp_conversations.insert_one({
    "patient_id": "P12345",
    "messages": [
        {
            "role": "patient",  # or "assistant"
            "content": "வணக்கம்",
            "language": "ta",
            "timestamp": "2026-03-10T12:34:56"
        },
        {
            "role": "assistant",
            "content": "வணக்கம் மரியா 👋",
            "language": "ta",
            "timestamp": "2026-03-10T12:35:00"
        }
    ],
    "updated_at": "2026-03-10T12:35:00"
})
```

---

### Phase 3: Enhanced Webhook (OPTIONAL)

**File**: `backend/apps/outreach/views_enhanced.py` - NEW

This is an alternative to the basic webhook that uses LangChain for:
- Context-aware responses
- Persistent conversation memory
- More sophisticated intent detection

#### To Enable Enhanced Version:
```python
# In backend/apps/outreach/urls.py
from . import views_enhanced

urlpatterns = [
    path('webhook/whatsapp/', views_enhanced.whatsapp_webhook_enhanced, name='whatsapp_webhook'),
]
```

---

## 🚀 Installation & Setup

### Step 1: Update Requirements
✅ **Already done** - Added LangChain to `requirements.txt`:
```bash
langchain>=0.1.0
langchain-community>=0.0.10
```

### Step 2: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
# or just install new packages:
pip install langchain langchain-community
```

### Step 3: Database Migration (Optional)

Add indexes for better performance:
```python
# Run once in Django shell or create a migration
from config.db import db

# Create indexes
db.whatsapp_conversations.create_index([("patient_id", 1)])
db.whatsapp_conversations.create_index([("updated_at", -1)])

# Optional: Set TTL to auto-delete old conversations after 90 days
db.whatsapp_conversations.create_index([("created_at", 1)], expireAfterSeconds=7776000)
```

### Step 4: Environment Variables (Optional)
No new environment variables needed! But ensure existing variables are set:
```
GROQ_API_KEYS=xxxx  # For AI responses
TWILIO_ACCOUNT_SID=xxxx
TWILIO_AUTH_TOKEN=xxxx
```

---

## 📝 Usage Examples

### Basic Webhook Flow (Recommended for immediate use)
```python
# Client sends: "1"
# Webhook executes:
# 1. Finds patient
# 2. Registers: preferred_language="en", whatsapp_state="active"
# 3. Replies with health message

# Client sends: "Hello, can I book?"
# Webhook uses stored language preference from DB
# Replies in their chosen language (no memory loss)
```

### Enhanced Webhook Flow (With LangChain)
```python
from integrations.langchain_service import create_conversation_manager

# In webhook:
conv_mgr = create_conversation_manager(
    patient_id="P123",
    patient_name="Maria",
    disease="Diabetes"
)

# Analyze with context
intent = conv_mgr.analyze_patient_intent_with_context(
    "Can I get an appointment tomorrow?",
    preferred_language="ta"
)
# Returns: {
#     "intent": "book_appointment",
#     "confidence": 0.95,
#     "requires_booking": true,
#     "sentiment": "positive"
# }

# Generate response with context awareness
response = conv_mgr.generate_contextual_response(
    "What about my test results?",
    patient_info=patient,
    preferred_language="ta"
)

# Log the exchange
conv_mgr.log_exchange(
    patient_message="What about my test results?",
    assistant_response="Your last HbA1c was 7.5%...",
    language="ta"
)
```

### Supported Languages
```python
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'ta': 'Tamil',
    'hi': 'Hindi',
    'te': 'Telugu',
    'kn': 'Kannada',
    'ml': 'Malayalam',
    'bn': 'Bengali',
    'mr': 'Marathi',
    'gu': 'Gujarati',
    'pa': 'Punjabi',
    'ur': 'Urdu',
}

# To add more languages:
# 1. Update LANGUAGE_MENU in webhook
# 2. Add translations for fixed messages
# 3. Update SUPPORTED_LANGUAGES in langchain_service.py
```

---

## 🧪 Testing

### Manual Testing via WhatsApp
```
1. Patient sends WhatsApp message
2. Bot prompts: "Choose language: 1=English 2=தமிழ்"
3. Patient sends: "1"
4. Bot replies: "✅ Language set to English..." + health message
5. Patient sends: Any follow-up message
6. ✅ Bot replies in English (language preference PERSISTED)
7. Restart server
8. Patient sends another message
9. ✅ Bot STILL replies in English (database persistence works!)
```

### Testing Database Persistence
```bash
# In MongoDB
use medisync_db
db.patients.findOne(
    {"name": "Maria"},
    {"preferred_language": 1, "whatsapp_state": 1}
)

# Should show:
# {
#     "_id": ObjectId(...),
#     "preferred_language": "ta",
#     "whatsapp_state": "active"
# }
```

### Testing Conversation Memory (LangChain)
```bash
# In MongoDB
use medisync_db
db.whatsapp_conversations.findOne(
    {"patient_id": "P123"}
)

# Should show conversation history with timestamps
```

---

## 🔄 Migration from Old to New System

### For Existing Patients

**Option 1: Automatic On-First-Message** (Recommended)
- Existing patients with no `whatsapp_state` will be prompted for language
- Their choice gets saved to `preferred_language`
- Process continues normally

**Option 2: Batch Script** (For clean migration)
```python
# Create migration script
# backend/scripts/migrate_languages.py

from config.db import db

# Set all patients to awaiting_language
db.patients.update_many(
    {"whatsapp_state": {"$exists": False}},
    {
        "$set": {
            "whatsapp_state": "awaiting_language",
            "preferred_language": "en"  # Default
        }
    }
)

# Run: python manage.py shell < scripts/migrate_languages.py
```

---

## 📊 Comparison: Before vs After

| Feature | Before | After (Basic) | After (LangChain) |
|---------|--------|---------------|------------------|
| Language storage | RAM (Lost) | ✅ Database | ✅ Database |
| Persistence | ❌ No | ✅ Yes | ✅ Yes |
| Multi-instance ready | ❌ No | ✅ Yes | ✅ Yes |
| Conversation memory | ❌ No | ❌ Limited | ✅ Full |
| Context-aware responses | ❌ No | ❌ No | ✅ Yes |
| Intent confidence | ❌ No | ❌ No | ✅ Yes |
| Language support | 2 (hardcoded) | 2-6 (configurable) | All 11 languages |
| Server restarts | ❌ Breaks | ✅ Works | ✅ Works |

---

## 🎓 Architecture Decisions

### Why Database Persistence Over Redis?
- ✅ Data survives indefinitely (not temporary)
- ✅ Already using MongoDB for patients
- ✅ No additional infrastructure needed
- ❌ Slightly slower than Redis (negligible for WhatsApp)

### Why LangChain Optional?
- ✅ Basic fix works immediately without new deps
- ✅ LangChain adds complexity (can opt-in later)
- ✅ Gradual migration approach
- ✅ Backwards compatible

### Why State Machine?
- ✅ Prevent confusion of flow states
- ✅ Clear state transitions
- ✅ Easier to debug
- ✅ Scalable to add more states (e.g., "appointment_scheduled")

---

## 🐛 Troubleshooting

### Issue: Language not persisting after server restart
**Solution**: Ensure MongoDB is persistent (not in-memory testing DB)

### Issue: Patient seeing old language on new device
**Solution**: This is by design - phone number is primary key. If patient has two devices, they share language.

### Issue: LangChain service raising ImportError
**Solution**: 
```bash
pip install langchain langchain-community
# If issues persist:
pip install --upgrade langchain
```

### Issue: Conversation memory not growing
**Solution**: Check MongoDB `whatsapp_conversations` collection:
```bash
db.whatsapp_conversations.stats()
db.whatsapp_conversations.find({"patient_id": "P123"}).pretty()
```

---

## 📚 Next Steps (Future Enhancements)

1. **Add more languages** - Easy: update LANGUAGE_MENU + translations
2. **Implement conversation search** - Patients can ask "What were my last results?"
3. **Add appointment reminders** - Use conversation history for better context
4. **Feedback loop** - Rate bot responses, improve AI prompts
5. **Analytics** - Track most common intents, language preferences distribution
6. **Escalation** - If confidence < 0.5 or "human_assistance" intent detected

---

## 📞 Support

**Files Modified**:
- ✅ `backend/apps/outreach/views.py` - Main webhook (FIXED)
- ✅ `backend/requirements.txt` - Added LangChain deps
- ✅ `backend/integrations/langchain_service.py` - NEW service (Optional)
- ✅ `backend/apps/outreach/views_enhanced.py` - Enhanced webhook (Optional)

**No Breaking Changes** - Existing code continues to work!

---

**Date**: March 10, 2026  
**Status**: ✅ Production Ready (Basic Phase)  
**Optional**: LangChain Enhancement Available
