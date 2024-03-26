
from bs4 import BeautifulSoup
import os
import shutil
from page import Page
from listing import Listing
from language_libraries import *

class watcherbase():
    
    def get_name_from_address(address):
        return address[30:].replace('/','_')

    def get_address_from_name(name):
        return "https://www.cardmarket.com/en/" + name[:-5].replace('_','/')

    def delete_download(file_name):
        print("delete_download | deleting html " + file_name)
        os.remove(os.path.join("downloads",file_name))
        print("delete_download | deleting folder " + file_name[:-4] + "-Dateien")
        shutil.rmtree(os.path.join("downloads",file_name[:-4]+"-Dateien"))
    

    def get_page(page_name):
        active_page = Page()
        active_page.canonical_name = page_name[:-5]
        active_page.import_page(os.path.join("pages",page_name))
        return active_page
    
    def save_image(path,new_path):
        try: 
            if os.path.exists(new_path):
                return
            shutil.copy2(path, new_path)
        except Exception as e:
            print("save_image: ERROR: " + str(e))

    def import_all_pages():
        changes = {}
        file_list = os.listdir("downloads")
        file_info_list = [(file_name, os.path.getmtime(os.path.join("downloads",file_name))) for file_name in file_list if file_name.lower().endswith(".htm")]
        sorted_file_info_list = sorted(file_info_list, key=lambda x: x[1])
        for file_name,timestamp in sorted_file_info_list:
            print("import_all_pages | importing " + file_name)
            content = ""
            with open(os.path.join("downloads",file_name),'r',encoding="utf-8") as f:
                content = f.read()

            parsed_html = BeautifulSoup(content)
            if not parsed_html.body:
                watcherbase.delete_download(file_name)
                print("import_all_pages | no html found")
                continue
            table_body = parsed_html.body.find('div', attrs={'class':'table-body'})

            page = Page()
            if not parsed_html.find_all('link'):
                watcherbase.delete_download(file_name)
                print("import_all_pages | no link found")
                continue
            page.canonical_name = watcherbase.get_name_from_address(parsed_html.find_all('link')[0]['href'])

            if not parsed_html.body.find('div',attrs={'class':'page-title-container'}):
                watcherbase.delete_download(file_name)
                print("import_all_pages | no page-title found")
                continue
            page.card = parsed_html.body.find('div',attrs={'class':'page-title-container'}).find('h1').find(string=True,recursive=False).replace('Ã©','e')
            
            if not parsed_html.body.find('div',attrs={'id':'articleFilterSellerLocation'}):
                watcherbase.delete_download(file_name)
                print("import_all_pages | no seller location filter found")
                continue
            checkmark = parsed_html.body.find('div',attrs={'id':'articleFilterSellerLocation'}).find('input',attrs={'class':'form-check-input'})
            checked_country = parsed_html.body.find('div',attrs={'id':'articleFilterSellerLocation'}).find('div',attrs={'class','form-check'}).find('label').text
            page.only_germany = False
            if 'checked' in checkmark.attrs and ("Deutschland" in checked_country or "Germany" in checked_country):
                page.only_germany = (checkmark['checked'] == 'checked')
            print("import_all_pages | only listings from germany: " + str(page.only_germany))

            # get the active languages
            all_languages = []
            for language in parsed_html.body.find('div',attrs={'id':'articleFilterProductLanguage'}).find_all('div',attrs={'class':'form-check'}):
                all_languages.append(language_to_english[language.text] if language.text in language_to_english else language.text)
                checkbox = language.find('input',attrs={'class':'form-check-input'})
                if "checked" in checkbox.attrs and checkbox['checked'] == "checked":
                    page.languages.append(language.text)
            # if no language is checked, all languages in the list are active
            if len(page.languages) == 0:
                for language in all_languages:
                    page.languages.append(language_to_english[language] if language in language_to_english else language)

            # get the product image
            card_slideshow = parsed_html.body.find('div',attrs={'class':'card-slideshow'})
            if card_slideshow:
                image_path = card_slideshow.find_all('div',attrs={'class':'slide'})[1].find('img')['src'].replace('%20',' ').replace('%C3%A9','é')
            else:
                image_path = parsed_html.body.find('section',attrs={'id':'image'}).find('img')['src'].replace('%20',' ').replace('%C3%A9','é')
            page.image = "static/Blanko/images/" + (page.canonical_name) + ".jpg" 
            watcherbase.save_image(os.path.join("downloads",image_path),page.image)
            print("import_all_pages | image saved under " + page.image)
            
            # get the set the product is from    
            page.set = parsed_html.body.find('div',attrs={'class':'page-title-container'}).find('h1').find('span').text.replace('Ã©','e')
            
            # check if the user loaded all listings
            if parsed_html.find('button',attrs={'id':'loadMoreButton'}):
                page.loadMoreButton = True
            
            for item in parsed_html.find_all('button', attrs={'class':'mt-2 text-muted text-center'}):
                if item.text == "We only show the first 300 articles. Please use the filters for more precise results.":
                    page.loadMoreButton = True
                    break

            # iterate over the available listings and parse them
            for row in table_body.find_all('div', attrs={'class':'article-row'}):
                # skip rows that sell playsets, those are usually not actual playsets, but some other random combinations
                if row.find('span',attrs={'data-bs-original-title':'Playset'}):
                    continue
                # skip additional rows by active seller
                if "stockRow" in row["id"] or "shoppingCartRow" in row["id"]:
                    continue
                listing = Listing()
                listing.card = page.card
                listing.parse_from_row(row)
                listing.date = timestamp
                listing.canonical_name = page.canonical_name
                page.listings.append(listing)

            # open the corresponding old page and compare it with the newly created one
            old_page = Page()
            old_page.canonical_name = page.canonical_name
            old_page.import_page(os.path.join("pages",old_page.canonical_name+".page"))
            old_page.update_page(page)
            old_page.save()
            print("import_all_pages | page saved under " + os.path.join("pages",(old_page.canonical_name+".page")))
            watcherbase.delete_download(file_name)
            changes[page.canonical_name + ".page"] = str(old_page.inserted) + "/" + str(old_page.sold)
        # print changes to file
        with open("changes.txt", "r") as f:
            old_changes = {}
            for line in f.read().split('\n'):
                if len(line.split(" ")) < 2:
                    continue
                old_changes[line.split(" ")[0]] = line.split(" ")[1]
            for key, value in changes.items():
                old_changes[key] = value
        f.close()
        with open("changes.txt", "w") as f:
            for key,value in old_changes.items():
                f.write(key + " " + str(value) + "\n")
        f.close()
    