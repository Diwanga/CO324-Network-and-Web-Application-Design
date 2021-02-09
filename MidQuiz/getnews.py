#!/usr/bin/env python3
import sys
import requests
from bs4 import BeautifulSoup as bs4

SITE='https://lite.cnn.io/'
pageno =1


def get_links(html_text, keywords):    
    url_list=[] 
    soup = bs4(html_text, 'html.parser')
    ul = soup.ul
    atags =ul.find_all("a") 
  
    for tag  in atags:
         
        headline = tag.string.lower().split() 
        

        for key in keywords:
          if(key in headline):  
            url = "https://lite.cnn.com"+tag.get('href')
            url_list.append(url)
            break  
    return url_list


def save_to_disk(news_link):
    global pageno
    filename = str(pageno)+".html"  

    result = requests.get(news_link)
      
    with open(filename, 'w') as file:
        file.write(result.text)
        print(filename+" is saved to Disk")
    
    pageno += 1



if __name__ == "__main__":  
    
    if not len(sys.argv)  > 1:
        print (f'usage: getnews.py keyword')
        exit(-1)
   
    try:
      result = requests.get(SITE)
      html_text = result.text 
  
      keywords = sys.argv[1:]

      urls = get_links(html_text, [arg.lower() for arg in keywords])
       
      for url in urls:  
        save_to_disk(url)
        
    except KeyboardInterrupt:
        print("Oparation is stopped By user.. Exiting..")
    except requests.exceptions.RequestException:
        print("Cannot made http request... Exiting..")
    