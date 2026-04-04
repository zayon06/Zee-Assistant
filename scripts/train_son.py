import os
from openwakeword.custom_model_generator import generate_models

output_dir = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(output_dir, exist_ok=True)

print("Training custom wake word models for 'Son'...")
generate_models(
    target_words=["son", "hey son"],
    output_path=output_dir,
)
print("Finished generating custom wake words.")
