import pytest
from server.brain import ZeeBrain

def test_trim_memory():
    brain = ZeeBrain()
    brain.max_history = 5
    
    # Fill memory
    for i in range(10):
         brain.memory.append({"role": "user", "content": f"Message {i}"})
         
    brain.trim_memory()
    
    assert len(brain.memory) == 5
    # The first message is ALWAYS the system prompt, which should be preserved
    assert brain.memory[0]["role"] == "system"
    # The last messages should be the most recent ones (Message 6, 7, 8, 9)
    assert brain.memory[-1]["content"] == "Message 9"
    assert brain.memory[1]["content"] == "Message 6"
