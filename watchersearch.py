from datetime import datetime
import os

def build_search(search_term = ""):
    changes = {}
    with open("changes.txt","r") as f:
        for line in f.readlines():
            line = line.strip()
            if line == "":
                continue
            changes[line.split(" ")[0]] = line.split(" ")[1]
    f.close()
    search = ""
    file_list = os.listdir("pages")
    file_info_list = [(file_name, os.path.getmtime(os.path.join("pages",file_name))) for file_name in file_list]
    sorted_file_list = sorted(file_info_list, key=lambda x: x[0])
    for file_name,timestamp in sorted_file_list:
        if search_term and search_term.lower() not in file_name.lower():
            continue
        status = ""
        if file_name in changes:
            inserted = int(changes[file_name].split('/')[0])
            sold = int(changes[file_name].split('/')[1])
            if inserted > sold:
                diff = min(10,inserted)/10
                status = "style=\"background:rgba(34,139,34,"+str(diff)+");\" "
            else:
                diff = min(10, sold)/10
                status = "style=\"background:rgba(220, 20, 60, "+str(diff)+");\" "
            
        article_name = file_name[:-5].split('_')[-1].replace('-',' ')
        search += "<div class=\"d-flex mb-4 col-12 col-sm-6 col-md-4 col-lg-2\">" + \
		            "<a " + status + "name=\"" + file_name + "\" href=\"?name="+file_name+"\" class=\"card text-center w-100 galleryBox\">" + \
		                "<img src=\"static/Blanko/images/" + file_name[:-5] +".jpg" +\
                        "\" alt=\"" + article_name + "\" class=\"lazy card-img-top img-fluid\">" + \
			            "<div class=\"card-body d-flex flex-column\">" + \
				            "<h2 class=\"card-title h3\">" + \
					            "</span>&nbsp;"+\
                                article_name + "<br/>" + \
				            "</h2>" + \
                            "<span style=\"fontweight:none;fontsize:12;\">(" + \
                                datetime.fromtimestamp(float(timestamp)).strftime('%d.%m.%Y') + \
                            ")</span>" + \
			            "</div>" + \
		            "</a>" + \
	              "</div>"
    return search