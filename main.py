from aiogram import Bot, Dispatcher, filters, types, exceptions, executor
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types.callback_query import CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from decimal import Decimal
from uuid import uuid4
from db import DataBase
from markups import Markups
from payments import QIWI, Bitcoin
from time import time
from asyncio import sleep
from config import bot_token, db_name, db_url, admins, texts, payment_types, currency_type, payment_blocks


bot = Bot(bot_token, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())

db = DataBase(db_url, db_name)

markups = Markups(dp, texts, payment_types, payment_blocks)

currency = 0


only_admins = filters.IDFilter(user_id=admins)

channel_types = [types.ChatType.CHANNEL, types.ChatType.SUPERGROUP, types.ChatType.GROUP]


class AddChannelForm(StatesGroup):
    channel_id = State()
    cost = State()
    qiwi_token = State()


class AdminForm(StatesGroup):
    mail = State()
    mail_markup = State()


class UsersMiddleware(BaseMiddleware):
    def __init__(self):
        super(UsersMiddleware, self).__init__()

    async def on_pre_process_message(self, message: types.Message, data: dict):
        if message.chat.type == types.ChatType.PRIVATE and not db.get_user(user_id=message.from_user.id):
            db.add_user(user_id=message.from_user.id)


async def currency_scheduler():
    global currency
    currency = await Bitcoin.currency(currency_type)


async def on_startup(dp: Dispatcher):
    await currency_scheduler()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(currency_scheduler, trigger=IntervalTrigger(minutes=1))
    scheduler.start()


