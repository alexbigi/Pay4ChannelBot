from aiogram import Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import quote


class Markups:
    def __init__(self, dp: Dispatcher, texts: dict, payment_types: list, payment_blocks: list):
        self._dp = dp
        self._texts = texts
        self._payment_types = payment_types
        self._payment_blocks = payment_blocks

        self.menu = InlineKeyboardMarkup()
        self.menu.add(InlineKeyboardButton(self._texts['add_channel'], callback_data='channel_add'))
        self.menu.add(InlineKeyboardButton(self._texts['_channels'], callback_data='channels'))

        self.to_menu = InlineKeyboardMarkup()
        self.to_menu.add(InlineKeyboardButton(self._texts['menu'], callback_data='menu'))

        self.cancel = InlineKeyboardMarkup()
        self.cancel.add(InlineKeyboardButton(self._texts['cancel'], callback_data='cancel'))

    def channel(self, username: str, channel_id: int) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(self._texts['buy'], url='https://t.me/share/url?url={}'.format(quote('https://t.me/{}?start=buy_{}'.format(username, channel_id)))))
        markup.add(InlineKeyboardButton(self._texts['delete'], callback_data='channel_delete_{}'.format(channel_id)))
        markup.add(InlineKeyboardButton(self._texts['menu'], callback_data='menu'))
        return markup

    def channels(self, channels: list) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup()

        for channel in channels:
            markup.add(InlineKeyboardButton(channel[1], callback_data='channel_{}'.format(channel[0])))

        markup.add(InlineKeyboardButton(self._texts['menu'], callback_data='menu'))

        return markup

    def topup(self, channel_id: int, block=[]) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup()

        for payment_type in self._payment_types:
            if payment_type != block:
                index = self._payment_types.index(payment_type)

                if payment_type not in block:
                    markup.add(InlineKeyboardButton(payment_type, callback_data='topup_{}_{}'.format(index, channel_id)))

        return markup

    def qiwi_payment(self, payment_type: int, uuid: str, url: str) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(self._texts['pay'], url=url))
        markup.add(InlineKeyboardButton(self._texts['check_topup'], callback_data='topup_{}_{}_check'.format(payment_type, uuid)))
        markup.add(InlineKeyboardButton(self._texts['reject_topup'], callback_data='topup_{}_{}_reject'.format(payment_type, uuid)))
        return markup

    def btc_payment(self, payment_type: int, uuid: str) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(self._texts['check_topup'], callback_data='topup_{}_{}_check'.format(payment_type, uuid)))
        markup.add(InlineKeyboardButton(self._texts['reject_topup'], callback_data='topup_{}_{}_reject'.format(payment_type, uuid)))
        return markup

    def join(self, url: str) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(self._texts['join'], url=url))
        return markup
