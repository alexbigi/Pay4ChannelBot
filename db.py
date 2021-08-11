from pymongo import MongoClient, errors
from pymongo.cursor import Cursor
from typing import Optional, Union, Dict
from sys import exit


class DataBase:
    def __init__(self, db_url: str, db_name: str):
        try:
            self.client = MongoClient(db_url)
        except errors.ConfigurationError:
            exit('Can\'t connect to server!')

        self.db = self.client[db_name]

    def add_user(self, user_id: int) -> int:
        return self.db.users.insert_one({'user_id': user_id, 'channels': [], 'qiwi_token': None, 'payment': {}}).inserted_id

    def get_user(self, user_id: Optional[int]=None) -> Union[Cursor, Dict]:
        if user_id:
            return self.db.users.find_one({'user_id': user_id})

        return self.db.users.find({})

    def get_users_count(self) -> int:
        return self.db.users.count_documents({})

    def edit_user(self, user_id: int, user: dict) -> int:
        return self.db.users.update_one({'user_id': user_id}, {'$set': user})

    def add_user_channel(self, user_id: int, channel: dict) -> int:
        return self.db.users.update_one({'user_id': user_id}, {'$push': {'channels': channel}})

    def get_user_channels(self, user_id: int) -> Cursor:
        return self.db.users.find_one({'user_id': user_id})['channels']

    def get_user_by_channel(self, channel_id: int) -> dict:
        return self.db.users.find_one({'channels.id': channel_id})

    def get_user_by_payment(self, uuid: str) -> dict:
        return self.db.users.find_one({'payment.uuid': uuid})

    def delete_user_channel(self, user_id: int, channel: Optional[dict]=None) -> int:
        if channel != None:
            return self.db.users.update_one({'user_id': user_id}, {'$pull': {'channels': {'id': channel}}}).modified_count

        return self.db.users.update_many({'user_id': user_id}, {'$set': {'channels': []}}).modified_count

    def set_qiwi_token(self, user_id: int, qiwi_token: str) -> int:
        return self.db.users.update_one({'user_id': user_id}, {'$set': {'qiwi_token': qiwi_token}}).modified_count

    def delete_user(self, user_id: Optional[int]=None) -> int:
        if user_id:
            return self.db.users.delete_one({'user_id': user_id}).deleted_count

        return self.db.users.delete_many({}).deleted_count


if __name__ == '__main__':
    from config import db_url, db_name

    db = DataBase(db_url, db_name)

    print(db.get_users_count())
    print(type(db.get_users_count()))
