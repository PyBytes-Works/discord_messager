import datetime
import os

from peewee import (
    CharField, BooleanField, DateTimeField, ForeignKeyField
)
from peewee import Model
from config import logger, db, admins_list, db_file_name


class BaseModel(Model):
    """A base model that will use our Sqlite database."""

    class Meta:
        database = db
        order_by = 'date_at'


class User(BaseModel):
    """
    Model for table users
      methods
        get_telegram_id
        get_user_id_by_telegram_id
        get_user_by_telegram_id
        add_new_user
        delete_user_by_telegram_id
        get_active_users
        get_working_users
        set_user_is_work
        set_user_is_not_work
        get_subscribers_list
        deactivate_user
        activate_user
        set_user_status_admin
        delete_status_admin
        is_admin
        is_active
    """

    telegram_id = CharField(unique=True, verbose_name="id пользователя в телеграмм")
    nick_name = CharField(max_length=50, verbose_name="Ник")
    first_name = CharField(max_length=50, null=True, verbose_name="Имя")
    last_name = CharField(max_length=50, null=True, verbose_name="фамилия")
    active = BooleanField(default=True, verbose_name="Активирован")
    is_work = BooleanField(default=False, verbose_name='В работе / в настройке')
    admin = BooleanField(default=False, verbose_name="Администраторство")
    created_at = DateTimeField(default=datetime.datetime.now())
    expiration = DateTimeField(default=datetime.datetime.now())

    class Meta:
        db_table = "users"

    @classmethod
    @logger.catch
    def get_telegram_id(cls: 'User', id: str) -> str:
        """
        method returning telegram id for user by user id
        if the user is not in the database will return None
        return: telegram_id: str
        """
        user = cls.get_or_none(cls.id == id)
        return user.telegram_id if user else None

    @classmethod
    @logger.catch
    def get_user_id_by_telegram_id(cls: 'User', telegram_id: str) -> str:
        """
        if the user is in the database it returns the id, otherwise it returns None
        return: id: str
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        return str(user.id) if user else None

    @classmethod
    @logger.catch
    def get_user_by_telegram_id(cls: 'User', telegram_id: str) -> 'User':
        """
        Returns User`s class instance if user with telegram_id in database else None

        if the user is already in the database, returns the user
        otherwise it will return none

        return: User
        """
        return cls.get_or_none(cls.telegram_id == telegram_id)

    @classmethod
    @logger.catch
    def add_new_user(cls: 'User', nick_name: str, telegram_id: str) -> str:
        """
        if the user is already in the database, returns None
        if created user will return user id
        return: str
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if not user:
            return cls.create(nick_name=f'{nick_name}_{telegram_id}', telegram_id=telegram_id).save()

    @classmethod
    @logger.catch
    def delete_user_by_telegram_id(cls: 'User', telegram_id: str) -> None:
        """
        delete user by telegram id
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        if user:
            user.delete_instance()

    @classmethod
    @logger.catch
    def get_active_users(cls: 'User') -> list:
        """
        return list of telegram ids for active users
        return: list
        """
        return [user.telegram_id for user in cls.select(cls.telegram_id).where(cls.active == True)]

    @classmethod
    @logger.catch
    def get_all_users(cls: 'User') -> dict:
        """
        returns dict of users
        return: dict
        """
        return {
            user.telegram_id: (f'{user.nick_name.rsplit("_", maxsplit=1)[0]} | '
                               f'{"Active" if user.active else "Not active"} | '
                               f'{"In work" if user.is_work else "Not in work"} | '
                               f'{"Admin" if user.admin else "Not admin"} | ')
            for user in User.select().execute()
        }

    @classmethod
    @logger.catch
    def get_working_users(cls: 'User') -> list:
        """
        return list of telegram ids for active users with active subscription
        return: list
        """
        return [
            user.telegram_id for user in cls.select(
                cls.telegram_id).where(cls.is_work == True).where(cls.active == True).execute()
        ]

    @classmethod
    @logger.catch
    def set_user_is_work(cls: 'User', telegram_id: str) -> bool:
        """
        set subscriber value enabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(is_work=True).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def set_user_is_not_work(cls: 'User', telegram_id: str) -> bool:
        """
        set subscriber value disabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(is_work=False).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def get_subscribers_list(cls: 'User') -> list:
        """ возвращает список пользователей которым должна отправляться рассылка"""

        return [user.telegram_id
                for user in cls
                    .select(cls.telegram_id)
                    .where(cls.active == True)
                    .where(cls.is_work == True)]

    @classmethod
    @logger.catch
    def deactivate_user(cls: 'User', telegram_id: str) -> bool:
        """
        set active value disabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(active=False).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def activate_user(cls: 'User', telegram_id: str) -> bool:
        """
        set active value disabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(active=True).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def set_user_status_admin(cls: 'User', telegram_id: str) -> bool:
        """
        set admin value enabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(admin=True).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def delete_status_admin(cls: 'User', telegram_id: str) -> bool:
        """
        set admin value enabled for user
        return: 1 if good otherwise 0
        """
        return cls.update(admin=False).where(cls.telegram_id == telegram_id).execute()

    @classmethod
    @logger.catch
    def is_admin(cls: 'User', telegram_id: str) -> bool:
        """
        checks if the user is an administrator
        return: bool
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        return user.admin if user else False

    @classmethod
    @logger.catch
    def is_active(cls: 'User', telegram_id: str) -> bool:
        """
        checks if the user is active
        return: bool
        """
        user = cls.get_or_none(cls.telegram_id == telegram_id)
        return user.active if user else False


class Filter(BaseModel):
    """
    model filter
      methods:
        add_filter
        update_filter
        clear_filter
        delete_filter
        get_filer
    """
    user = ForeignKeyField(User, unique=True, on_delete='CASCADE')
    max_price = CharField(max_length=50, verbose_name='min price lot', default='')
    min_price = CharField(max_length=50, verbose_name='max price lot', default='')
    status = CharField(max_length=50, verbose_name='Lot status', default='')
    type = CharField(max_length=50, verbose_name='Lot type', default='')

    class Meta:
        db_table = "filters"

    @classmethod
    @logger.catch
    def add_or_update(
            cls,
            telegram_id: str,
            max_price: str = None,
            min_price: str = None,
            status: str = None,
            type: str = None
    ) -> bool:
        """
        add or update filter for user if user there is in table users
        return: id record or None
        """
        user_id = User.get_user_id_by_telegram_id(telegram_id)
        if user_id:
            record: cls = cls.get_or_create(user=user_id)[0]

            data = (
                ('max_price', max_price),
                ('min_price', min_price),
                ('status', status),
                ('type', type)
            )
            data_add = {key: value for key, value in data if value is not None}
            if data_add:
                record.update(**data_add).where(cls.user == user_id).execute()
            return record

    @classmethod
    @logger.catch
    def clear_filters(cls, telegram_id: str) -> bool:
        """
        method sets all user filter values == ''
        return: record id or None
        """
        user_id = User.get_user_id_by_telegram_id(telegram_id)
        if user_id:
            return cls.update(
                {'max_price': '', 'min_price': '', 'status': '', 'type': ''}
            ).where(cls.user == user_id).execute()

    @classmethod
    @logger.catch
    def get_filters_for_user(cls, telegram_id: str) -> dict:
        """
        method to get all filters for one the user
        return: dict
        """
        user_id = User.get_user_id_by_telegram_id(telegram_id)
        if user_id:
            filters: cls = cls.get_or_none(cls.user == user_id)
            if filters:
                return {
                    'price': (
                        filters.min_price if filters.min_price else None,
                        filters.max_price if filters.max_price else None
                    ),
                    'status': filters.status if filters.status else None,
                    'type': filters.type if filters.type else None
                }
            return {
                'price': (None, None),
                'status': None,
                'type': None
            }


class UserCollection(BaseModel):
    """
    Model for filters by collections table
      methods:
        add_collection
        delete_collection
        clear_collections
        get_collections
    """
    user = ForeignKeyField(User, on_delete="CASCADE")
    collection_name = CharField(max_length=255, verbose_name="Название коллекции")

    class Meta:
        db_table = "user_collections"

    @classmethod
    @logger.catch
    def add_collection(cls, telegram_id: str, collection_name: str) -> None:
        """
        method for adding a collection for a user
        return: id record or None
        """
        user_id = User.get_user_by_telegram_id(telegram_id)
        if user_id:
            return cls.get_or_create(user=user_id, collection_name=collection_name)[-1]

    @classmethod
    @logger.catch
    def delete_collection(cls, telegram_id: str, collection_name: str) -> None:
        """
        method removes one collection of the user
        return: id record or none
        """
        user_id = User.get_user_by_telegram_id(telegram_id)
        if user_id:
            return cls.delete().where(
                cls.user == user_id, cls.collection_name == collection_name
            ).execute()

    @classmethod
    @logger.catch
    def clear_collection(cls, telegram_id: str) -> None:
        """
        method to delete all collections of one user
        return: sql or none
        """
        user_id = User.get_user_by_telegram_id(telegram_id)
        if user_id:
            return cls.delete().where(
                cls.user == user_id
            ).execute()

    @classmethod
    @logger.catch
    def get_collections(cls, telegram_id: str) -> dict:
        """
        Returns dictionary of collection by user telegram_id

        method for get all collection for one user
        return: dict
        """
        collections = None
        user_id = User.get_user_by_telegram_id(telegram_id)
        if user_id:
            records = cls.select(cls.collection_name).where(cls.user == user_id).execute()
            if len(records):
                collections = tuple(record.collection_name for record in records)
            return {'collections': collections}


class AllFilters:
    """
    Model for filters
      methods
        get_full_filter_by_telegram_id
        clear_filters_and_collections_by_telegram_id
        delete_filters_and_collections_by_telegram_id
    """

    @classmethod
    @logger.catch
    def get_full_filter_and_collections_by_telegram_id(cls, telegram_id: str) -> dict:
        """
        full filter and collections
        return: dict
        """
        full_filter = Filter.get_filters_for_user(telegram_id)
        collections = UserCollection.get_collections(telegram_id)
        if full_filter is not None:
            full_filter.update(collections)
        return full_filter

    @classmethod
    @logger.catch
    def clear_filters_and_collections_by_telegram_id(cls, telegram_id: str) -> None:
        """
        clear all filters and delete collections for a user
        return: None
        """
        Filter.clear_filters(telegram_id)
        UserCollection.clear_collection(telegram_id)

    @classmethod
    @logger.catch
    def add_or_update_filters_by_telegram_id(cls, telegram_id: str,
                                             max_price: str = None,
                                             min_price: str = None,
                                             status: str = None,
                                             type: str = None
                                             ) -> bool:
        return Filter.add_or_update(telegram_id, max_price, min_price, status, type)

    @classmethod
    @logger.catch
    def clear_filter_price_by_telegram_id(cls, telegram_id: str) -> bool:
        """"""
        return Filter.add_or_update(telegram_id, max_price="", min_price="")

    @classmethod
    @logger.catch
    def clear_filter_status_by_telegram_id(cls, telegram_id: str) -> bool:
        return Filter.add_or_update(telegram_id, status="")

    @classmethod
    @logger.catch
    def clear_filter_type_by_telegram_id(cls, telegram_id: str) -> bool:
        return Filter.add_or_update(telegram_id, type="")

    @classmethod
    @logger.catch
    def add_collection_by_telegram_id(cls, telegram_id: str, collection_name: str) -> None:
        UserCollection.add_collection(telegram_id=telegram_id, collection_name=collection_name)

    @classmethod
    @logger.catch
    def delete_collection(cls, telegram_id: str, collection_name: str) -> None:
        UserCollection.delete_collection(telegram_id=telegram_id, collection_name=collection_name)

    @classmethod
    @logger.catch
    def clear_collection(cls, telegram_id: str) -> None:
        UserCollection.clear_collection(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    def get_collections(cls, telegram_id: str) -> dict:
        return UserCollection.get_collections(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    def clear_filters_by_telegram_id(cls, telegram_id: str) -> bool:
        return Filter.clear_filters(telegram_id=telegram_id)

    @classmethod
    @logger.catch
    def get_filters_for_user(cls, telegram_id):
        return Filter.get_filters_for_user(telegram_id=telegram_id)


@logger.catch
def drop_db() -> None:
    """Deletes all tables in database"""

    with db:
        try:
            db.drop_tables([User, Filter, UserCollection], safe=True)
            logger.info('DB deleted')
        except Exception as err:
            logger.error(f"Ошибка удаления таблиц БД: {err}")


@logger.catch
def recreate_db(db_file_name: str) -> None:
    """Creates new tables in database. Drop all data from DB if it exists."""

    with db:
        if os.path.exists(db_file_name):
            drop_db()
        db.create_tables([User, Filter, UserCollection], safe=True)
        logger.info('DB REcreated')


if __name__ == '__main__':
    recreate_db(db_file_name)
    for admin_id in admins_list:
        nick_name = "Admin"
        User.add_new_user(nick_name=nick_name, telegram_id=admin_id)
        User.set_user_status_admin(telegram_id=admin_id)
        logger.info(f"User {nick_name} with id {admin_id} created as ADMIN.")

