import requests
import time
from typing import Optional, Dict, Any
from django.conf import settings
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SendPulseService:
    """Сервис для работы с SendPulse API"""

    TOKEN_CACHE_KEY = 'sendpulse_access_token'
    TOKEN_CACHE_TIMEOUT = 3600  # 1 час

    def __init__(self):
        self.api_id = settings.SENDPULSE_API_ID
        self.api_secret = settings.SENDPULSE_API_SECRET
        self.api_url = settings.SENDPULSE_API_URL

    def _get_access_token(self) -> Optional[str]:
        """Получить access token (с кешированием)"""
        # Проверяем кеш
        token = cache.get(self.TOKEN_CACHE_KEY)
        if token:
            return token

        # Запрашиваем новый токен
        url = f"{self.api_url}/oauth/access_token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.api_id,
            'client_secret': self.api_secret,
        }

        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            token = result.get('access_token')
            if token:
                # Кешируем на 50 минут (токен живет 1 час)
                cache.set(self.TOKEN_CACHE_KEY, token, 3000)
                return token

        except requests.RequestException as e:
            print(f"Ошибка получения токена SendPulse: {e}")
            return None

        return None

    def send_email(
            self,
            to_email: str,
            subject: str,
            html_content: str,
            from_email: Optional[str] = None,
            from_name: Optional[str] = None,
            attachments: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Отправить email через SendPulse API

        attachments: список словарей [{'filename': 'cert.pdf', 'data': base64_string}]
        """
        token = self._get_access_token()
        if not token:
            return {
                'success': False,
                'message': 'Не удалось получить access token',
                'response': None
            }

        url = f"{self.api_url}/smtp/emails"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        sender_email = from_email or settings.SENDPULSE_FROM_EMAIL

        logger.info("=" * 50)
        logger.info("SendPulse API Request:")
        logger.info(f"From: {sender_email}")
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Attachments: {len(attachments) if attachments else 0}")
        logger.info("=" * 50)

        # Payload
        payload = {
            'email': {
                'text': html_content,
                'html': html_content,
                'subject': subject,
                'from': {
                    'email': sender_email,
                },
                'to': [
                    {
                        'email': to_email,
                    }
                ],
            }
        }

        # Добавляем attachments если есть
        if attachments:
            payload['email']['attachments_binary'] = attachments

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            logger.info(f"SendPulse Success: {result}")

            return {
                'success': True,
                'message': 'Email успешно отправлен',
                'response': result
            }

        except requests.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = f"{error_message}: {error_data}"
                except:
                    error_message = f"{error_message}: {e.response.text}"

            logger.error(f"SendPulse Error: {error_message}")

            return {
                'success': False,
                'message': error_message,
                'response': None
            }