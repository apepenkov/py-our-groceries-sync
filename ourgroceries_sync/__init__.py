#!/usr/bin/env python

import re
import json
import requests
import logging

from .exceptions import InvalidLoginException


_LOGGER = logging.getLogger(__name__)

# urls used
BASE_URL = "https://www.ourgroceries.com"
SIGN_IN = "{}/sign-in".format(BASE_URL)
YOUR_LISTS = "{}/your-lists/".format(BASE_URL)

# cookies
COOKIE_KEY_SESSION = "ourgroceries-auth"

# form fields when logging in
FORM_KEY_USERNAME = "emailAddress"
FORM_KEY_PASSWORD = "password"
FORM_KEY_ACTION = "action"
FORM_VALUE_ACTION = "sign-in"

# actions to preform on post api
ACTION_GET_LIST = "getList"
ACTION_GET_LISTS = "getOverview"

ACTION_ITEM_CROSSED_OFF = "setItemCrossedOff"
ACTION_ITEM_ADD = "insertItem"
ACTION_ITEM_ADD_ITEMS = "insertItems"
ACTION_ITEM_REMOVE = "deleteItem"
ACTION_ITEM_RENAME = "changeItemValue"

ACTION_LIST_CREATE = "createList"
ACTION_LIST_REMOVE = "deleteList"
ACTION_LIST_RENAME = "renameList"

ACTION_GET_MASTER_LIST = "getMasterList"
ACTION_GET_CATEGORY_LIST = "getCategoryList"

ACTION_ITEM_CHANGE_VALUE = "changeItemValue"
ACTION_LIST_DELETE_ALL_CROSSED_OFF = "deleteAllCrossedOffItems"
REGEX_MASTER_LIST_ID = r'href="/your-lists/list/(\S*)".*Manage Master List'
ATTR_CATEGORY_ID = "categoryId"
ATTR_ITEM_NEW_VALUE = "newValue"


# regex to get team id
REGEX_TEAM_ID = r'g_teamId = "(.*)";'
REGEX_STATIC_METALIST = r"g_staticMetalist = (\[.*\]);"

# post body attributes
ATTR_LIST_ID = "listId"
ATTR_LIST_NAME = "name"
ATTR_LIST_TYPE = "listType"

ATTR_ITEM_ID = "itemId"
ATTR_ITEM_CROSSED = "crossedOff"
ATTR_ITEM_VALUE = "value"
ATTR_ITEM_CATEGORY = "categoryId"
ATTR_ITEM_NOTE = "note"
ATTR_ITEMS = "items"
ATTR_COMMAND = "command"
ATTR_TEAM_ID = "teamId"

# properties of returned data
PROP_LIST = "list"
PROP_ITEMS = "items"


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"


def add_crossed_off_prop(item):
    """Adds crossed off prop to any items that don't have it."""
    item[ATTR_ITEM_CROSSED] = item.get(ATTR_ITEM_CROSSED, False)
    return item


def list_item_to_payload(item, list_id):
    """Maps a list item (scalar value or a tuple (value, category, note)) to payload"""
    if isinstance(item, str):
        payload = {ATTR_ITEM_VALUE: item}
    else:
        item = item + (None, None)
        payload = {
            ATTR_ITEM_VALUE: item[0],
            ATTR_ITEM_CATEGORY: item[1],
            ATTR_ITEM_NOTE: item[2],
        }
    payload[ATTR_LIST_ID] = list_id
    return payload


