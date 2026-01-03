import requests
import base64
import re
import logging
import threading
import time
from django.conf import settings

logger = logging.getLogger(__name__)


class SigexAuthService:
    """Сервис для работы с Sigex API для аутентификации через eGov Mobile"""

    BASE_URL = getattr(settings, 'SIGEX_API_URL', 'https://sigex.kz')
    AUTH_DATA = getattr(settings, 'SIGEX_AUTH_DATA', 'LMS Authentication Request')

    @classmethod
    def init_qr_signing(cls, session_id: int):
        """
        Инициализирует новую процедуру подписания через QR.

        Args:
            session_id: ID сессии в БД для сохранения результата

        Returns:
            dict: {
                'qr_id': str,
                'qr_code': str (base64),
                'egov_mobile_link': str,
                'egov_business_link': str,
            }
        """
        try:
            # Шаг 1: Регистрация новой процедуры подписания
            response = requests.post(
                f'{cls.BASE_URL}/api/egovQr',
                json={'description': cls.AUTH_DATA},
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if 'message' in data:
                raise Exception(data['message'])

            # Извлекаем qr_id из dataURL
            data_url = data.get('dataURL', '')
            qr_id = data_url.split('/')[-1] if data_url else None

            if not qr_id:
                raise Exception('Не удалось получить qr_id из ответа')

            sign_url = data.get('signURL', '')

            result = {
                'qr_id': qr_id,
                'qr_code': data.get('qrCode', ''),
                'egov_mobile_link': data.get('eGovMobileLaunchLink', ''),
                'egov_business_link': data.get('eGovBusinessLaunchLink', ''),
            }

            # Шаг 2: Запускаем фоновый процесс для отправки документов и получения подписи
            def background_signing_flow():
                try:
                    logger.info(f'[Session {session_id}] Starting background signing flow...')

                    # 2.1 Отправляем документы (long-polling - ждёт пока eGov заберёт)
                    auth_text = cls.AUTH_DATA
                    auth_data_base64 = base64.b64encode(auth_text.encode('utf-8')).decode('utf-8')

                    documents_payload = {
                        'signMethod': 'CMS_WITH_DATA',
                        'documentsToSign': [
                            {
                                'id': 1,
                                'nameRu': 'Запрос на аутентификацию',
                                'nameKz': 'Аутентификация сұрауы',
                                'nameEn': 'Authentication Request',
                                'meta': [],
                                'document': {
                                    'file': {
                                        'mime': '',
                                        'data': auth_data_base64
                                    }
                                }
                            }
                        ]
                    }

                    logger.info(f'[Session {session_id}] Sending documents to {data_url}...')
                    send_resp = requests.post(
                        data_url,
                        json=documents_payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=300  # 5 минут - ждём пока eGov mobile заберёт документы
                    )
                    logger.info(f'[Session {session_id}] Documents sent, status: {send_resp.status_code}')

                    if send_resp.status_code != 200:
                        logger.error(f'[Session {session_id}] Failed to send documents')
                        return

                    # 2.2 Получаем подписи (long-polling - ждём пока пользователь подпишет)
                    logger.info(f'[Session {session_id}] Waiting for signature from {sign_url}...')
                    sign_resp = requests.get(
                        sign_url,
                        timeout=300  # 5 минут - ждём подпись
                    )
                    logger.info(f'[Session {session_id}] Got signature response, status: {sign_resp.status_code}')

                    if sign_resp.status_code == 200:
                        sign_data = sign_resp.json()

                        if 'message' in sign_data:
                            logger.error(f'[Session {session_id}] Sigex error: {sign_data["message"]}')
                            cls._update_session_error(session_id, sign_data['message'])
                            return

                        # Извлекаем подпись
                        documents = sign_data.get('documentsToSign', [])
                        if documents:
                            signature = documents[0].get('document', {}).get('file', {}).get('data')
                            if signature:
                                logger.info(f'[Session {session_id}] Signature received, parsing...')
                                cert_info = cls._parse_signature(signature)
                                cls._update_session_signed(session_id, signature, cert_info)
                                logger.info(f'[Session {session_id}] Session updated with signature data')
                            else:
                                logger.error(f'[Session {session_id}] No signature in response')
                        else:
                            logger.error(f'[Session {session_id}] No documents in response')

                except requests.Timeout:
                    logger.warning(f'[Session {session_id}] Signing flow timeout')
                    cls._update_session_error(session_id, 'Timeout')
                except Exception as e:
                    logger.error(f'[Session {session_id}] Background signing error: {e}')
                    cls._update_session_error(session_id, str(e))

            # Запускаем фоновый поток
            thread = threading.Thread(target=background_signing_flow, daemon=True)
            thread.start()

            # Даём потоку время запуститься
            time.sleep(0.5)

            return result

        except requests.RequestException as e:
            logger.error(f'Sigex API error: {e}')
            raise Exception(f'Ошибка связи с Sigex: {str(e)}')

    @classmethod
    def _update_session_signed(cls, session_id: int, signature: str, cert_info: dict):
        """Обновляет сессию после успешного подписания"""
        from account.models import EgovAuthSession
        try:
            session = EgovAuthSession.objects.get(id=session_id)
            session.status = 'signed'
            session.iin = cert_info.get('iin')
            session.first_name = cert_info.get('first_name')
            session.last_name = cert_info.get('last_name')
            session.middle_name = cert_info.get('middle_name')
            session.save()
        except Exception as e:
            logger.error(f'Error updating session {session_id}: {e}')

    @classmethod
    def _update_session_error(cls, session_id: int, error: str):
        """Обновляет сессию при ошибке"""
        from account.models import EgovAuthSession
        try:
            session = EgovAuthSession.objects.get(id=session_id)
            session.status = 'error'
            session.save()
        except Exception as e:
            logger.error(f'Error updating session {session_id}: {e}')

    @classmethod
    def check_signing_status(cls, qr_id: str) -> dict:
        """
        Проверяет статус подписания из БД (быстрая проверка).
        Фактическое получение подписи происходит в фоновом потоке.
        """
        # Теперь просто возвращаем pending - реальный статус берётся из БД во view
        return {'status': 'pending'}

    @classmethod
    def _parse_signature(cls, signature_base64: str) -> dict:
        """Парсит CMS подпись и извлекает данные сертификата."""
        result = {
            'iin': None,
            'first_name': None,
            'last_name': None,
            'middle_name': None
        }

        try:
            from cryptography.hazmat.primitives.serialization import pkcs7

            signature_bytes = base64.b64decode(signature_base64)
            certs = pkcs7.load_der_pkcs7_certificates(signature_bytes)

            if certs:
                cert = certs[0]
                subject = cert.subject

                cn_value = None

                for attr in subject:
                    oid = attr.oid.dotted_string
                    value = attr.value

                    if oid == '2.5.4.5':  # serialNumber → IIN
                        iin = cls._extract_iin(value)
                        if iin:
                            result['iin'] = iin
                    elif oid == '2.5.4.3':  # commonName → Фамилия + Имя
                        cn_value = value
                    elif oid == '2.5.4.4':  # surname → Фамилия
                        result['last_name'] = value
                    elif oid == '2.5.4.42':  # givenName → Отчество (в KZ сертификатах)
                        result['middle_name'] = value

                # Имя берём из CN (второе слово)
                if cn_value:
                    parts = cn_value.strip().split()
                    if len(parts) >= 2:
                        result['first_name'] = parts[1]  # Второе слово = имя
                    # Если фамилия не заполнена, берём из CN
                    if not result['last_name'] and len(parts) >= 1:
                        result['last_name'] = parts[0]

        except Exception as e:
            logger.error(f'Error parsing signature: {e}')

        logger.info(f'PARSED RESULT: {result}')
        return result

    @classmethod
    def _extract_iin(cls, serial_number: str) -> str | None:
        match = re.search(r'IIN(\d{12})', serial_number)
        if match:
            return match.group(1)
        return None

    @classmethod
    def _parse_cn(cls, cn: str) -> dict:
        result = {
            'first_name': None,
            'last_name': None,
            'middle_name': None
        }

        parts = cn.strip().split()
        if len(parts) >= 1:
            result['last_name'] = parts[0]
        if len(parts) >= 2:
            result['first_name'] = parts[1]
        if len(parts) >= 3:
            result['middle_name'] = ' '.join(parts[2:])

        return result