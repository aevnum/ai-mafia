# api_handler.py
"""Handles API calls to Gemini or Grok"""

import os
import time
import re
from typing import Optional
from config import API_PROVIDER, GEMINI_CONFIG, GROK_CONFIG

# Import API libraries
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class APIHandler:
    """Handles API communication with Gemini or Grok"""
    
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or API_PROVIDER
        self.config = GEMINI_CONFIG if self.provider == "gemini" else GROK_CONFIG
        
        # Get API key from config or environment
        self.api_key = self.config['api_key'] or os.getenv(
            'GOOGLE_API_KEY' if self.provider == 'gemini' else 'GROK_API_KEY'
        )
        
        if not self.api_key:
            raise ValueError(f"API key not found for {self.provider}. Set it in config.py or environment.")
        
        # Initialize API clients
        if self.provider == "gemini":
            if genai is None:
                raise ImportError("google-generativeai library not installed. Run: pip install google-generativeai")
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.config['model'])
        elif self.provider == "grok":
            if OpenAI is None:
                raise ImportError("openai library not installed. Run: pip install openai")
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.x.ai/v1"
            )
    
    def generate_response(self, prompt: str) -> Optional[str]:
        """
        Generates a response using the configured API provider.
        Returns the generated text or None if error occurs.
        """
        try:
            if self.provider == "gemini":
                return self._call_gemini(prompt)
            elif self.provider == "grok":
                return self._call_grok(prompt)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")
        except Exception as e:
            print(f"Error generating response: {e}")
            return None
    
    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Call Gemini API with retry logic for rate limits"""
        max_retries = 3
        base_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": self.config['temperature'],
                        "max_output_tokens": self.config['max_tokens']
                    }
                )
                return response.text.strip()
            
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a rate limit error (429)
                if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                    if attempt < max_retries - 1:
                        # Extract retry delay from error message if available
                        retry_match = re.search(r'retry in ([\d.]+)s', error_msg)
                        wait_time = float(retry_match.group(1)) if retry_match else base_delay * (2 ** attempt)
                        
                        print(f"Rate limit hit. Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Rate limit exceeded after {max_retries} retries. Skipping this turn.")
                        return None
                else:
                    # Other error, don't retry
                    print(f"Gemini API error: {e}")
                    return None
        
        return None
    
    def _call_grok(self, prompt: str) -> Optional[str]:
        """Call Grok API using OpenAI library"""
        response = self.client.chat.completions.create(
            model=self.config['model'],
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=self.config['temperature'],
            max_tokens=self.config['max_tokens']
        )
        return response.choices[0].message.content.strip()
    
    def test_connection(self) -> bool:
        """Test if API connection works"""
        try:
            response = self.generate_response("Say 'Hello' in one word.")
            return response is not None
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False