class OurGroceries:
    def __init__(self, username, password):
        """Set Our Groceries username and password."""
        self._username = username
        self._password = password
        self._session_key = None
        self._team_id = None

    def login(self):
        """Logs into Our Groceries."""
        self._get_session_cookie()
        self._get_team_id()
        self._get_master_list_id()
        _LOGGER.debug("ourgroceries_sync logged in")

    def _get_session_cookie(self):
        """Gets the session cookie value."""
        _LOGGER.debug("ourgroceries_sync _get_session_cookie")
        data = {
            FORM_KEY_USERNAME: self._username,
            FORM_KEY_PASSWORD: self._password,
            FORM_KEY_ACTION: FORM_VALUE_ACTION,
        }
        with requests.Session() as session:
            session.headers.update({"User-Agent": USER_AGENT})
            resp = session.post(SIGN_IN, data=data, headers={"User-Agent": USER_AGENT})

            # Extracting cookies
            session_cookie = session.cookies.get(COOKIE_KEY_SESSION)
            if session_cookie:
                self._session_key = session_cookie
                _LOGGER.debug(
                    "ourgroceries_sync found _session_key {}".format(self._session_key)
                )
            else:
                _LOGGER.error("ourgroceries_sync Could not find cookie session")
                raise InvalidLoginException("Could not find session cookie")

    def _get_team_id(self):
        """Gets the team id for a user."""
        _LOGGER.debug("ourgroceries_sync _get_team_id")
        cookies = {COOKIE_KEY_SESSION: self._session_key}
        resp = requests.get(
            YOUR_LISTS, cookies=cookies, headers={"User-Agent": USER_AGENT}
        )
        response_text = resp.text
        self._team_id = re.findall(REGEX_TEAM_ID, response_text)[0]
        _LOGGER.debug("ourgroceries_sync found team_id {}".format(self._team_id))
        static_metalist = json.loads(
            re.findall(REGEX_STATIC_METALIST, response_text)[0]
        )
        category_list = [
            _list for _list in static_metalist if _list["listType"] == "CATEGORY"
        ][0]
        self._category_id = category_list["id"]
        _LOGGER.debug(
            "ourgroceries_sync found category_id {}".format(self._category_id)
        )

    def _get_master_list_id(self):
        """Gets the master list id for a user."""
        _LOGGER.debug("ourgroceries_sync _get_master_list_id")
        cookies = {COOKIE_KEY_SESSION: self._session_key}
        resp = requests.get(
            YOUR_LISTS, cookies=cookies, headers={"User-Agent": USER_AGENT}
        )
        response_text = resp.text
        self._master_list_id = re.findall(REGEX_MASTER_LIST_ID, response_text)[0]
        _LOGGER.debug(
            "ourgroceries_sync found master_list_id {}".format(self._master_list_id)
        )

    def get_my_lists(self):
        """Get our grocery lists."""
        _LOGGER.debug("ourgroceries_sync get_my_lists")
        return self._post(ACTION_GET_LISTS)

    def get_category_items(self):
        """Get category items."""
        _LOGGER.debug("ourgroceries_sync get_category_items")
        other_payload = {ATTR_LIST_ID: self._category_id}
        data = self._post(ACTION_GET_LIST, other_payload)
        return data

    def get_list_items(self, list_id):
        """Get a grocery list's items."""
        _LOGGER.debug("ourgroceries_sync get_list_items")
        other_payload = {ATTR_LIST_ID: list_id}
        data = self._post(ACTION_GET_LIST, other_payload)
        data[PROP_LIST][PROP_ITEMS] = list(
            map(add_crossed_off_prop, data[PROP_LIST][PROP_ITEMS])
        )
        return data

    def create_list(self, name, list_type="SHOPPING"):
        """Create a new shopping list."""
        _LOGGER.debug("ourgroceries_sync create_list")
        other_payload = {
            ATTR_LIST_NAME: name,
            ATTR_LIST_TYPE: list_type.upper(),
        }
        return self._post(ACTION_LIST_CREATE, other_payload)

    def create_category(self, name):
        """Create a new category."""
        _LOGGER.debug("ourgroceries_sync create_category")
        other_payload = {
            ATTR_ITEM_VALUE: name,
            ATTR_LIST_ID: self._category_id,
        }
        return self._post(ACTION_ITEM_ADD, other_payload)

    def toggle_item_crossed_off(self, list_id, item_id, cross_off=False):
        """Toggles a list's item's crossed off property."""
        _LOGGER.debug("ourgroceries_sync toggle_item_crossed_off")
        other_payload = {
            ATTR_LIST_ID: list_id,
            ATTR_ITEM_ID: item_id,
            ATTR_ITEM_CROSSED: cross_off,
        }
        return self._post(ACTION_ITEM_CROSSED_OFF, other_payload)

    def add_item_to_list(
        self, list_id, value, category="uncategorized", auto_category=False, note=None
    ):
        """Add a new item to a list."""
        _LOGGER.debug("ourgroceries_sync add_item_to_list")
        other_payload = {
            ATTR_LIST_ID: list_id,
            ATTR_ITEM_VALUE: value,
            ATTR_ITEM_CATEGORY: category,
            ATTR_ITEM_NOTE: note,
        }
        if auto_category:
            other_payload.pop(ATTR_ITEM_CATEGORY, None)
        return self._post(ACTION_ITEM_ADD, other_payload)

    def add_items_to_list(self, list_id, items):
        """
        Add many items to a list.

        :param list_id: the id of the list to add the items to
        :param items sequence of items, each being just a value, or a tuple (value, category, note).
        :return: the response from the server.
        """
        _LOGGER.debug("ourgroceries_sync add_items_to_list")
        other_payload = {ATTR_ITEMS: [list_item_to_payload(i, list_id) for i in items]}
        return self._post(ACTION_ITEM_ADD_ITEMS, other_payload)

    def remove_item_from_list(self, list_id, item_id):
        """Remove an item from a list."""
        _LOGGER.debug("ourgroceries_sync remove_item_from_list")
        other_payload = {
            ATTR_LIST_ID: list_id,
            ATTR_ITEM_ID: item_id,
        }
        return self._post(ACTION_ITEM_REMOVE, other_payload)

    def get_master_list(self):
        """Get a grocery list's items."""
        _LOGGER.debug("ourgroceries_sync get_list_items")
        other_payload = {ATTR_LIST_ID: self._master_list_id}
        return self._post(ACTION_GET_LIST, other_payload)

    def get_category_list(self):
        """Get our grocery lists."""
        _LOGGER.debug("ourgroceries_sync get_master_list")
        other_payload = {ATTR_TEAM_ID: self._team_id}
        return self._post(ACTION_GET_CATEGORY_LIST, other_payload)

    def delete_list(self, list_id):
        """Create a new shopping list."""
        _LOGGER.debug("ourgroceries_sync create_list")
        other_payload = {
            ATTR_LIST_ID: list_id,
            ATTR_TEAM_ID: self._team_id,
        }
        return self._post(ACTION_LIST_REMOVE, other_payload)

    def delete_all_crossed_off_from_list(self, list_id):
        """delete all crossed off items from a list."""
        _LOGGER.debug("ourgroceries_sync remove_item_from_list")
        other_payload = {
            ATTR_LIST_ID: list_id,
        }
        return self._post(ACTION_LIST_DELETE_ALL_CROSSED_OFF, other_payload)

    def add_item_to_master_list(self, value, category_id):
        """Add a new item to a list."""
        _LOGGER.debug("ourgroceries_sync add_item_to_list")
        other_payload = {
            ATTR_LIST_ID: self._master_list_id,
            ATTR_ITEM_VALUE: value,
            ATTR_CATEGORY_ID: category_id,
        }
        return self._post(ACTION_ITEM_ADD, other_payload)

    def change_item_on_list(self, list_id, item_id, category_id, value):
        """Add a new item to a list."""
        _LOGGER.debug("ourgroceries_sync add_item_to_list")
        other_payload = {
            ATTR_ITEM_ID: item_id,
            ATTR_LIST_ID: list_id,
            ATTR_ITEM_NEW_VALUE: value,
            ATTR_CATEGORY_ID: category_id,
            ATTR_TEAM_ID: self._team_id,
        }
        return self._post(ACTION_ITEM_CHANGE_VALUE, other_payload)

    def _post(self, command, other_payload=None):
        """Post a command to the API."""
        if not self._session_key:
            self.login()

        cookies = {COOKIE_KEY_SESSION: self._session_key}
        payload = {ATTR_COMMAND: command}

        if self._team_id:
            payload[ATTR_TEAM_ID] = self._team_id

        if other_payload:
            payload = {**payload, **other_payload}

        return requests.post(
            YOUR_LISTS,
            json=payload,
            cookies=cookies,
            timeout=10,
            headers={"User-Agent": USER_AGENT},
        ).json()