@dp.callback_query_handler(state='*')
async def callback_query_handler(callback_query: CallbackQuery, state: FSMContext):
    args = callback_query.data.split('_')
    message = callback_query.message

    if args[0] == 'menu':
        await message.edit_text(texts['start'], reply_markup=markups.menu)

    elif args[0] == 'topup':
        payment_type = int(args[1])

        user = db.get_user(callback_query.from_user.id)

        if payment_type == 0:
            if len(args) == 3:
                channel_id = int(args[2])
                channel_owner = db.get_user_by_channel(channel_id)

                uuid = uuid4()

                for channel in channel_owner['channels']:
                    if channel['id'] == channel_id:
                        amount = channel['cost']

                user['payment'] = {'channel_id': channel_id}
                db.edit_user(user['user_id'], user)

                url = await QIWI.create(channel_owner['qiwi_token'], uuid, amount)

                await message.edit_text(texts['topup'].format(payment_type=payment_types[payment_type], details=''), reply_markup=markups.qiwi_payment(payment_type, uuid, url))

            elif args[3] == 'check':
                channel_id = user['payment']['channel_id']
                channel_owner = db.get_user_by_channel(channel_id)

                uuid = args[2]

                if await QIWI.is_paid(channel_owner['qiwi_token'], uuid):
                    invite_link = await bot.create_chat_invite_link(channel_id, member_limit=1)
                    invite_link = invite_link.invite_link

                    await bot.send_message(channel_owner['user_id'], texts['new_topup'].format(payment_type=payment_types[payment_type], details=''))
                    await message.edit_text(texts['succesful_topup'].format(invite_link=invite_link), disable_web_page_preview=True, reply_markup=markups.join(invite_link))

                    user['payment'] = {}
                    db.edit_user(user['user_id'], user)

                else:
                    return await callback_query.answer(texts['not_paid'])

            elif args[3] == 'reject':
                uuid = args[2]

                channel_id = user['payment']['channel_id']
                channel_owner = db.get_user_by_channel(channel_id)

                await QIWI.reject(channel_owner['qiwi_token'], uuid)
                await message.edit_text(texts['cancelled'], reply_markup=markups.to_menu)

        elif payment_type == 1:
            if len(args) == 3:
                channel_id = int(args[2])
                channel_owner = db.get_user_by_channel(channel_id)

                uuid = uuid4()

                for channel in channel_owner['channels']:
                    if channel['id'] == channel_id:
                        amount = channel['cost']

                wallet = Bitcoin.generate()

                user['payment'] = {
                    'channel_id': channel_id,
                    'amount': str(round(Decimal(amount / currency), 10)),
                    'private': wallet['private'],
                    'public': wallet['public'],
                    'address': wallet['address']
                }

                db.edit_user(user['user_id'], user)

                await message.edit_text(
                    texts['topup'].format(payment_type=payment_types[payment_type],
                        details=texts['topup_btc'].format(
                            amount=user['payment']['amount'],
                            address=user['payment']['address']
                        )
                    ), reply_markup=markups.btc_payment(payment_type, uuid)
                )

            elif args[3] == 'check':
                channel_id = user['payment']['channel_id']
                channel_owner = db.get_user_by_channel(channel_id)

                uuid = args[2]

                balance = await Bitcoin.balance(user['payment']['address'])

                if balance >= Decimal(user['payment']['amount']):
                    invite_link = await bot.create_chat_invite_link(channel_id, member_limit=1)
                    invite_link = invite_link.invite_link

                    await bot.send_message(
                        channel_owner['user_id'], texts['new_topup'].format(
                            payment_type=payment_types[payment_type],
                            details=texts['btc_details'].format(
                                address=user['payment']['address'],
                                private=user['payment']['private'],
                                public=user['payment']['public']
                            )
                        )
                    )

                    await message.edit_text(texts['succesful_topup'].format(invite_link=invite_link), disable_web_page_preview=True, reply_markup=markups.join(invite_link))

                    user['payment'] = {}
                    db.edit_user(user['user_id'], user)

                else:
                    return await callback_query.answer(texts['not_paid'])

            elif args[3] == 'reject':
                user['payment'] = {}
                db.edit_user(user['user_id'], user)

                await message.edit_text(texts['cancelled'], reply_markup=markups.to_menu)

    elif args[0] == 'channel':
        if args[1] == 'add':
            await AddChannelForm.channel_id.set()
            await message.edit_text(texts['enter_channel_id'], reply_markup=markups.cancel)

        elif args[1] == 'delete':
            db.delete_user_channel(callback_query.from_user.id, int(args[2]))
            await message.edit_text(texts['deleted'], reply_markup=markups.to_menu)

        else:
            try:
                channel_id = int(args[1])

                if not db.get_user_by_channel(channel_id):
                    raise Exception

                channel = await bot.get_chat(channel_id)

                await message.edit_text(texts['channel'].format(
                    id=channel.id, title=channel.title, description=channel.description),
                    reply_markup=markups.channel((await bot.me).username, channel.id)
                )

            except:
                db.delete_user_channel(callback_query.from_user.id, channel.id)
                await message.edit_text(texts['no_channel'], reply_markup=markups.to_menu)

    elif args[0] == 'channels':
        channels = []

        for channel in db.get_user_channels(callback_query.from_user.id):
            try:
                channel = await bot.get_chat(channel['id'])
                channels.append([channel['id'], channel.title])
            except:
                db.delete_user_channel(callback_query.from_user.id, channel['id'])

        await message.edit_text(texts['channels'], reply_markup=markups.channels(channels))

    elif args[0] == 'cancel':
        await state.finish()
        await message.edit_text(texts['cancelled'], reply_markup=markups.to_menu)

    await callback_query.answer()


@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    try:
        channel_id = int(message.text.split(' ')[1].replace('buy_', ''))
        channel_owner = db.get_user_by_channel(channel_id)

        if not channel_owner:
            raise Exception

        title = (await bot.get_chat(channel_id)).title

        block = []

        for channel in channel_owner['channels']:
            if channel['id'] == channel_id:
                for payment_block in payment_blocks:
                    if channel['cost'] < payment_block:
                        block.append(payment_types[payment_blocks.index(payment_block)])

        await message.answer(texts['channel_topup'].format(title=title), reply_markup=markups.topup(channel_id, block=block))

    except:
        await message.answer(texts['start'], reply_markup=markups.menu)


