from ourgroceries_sync import OurGroceries

username = ""
password = ""

og = OurGroceries(username, password)
og.login()

my_lists = og.get_my_lists()
print(my_lists)

my_todo_list = og.get_list_items(list_id="")
print(my_todo_list)
