from flask import Flask, request, jsonify
from nano_llm import NanoLLM, ChatHistory
from PIL import Image
import base64
import io

app = Flask(__name__)

print("Loading VILA model...")
model = NanoLLM.from_pretrained(
    "Efficient-Large-Model/VILA1.5-3b",
    api='mlc',
    quantization='q4f16_ft'
)
chat_history = ChatHistory(model)
print("VILA ready on port 5000")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "model": "VILA1.5-3b"})

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json

    if not data:
        return jsonify({"error": "No data received"}), 400

    prompt = data.get('prompt', '')
    system = data.get('system', '')
    image_b64 = data.get('image')

    chat_history.reset()

    if system:
        chat_history.append(role='system', text=system)

    if image_b64:
        try:
            image_data = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_data)).convert('RGB')
            chat_history.append(role='user', image=image)
            print(f"Image received: {image.size}")
        except Exception as e:
            print(f"Image decode error: {e}")
            return jsonify({"error": f"Image error: {e}"}), 400

    chat_history.append(role='user', text=prompt)

    try:
        response = ''
        for token in model.generate(
            chat_history.embed_chat(),
            max_new_tokens=256,
            streaming=True
        ):
            response += token

        print(f"Response: {response.strip()}")
        return jsonify({"response": response.strip()})

    except Exception as e:
        print(f"Generation error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting VILA server...")
    app.run(host='0.0.0.0', port=5000, debug=False)