import google.generativeai as genai
from config import config
from logger import default_logger

logger = default_logger

# List of known working models from the API response
WORKING_MODELS = [
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.7-flash"
        ]

def test_gemini_models():
    """Test available Gemini models."""
    print("\n🔍 Testing Gemini API connection...")

    if not config.GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY is not set in .env file")
        print("   Please add: GEMINI_API_KEY=your-api-key-here")
        return False

    # Configure
    genai.configure(api_key=config.GEMINI_API_KEY)

    # List available models
    print("\n📋 Available models:")
    available_models = []
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            model_name = model.name.replace('models/', '')
            print(f"  ✓ {model_name}")
            available_models.append(model_name)

    if not available_models:
        print("❌ No working models found. Check your API key.")
        return False

    # Try the configured model
    configured_model = config.GEMINI_MODEL
    print(f"\n🔧 Testing configured model: {configured_model}")

    try:
        model = genai.GenerativeModel(configured_model)
        response = model.generate_content(
                "Say 'Hello, invoice processing system!' in one sentence.",
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=50
                    )
                )
        print(f"✅ Response: {response.text}")
        print(f"✅ Model {configured_model} is working!")
        return True
    except Exception as e:
        print(f"❌ Error with model {configured_model}: {e}")

        # Try fallback models
        print(f"\n🔧 Trying fallback models...")
        found_working = False

        for model_name in WORKING_MODELS:
            if model_name != configured_model and model_name in available_models:
                try:
                    print(f"  Testing {model_name}...")
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content("Say 'OK'.")
                    if response and response.text:
                        print(f"  ✅ {model_name} is working!")
                        print(f"\n💡 Update your .env file with:")
                        print(f"   GEMINI_MODEL={model_name}")
                        found_working = True
                        break
                except Exception as e2:
                    print(f"  ❌ {model_name} failed: {e2}")

        if not found_working:
            print("\n❌ No working models found. Please check:")
            print("   1. Your GEMINI_API_KEY is correct")
            print("   2. You have internet access")
            print("   3. Your API key has access to Gemini models")
            return False

if __name__ == "__main__":
    test_gemini_models()
