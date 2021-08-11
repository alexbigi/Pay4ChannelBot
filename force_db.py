from db import DataBase
from config import db_url, db_name


db = DataBase(db_url, db_name)


print('Removed {} rows!'.format(db.delete_user()))
