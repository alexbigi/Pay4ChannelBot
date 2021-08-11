from aiohttp import ClientSession
from datetime import datetime, timedelta, timezone
from json import loads

from bitcoin import random_key, sha256, privkey_to_pubkey, pubkey_to_address
from aiohttp import ClientSession
from decimal import Decimal
from binascii import unhexlify
from hashlib import sha256 as _sha256
from base58 import b58encode


class QIWI:
    def __init__(self):
        super(QIWI, self).__init__()

    @classmethod
    async def _request(self, method: str, token: str, url, json=None) -> dict:
        async with ClientSession(headers={'Authorization': 'Bearer {}'.format(token), 'Content-Type': 'application/json', 'Accept': 'application/json'}) as session:
            async with session.request(method, url, json=json) as request:
                return loads(await request.text())

    @classmethod
    async def create(self, token: str, id: str, amount: float) -> str:
        expires = datetime.now(timezone(timedelta(hours=3))).replace(microsecond=0) + timedelta(days=2)
        response = await self._request('PUT', token, 'https://api.qiwi.com/partner/bill/v1/bills/{}'.format(id), json={'amount': {'value': amount, 'currency': 'RUB'}, 'expirationDateTime': expires.isoformat()})
        return response['payUrl']

    @classmethod
    async def is_paid(self, token: str, id: str) -> bool:
        response = await self._request('GET', token, 'https://api.qiwi.com/partner/bill/v1/bills/{}'.format(id))
        return response['status']['value'] == 'PAID'

    @classmethod
    async def reject(self, token: str, id: str) -> dict:
        return await self._request('POST', token, 'https://api.qiwi.com/partner/bill/v1/bills/{}/reject'.format(id))


class Bitcoin:
    BALANCE_URL = 'https://blockchain.info/balance?active={address}'
    TICKER_URL = 'https://blockchain.info/ticker'

    def __init__(self):
        pass

    async def _request(self, url: str, method: str='GET', params: dict=None) -> dict:
        async with ClientSession() as session:
            async with session.request(method, url, params=params) as request:
                return await request.json()

    @classmethod
    def generate(self) -> dict:
        key = random_key()
        private = sha256(key)
        public = privkey_to_pubkey(private)
        address = pubkey_to_address(public)
        private = self.privkey_to_wif(private)

        return {'private': private, 'public': public, 'address': address}

    @classmethod
    def privkey_to_wif(self, private: str) -> str:
        extended_key = '80{}01'.format(private)
        first_sha256 = _sha256(unhexlify(extended_key)).hexdigest()
        second_sha256 = _sha256(unhexlify(first_sha256)).hexdigest()
        return b58encode(unhexlify(extended_key + second_sha256[:8]))

    @classmethod
    async def balance(self, address: str) -> Decimal:
        request = await self._request(self, self.BALANCE_URL.format(address=address))
        return Decimal(request[address]['final_balance'])

    @classmethod
    async def currency(self, currency_type: str) -> float:
        request = await self._request(self, self.TICKER_URL)
        return request[currency_type]['buy']