@dp.message_handler(state=AddChannelForm.channel_id)
async def process_channel_id(message: types.Message, state: FSMContext):
    channel_id = message.forward_from_chat.id if message.forward_from_chat and message.forward_from_chat.type in channel_types else message.text
    
    try:
        channel_id = int(channel_id)

        if db.get_user_by_channel(channel_id) or (await bot.get_chat(channel_id)).type not in channel_types:
            raise Exception

    except:
        return await message.answer(texts['error_add_channel'], reply_markup=markups.cancel)

    async with state.proxy() as data:
        data['channel_id'] = channel_id

    await AddChannelForm.next()
    await message.answer(texts['enter_join_cost'].format(currency_type=currency_type), reply_markup=markups.cancel)


@dp.message_handler(state=AddChannelForm.cost)
async def process_cost(message: types.Message, state: FSMContext):
    try:
        cost = int(message.text)

        if cost < 1:
            raise Exception

    except:
        await message.answer(texts['error_join_cost'])

    async with state.proxy() as data:
        data['cost'] = cost

    user = db.get_user(message.from_user.id)

    if not user['qiwi_token']:
        await AddChannelForm.next()
        await message.answer(texts['enter_qiwi_token'], reply_markup=markups.cancel)
    else:
        db.add_user_channel(message.from_user.id, {'id': data['channel_id'], 'cost': data['cost']})
        await state.finish()
        await message.answer(texts['channel_added'], reply_markup=markups.to_menu)


@dp.message_handler(state=AddChannelForm.qiwi_token)
async def process_qiwi_token(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['qiwi_token'] = None if message.text in ['.', '-'] else message.text
        user = db.get_user(message.from_user.id)
        user['qiwi_token'] = data['qiwi_token']
        db.edit_user(user['user_id'], user)

    db.add_user_channel(message.from_user.id, {'id': data['channel_id'], 'cost': data['cost']})
    await state.finish()
    await message.answer(texts['channel_added'], reply_markup=markups.to_menu)


@dp.message_handler(only_admins, commands=['users', 'count'])
async def users_handler(message: types.Message):
    await message.answer(texts['users'].format(count=db.get_users_count()))


@dp.message_handler(commands=['mail', 'mailing'])
async def mailing_handler(message: types.Message):
    await AdminForm.mail.set()
    await message.answer(texts['enter_mail'], reply_markup=markups.cancel)


@dp.message_handler(content_types=types.ContentType.all(), state=AdminForm.mail)
async def process_mailing_handler(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['message'] = message

    await AdminForm.next()
    await message.answer(texts['enter_mail_markup'], reply_markup=markups.cancel)


@dp.message_handler(state=AdminForm.mail_markup)
async def process_mailing_markup_handler(message: types.Message, state: FSMContext):
    markup = types.InlineKeyboardMarkup()

    if message.text not in ['-', '.']:
        try:
            for line in message.text.split('\n'):
                text, url = line.split(' - ')
                markup.add(types.InlineKeyboardButton(text, url=url))

            markup.to_python()

        except:
            return await message.answer(texts['incorrect_mail_markup'], reply_markup=markups.cancel)

    async with state.proxy() as data:
        _message: types.Message = data['message']

    total = 0
    sent = 0
    unsent = 0

    await state.finish()

    await message.answer(texts['sending_mail'])

    start = time()

    for user in db.get_user():
        try:
            await _message.copy_to(user['user_id'], reply_markup=markup)
            sent += 1
        except:
            unsent += 1

        total += 1

        await sleep(0.04)

    await message.answer(texts['mail_stats'].format(total=total, sent=sent, unsent=unsent, time=round(time() - start, 3)))


dp.middleware.setup(UsersMiddleware())


if __name__ == '__main__':
    from sys import exit

    try:
        executor.start_polling(dp, skip_updates=False, on_startup=on_startup)
    except KeyboardInterrupt:
        exit(1)
