import random
import time
import os
import pyautogui
import pyperclip
from language_libraries import *
from watcherbase import watcherbase
import threading

def create_window_to_stop_updating(stopper):
    if pyautogui.confirm("Stop Update:", "Stop Update", buttons=["STOP"]) == "STOP":
        stopper[0] = True
    return

def download_page(page_name):
    if not page_name:
        return
    page_link = watcherbase.get_address_from_name(page_name)
    pyautogui.hotkey('ctrl', 't')
    pyperclip.copy(page_link)
    pyautogui.hotkey('ctrl', 'v')
    pyautogui.hotkey('enter')
    time.sleep(2.5 + random.random())
    pyautogui.hotkey('ctrl','s')
    time.sleep(0.1)
    pyautogui.hotkey('enter')
    time.sleep(0.1)
    pyautogui.hotkey('ctrl','w')
    time.sleep(0.1)

def update_all_pages():
    counter = 0
    for file_name in os.listdir("pages"):
        page_link = watcherbase.get_address_from_name(file_name)
        pyautogui.hotkey('ctrl', 't')
        pyperclip.copy(page_link)
        pyautogui.hotkey('ctrl', 'v')
        pyautogui.hotkey('enter')
        time.sleep(0.2)
        while(pyautogui.locateOnScreen("loading-cf.png",confidence=0.5)):
            time.sleep(1.0)
        counter += 1
        if counter == 10:
            counter = 0
            time.sleep(3)
            for i in range(10):
                pyautogui.hotkey('tab')
                pyautogui.hotkey('ctrl','down')
                while True:
                    try:
                        print("trying to find the show-more button")
                        pos = pyautogui.locateOnScreen('show-more.png',confidence=0.5)
                        if pos:
                            pyautogui.click(pos[0],pos[1])
                            time.sleep(3)
                        else:
                            break
                    except:
                        print("didn't find a button")
                        break
                pyautogui.hotkey('ctrl','s')
                time.sleep(0.1)
                pyautogui.hotkey('enter')
                time.sleep(0.1)
                pyautogui.hotkey('ctrl','w')
                time.sleep(0.1)
    if counter:
        time.sleep(3)
    for i in range(counter):
        pyautogui.hotkey('tab')
        pyautogui.hotkey('ctrl','down')
        while True:
            try:
                print("trying to find the show-more button")
                pyautogui.click('show-more.png')
                time.sleep(3)
            except:
                print("didn't find a button")
                break
        pyautogui.hotkey('ctrl','s')
        time.sleep(0.1)
        pyautogui.hotkey('enter')
        time.sleep(0.1)
        pyautogui.hotkey('ctrl','w')
        time.sleep(0.1)
    watcherbase.import_all_pages()

def update_all_pages_old():
    stopper = [False]

    files = os.listdir("pages")
    minutes = int(len(files)*5/60)
    threading.Thread(target=create_window_to_stop_updating, args=(stopper,)).start()
    if pyautogui.confirm("This will take around " + str(minutes) + " minutes. Are you sure?", "Confirmation", buttons=["OK", "Cancel"]) != "OK":
        return
    
    counter = 0
    for file_name in files:
        page_link = watcherbase.get_address_from_name(file_name)
        if stopper[0]:
            return
        pyautogui.hotkey('ctrl', 't')
        pyperclip.copy(page_link)
        pyautogui.hotkey('ctrl', 'v')
        pyautogui.hotkey('enter')

        while(True):
            try:
                pyautogui.locateOnScreen("loading-cf.png")
                time.sleep(1.0)
            except:
                break

        # add locateOnScreen for user click field
        try:
            pos = pyautogui.locateOnScreen("click-cf.png")
            time.sleep(0.2)
            
            if stopper[0]:
                pyautogui.hotkey('ctrl','w')
                return
            print("we are not free to go. Let's see if it notices we are not a human.")
            pyautogui.click(pos[0],pos[1])
            time.sleep(3.0)
        except:
            print("we are free to go.")
            
        while(True):
            try:
                pyautogui.hotkey('tab')
                pyautogui.hotkey('ctrl', 'down')
                time.sleep(0.2)
                pos = pyautogui.locateOnScreen('show-more.png')
                if pos:
                    print("found button")
                    if stopper[0]:
                        pyautogui.hotkey('ctrl','w')
                        return
                    pyautogui.click(pos[0],pos[1])
                    pyautogui.move(0, -50)
                    time.sleep(2.0)
            except:
                break

        if stopper[0]:
            pyautogui.hotkey('ctrl','w')
            return
        pyautogui.hotkey('ctrl','s')
        time.sleep(0.3)

        # give every download an unique int identifier, to enable downloads with same card names
        pyautogui.hotkey('left')
        pyperclip.copy(str(counter))
        pyautogui.hotkey('ctrl', 'v')
        pyautogui.hotkey('enter')
        time.sleep(0.3)
        pyautogui.hotkey('ctrl','w')
        time.sleep(0.3)
        counter += 1

