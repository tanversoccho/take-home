import google.generativeai as genai
from config import config

def test_models():
    """Test multiple models to find one with available quota."""
    genai.configure(api_key=config.GEMINI_API_KEY)

    models_to_test = [
            "gemini-2.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-flash-lite-latest",
            "gemini-pro-latest"
            ]

    print("Testing models for available quota...")
    print("=" * 50)

    for model_name in models_to_test:
        try:
            print(f"\nTesting: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Say OK")
            if response and response.text:
                print(f"✅ {model_name} is working!")
                print(f"   Update .env with: GEMINI_MODEL={model_name}")
                return model_name
        except Exception as e:
            if "429" in str(e):
                print(f"❌ {model_name} - Quota exceeded")
            else:
                print(f"❌ {model_name} - {str(e)[:50]}...")

    print("\n❌ No models with available quota found.")
    print("   You need to wait for quota reset (midnight PT)")
    return None

if __name__ == "__main__":
    test_models()
