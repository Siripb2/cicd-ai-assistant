from dotenv import load_dotenv
import os
load_dotenv()

key = os.getenv('GEMINI_API_KEY', '')
model = os.getenv('GEMINI_MODEL', 'NOT SET')
api_key = os.getenv('API_KEY', '')

print('KEY loaded:', bool(key), '| starts with:', key[:10] if key else 'EMPTY')
print('MODEL:', model)
print('API_KEY blank:', api_key == '')

if not key:
    print('PROBLEM: GEMINI_API_KEY is empty')
else:
    import google.generativeai as genai
    genai.configure(api_key=key)
    try:
        m = genai.GenerativeModel(model)
        r = m.generate_content('say hello in one word')
        print('SUCCESS:', r.text)
    except Exception as e:
        print('ERROR:', str(e)[:300])
