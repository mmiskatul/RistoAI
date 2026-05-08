## AI Chat Improvements & Fixes
- **Chat History:** Removed the hardcoded 40-message display limit, ensuring the full conversation history is loaded.
- **Translation Pagination:** Limited translation hydration to only the latest 40 messages to prevent Vercel Serverless Function timeouts on full-history requests.
- **Voice Transcription:**
  - Removed auto-translation of voice transcripts to preserve exact user phrasing.
  - Passed the user's selected app language explicitly to the OpenAI Whisper API to prevent cross-language misinterpretations.
- **Error Handling:** Added explicit error messages for missing API keys or OpenAI API failures instead of returning a generic fallback financial summary.
- **Infrastructure:** Validated that Vercel auto-detect works correctly for the FastAPI backend and removed explicit ercel.json to prevent deployment conflicts.
