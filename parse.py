my_str = ""
with open("search.htm","r") as f:
	my_str = f.read().replace("<","\n<")
with open("search.htm","w") as f:
	f.write(my_str)