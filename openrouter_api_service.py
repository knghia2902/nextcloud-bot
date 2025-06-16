#!/usr/bin/env python3
"""
OpenRouter API Service - Tích hợp với OpenRouter APIs
"""
import requests
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

class OpenRouterAPIService:
    """Service để tương tác với OpenRouter APIs"""
    
    def __init__(self):
        self.base_url = "https://openrouter.ai/api"
        self.frontend_base = "https://openrouter.ai/api/frontend"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NextcloudBot/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Cache for API responses
        self._providers_cache = None
        self._models_cache = None
        self._cache_timestamp = None
        self._cache_duration = timedelta(hours=1)  # Cache for 1 hour
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if self._cache_timestamp is None:
            return False
        return datetime.now() - self._cache_timestamp < self._cache_duration
    
    def get_all_providers(self) -> Optional[List[Dict]]:
        """
        Get all providers from OpenRouter API
        URL: https://openrouter.ai/api/frontend/all-providers
        """
        try:
            if self._is_cache_valid() and self._providers_cache:
                logging.info("Using cached providers data")
                return self._providers_cache

            url = f"{self.frontend_base}/all-providers"
            logging.info(f"Fetching providers from: {url}")

            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                response_data = response.json()

                # OpenRouter API may return providers in 'data' field or directly as array
                if isinstance(response_data, dict) and 'data' in response_data:
                    providers_data = response_data['data']
                elif isinstance(response_data, list):
                    providers_data = response_data
                else:
                    logging.error(f"Unexpected providers response structure: {type(response_data)}")
                    return None

                # Cache the response
                self._providers_cache = providers_data
                self._cache_timestamp = datetime.now()

                logging.info(f"Successfully fetched {len(providers_data)} providers")
                return providers_data
            else:
                logging.error(f"Failed to fetch providers: HTTP {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching providers: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error for providers: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching providers: {e}")
            return None
    
    def get_all_models(self) -> Optional[List[Dict]]:
        """
        Get all models from OpenRouter API
        URL: https://openrouter.ai/api/frontend/models
        """
        try:
            if self._is_cache_valid() and self._models_cache:
                logging.info("Using cached models data")
                return self._models_cache

            url = f"{self.frontend_base}/models"
            logging.info(f"Fetching models from: {url}")

            response = self.session.get(url, timeout=15)

            if response.status_code == 200:
                response_data = response.json()

                # OpenRouter API returns models in 'data' field
                if isinstance(response_data, dict) and 'data' in response_data:
                    models_data = response_data['data']
                elif isinstance(response_data, list):
                    models_data = response_data
                else:
                    logging.error(f"Unexpected response structure: {type(response_data)}")
                    return None

                # Cache the response
                self._models_cache = models_data
                self._cache_timestamp = datetime.now()

                logging.info(f"Successfully fetched {len(models_data)} models")
                return models_data
            else:
                logging.error(f"Failed to fetch models: HTTP {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching models: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error for models: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching models: {e}")
            return None
    
    def get_models_by_provider(self, provider_name: str) -> List[Dict]:
        """Get models filtered by provider"""
        try:
            all_models = self.get_all_models()
            if not all_models:
                return []
            
            provider_models = []
            for model in all_models:
                # Check if model belongs to the provider
                model_id = model.get('id', '')
                if model_id.startswith(f"{provider_name}/"):
                    provider_models.append(model)
            
            logging.info(f"Found {len(provider_models)} models for provider {provider_name}")
            return provider_models
            
        except Exception as e:
            logging.error(f"Error filtering models by provider {provider_name}: {e}")
            return []
    
    def get_free_models(self) -> List[Dict]:
        """Get only free models"""
        try:
            all_models = self.get_all_models()
            if not all_models:
                return []
            
            free_models = []
            for model in all_models:
                # Check if model is free (pricing is 0 or has 'free' in the name)
                pricing = model.get('pricing', {})
                prompt_price = float(pricing.get('prompt', '0'))
                completion_price = float(pricing.get('completion', '0'))
                
                model_id = model.get('id', '')
                is_free = (prompt_price == 0 and completion_price == 0) or ':free' in model_id
                
                if is_free:
                    free_models.append(model)
            
            logging.info(f"Found {len(free_models)} free models")
            return free_models
            
        except Exception as e:
            logging.error(f"Error filtering free models: {e}")
            return []
    
    def format_model_for_select(self, model: Dict) -> Dict:
        """Format model data for HTML select options"""
        try:
            model_id = model.get('id', '')
            original_name = model.get('name', model_id)

            # Use original name without modifications
            display_name = original_name

            # Get pricing info
            pricing = model.get('pricing', {})
            prompt_price = pricing.get('prompt', '0')
            completion_price = pricing.get('completion', '0')

            # Check if model is actually free
            is_free = float(prompt_price) == 0 and float(completion_price) == 0

            # Format price display
            if is_free:
                price_display = "Free"
            else:
                price_display = f"${prompt_price}/${completion_price}"

            # Get context length
            context_length = model.get('context_length', 0)
            context_display = f"{context_length:,}" if context_length > 0 else "Unknown"

            # Categorize model by provider/name
            category = self.categorize_model(model_id, original_name)

            return {
                'id': model_id,
                'name': display_name,
                'display_name': display_name,
                'price_display': price_display,
                'context_length': context_length,
                'context_display': context_display,
                'pricing': pricing,
                'is_free': is_free,
                'category': category
            }
            
        except Exception as e:
            logging.error(f"Error formatting model: {e}")
            return {
                'id': model.get('id', ''),
                'name': model.get('name', 'Unknown'),
                'display_name': 'Unknown Model',
                'price_display': 'Unknown',
                'context_length': 0,
                'context_display': 'Unknown',
                'pricing': {},
                'is_free': False,
                'category': 'Other'
            }

    def categorize_model(self, model_id: str, model_name: str) -> str:
        """Categorize model by provider/type"""
        try:
            # Extract provider from model ID or name
            model_id_lower = model_id.lower()
            model_name_lower = model_name.lower()

            # OpenAI models
            if 'openai' in model_id_lower or 'gpt' in model_name_lower:
                return 'OpenAI'

            # Anthropic models
            elif 'anthropic' in model_id_lower or 'claude' in model_name_lower:
                return 'Anthropic'

            # Google models
            elif 'google' in model_id_lower or 'gemini' in model_name_lower or 'palm' in model_name_lower:
                return 'Google'

            # Meta models
            elif 'meta' in model_id_lower or 'llama' in model_name_lower:
                return 'Meta'

            # Mistral models
            elif 'mistral' in model_id_lower or 'mistral' in model_name_lower:
                return 'Mistral'

            # DeepSeek models
            elif 'deepseek' in model_id_lower or 'deepseek' in model_name_lower:
                return 'DeepSeek'

            # Cohere models
            elif 'cohere' in model_id_lower or 'command' in model_name_lower:
                return 'Cohere'

            # Perplexity models
            elif 'perplexity' in model_id_lower or 'pplx' in model_name_lower:
                return 'Perplexity'

            # Hugging Face models
            elif 'huggingface' in model_id_lower or 'hf' in model_id_lower:
                return 'Hugging Face'

            # Together models
            elif 'together' in model_id_lower:
                return 'Together'

            # Other providers
            elif 'qwen' in model_name_lower:
                return 'Qwen'
            elif 'yi' in model_name_lower:
                return 'Yi'
            elif 'phi' in model_name_lower:
                return 'Microsoft'
            elif 'wizardlm' in model_name_lower:
                return 'WizardLM'
            elif 'openchat' in model_name_lower:
                return 'OpenChat'
            elif 'nous' in model_name_lower:
                return 'Nous Research'
            elif 'dolphin' in model_name_lower:
                return 'Dolphin'
            else:
                return 'Other'

        except Exception as e:
            logging.error(f"Error categorizing model: {e}")
            return 'Other'

    def get_formatted_models_by_category(self) -> Dict:
        """Get all models organized by category"""
        try:
            models = self.get_all_models()
            if not models:
                return {}

            categorized = {
                'free': [],
                'openai': [],
                'anthropic': [],
                'google': [],
                'meta': [],
                'mistral': [],
                'cohere': [],
                'deepseek': [],
                'perplexity': [],
                'microsoft': [],
                'other': []
            }

            for model in models:
                formatted_model = self.format_model_for_select(model)
                category = formatted_model.get('category', 'Other').lower()

                # Map categories to keys
                if category == 'openai':
                    categorized['openai'].append(formatted_model)
                elif category == 'anthropic':
                    categorized['anthropic'].append(formatted_model)
                elif category == 'google':
                    categorized['google'].append(formatted_model)
                elif category == 'meta':
                    categorized['meta'].append(formatted_model)
                elif category == 'mistral':
                    categorized['mistral'].append(formatted_model)
                elif category == 'cohere':
                    categorized['cohere'].append(formatted_model)
                elif category == 'deepseek':
                    categorized['deepseek'].append(formatted_model)
                elif category == 'perplexity':
                    categorized['perplexity'].append(formatted_model)
                elif category == 'microsoft':
                    categorized['microsoft'].append(formatted_model)
                else:
                    categorized['other'].append(formatted_model)

                # Also add to free category if it's free
                if formatted_model.get('is_free', False):
                    categorized['free'].append(formatted_model)

            # Sort models within each category by name
            for category in categorized:
                categorized[category].sort(key=lambda x: x.get('name', ''))

            return categorized

        except Exception as e:
            logging.error(f"Error getting categorized models: {e}")
            return {}
    
    def get_formatted_models_by_category(self) -> Dict[str, List[Dict]]:
        """Get models organized by category for UI"""
        try:
            all_models = self.get_all_models()
            if not all_models:
                return {}
            
            categories = {
                'free': [],
                'openai': [],
                'anthropic': [],
                'google': [],
                'meta': [],
                'mistral': [],
                'cohere': [],
                'deepseek': [],
                'other': []
            }
            
            for model in all_models:
                formatted_model = self.format_model_for_select(model)
                model_id = model.get('id', '')
                
                # Categorize models
                if formatted_model['is_free']:
                    categories['free'].append(formatted_model)
                elif model_id.startswith('openai/'):
                    categories['openai'].append(formatted_model)
                elif model_id.startswith('anthropic/'):
                    categories['anthropic'].append(formatted_model)
                elif model_id.startswith('google/'):
                    categories['google'].append(formatted_model)
                elif model_id.startswith('meta-llama/'):
                    categories['meta'].append(formatted_model)
                elif model_id.startswith('mistralai/'):
                    categories['mistral'].append(formatted_model)
                elif model_id.startswith('cohere/'):
                    categories['cohere'].append(formatted_model)
                elif model_id.startswith('deepseek/'):
                    categories['deepseek'].append(formatted_model)
                else:
                    categories['other'].append(formatted_model)
            
            # Sort each category by name
            for category in categories:
                categories[category].sort(key=lambda x: x['name'])
            
            return categories
            
        except Exception as e:
            logging.error(f"Error organizing models by category: {e}")
            return {}
    
    def clear_cache(self):
        """Clear the API cache"""
        self._providers_cache = None
        self._models_cache = None
        self._cache_timestamp = None
        logging.info("OpenRouter API cache cleared")

# Global instance
openrouter_service = OpenRouterAPIService()
